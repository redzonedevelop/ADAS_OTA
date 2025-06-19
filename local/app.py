from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import boto3
import paho.mqtt.client as mqtt
import pymysql
import pymysql.cursors
from datetime import datetime, timedelta, timezone
from crypto import compute_password_hash, encrypt_file_aes, sign_file
import time

app = Flask(__name__)
app.secret_key = 'redzone'

S3_BUCKET = ''
s3 = boto3.client(
    's3',
    aws_access_key_id='',
    aws_secret_access_key='',
    region_name='ap-northeast-2'
)

rds_host=''
rds_user=''
rds_password=''
rds_database=''
rds_port=3306

aes_key_hex = ''
aes_key = bytes.fromhex(aes_key_hex)
private_key_path = "key/Private_key1.pem"

ecu_map = {
    1: "Motor",
    2: "Transmission",
    3: "BMS",
    4: "ABS",
    5: "Brake",
    6: "Steering",
    7: "ADAS",
    8: "VUM",
    9: "Telematic",
    10: "Rain",
    11: "Illuminate",
    12: "Light",
    13: "Seat",
    14: "OBD",
    15: "Cluster"
}

KST = timezone(timedelta(hours=9))

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    password_hash = compute_password_hash(password)

    with open("cryptof/pwfile.txt", "r") as pwfile:
        for line in pwfile:
            approved_user, approved_hash = map(str.strip, line.split(":"))
            if username == approved_user and password_hash == approved_hash:
                session['user'] = username
                flash("로그인 성공")
                return redirect(url_for('upload_page'))

    flash("로그인 실패: 아이디 또는 비밀번호가 일치하지 않습니다.")
    return redirect(url_for('login_page'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return render_template('upload.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    version = request.form['version']
    ecu_id = int(request.form['ecu'])
    ecu = ecu_map.get(ecu_id, "Unknown")
    file = request.files['file']

    if file:
        original_filename = file.filename
        _, ext = os.path.splitext(original_filename)
        ext = ext.lstrip('.')

        conn = pymysql.connect(
            host=rds_host,
            user=rds_user,
            password=rds_password,
            database=rds_database,
            port=rds_port
        )
        cursor = conn.cursor()

        try:
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)

            s3_filename = f"{ecu}_{version}.{ext}"
            s3.upload_fileobj(file, S3_BUCKET, s3_filename)

            sql = "INSERT INTO ecu_firmware (ecu_id, version, file_name, file_size, upload_datetime) VALUES (%s, %s, %s, %s, %s)"
            now_kst = datetime.now(KST)
            cursor.execute(sql, (ecu_id, version, s3_filename, file_size, now_kst))
            conn.commit()
            
            flash(f"{s3_filename} 업로드 완료 (버전: {version}, ECU: {ecu})")
        except Exception as e:
            flash(f"업로드 실패 ({e})")
            print(f"{e}")
        finally:
            cursor.close()
            conn.close()

    else:
        flash("파일이 없습니다!")

    return redirect(url_for('upload_page'))


@app.route('/firmware_list')
def firmware_list():
    try:
        conn = pymysql.connect(
            host=rds_host,
            user=rds_user,
            password=rds_password,
            database=rds_database,
            port=rds_port
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        result = {}
        ecu_ids_to_show = [1, 10, 11, 12]

        for ecu_id in ecu_ids_to_show:
            cursor.execute("SELECT * FROM ecu_firmware WHERE ecu_id = %s ORDER BY upload_datetime DESC", (ecu_id,))
            result[ecu_id] = cursor.fetchall()
    
    except Exception as e:
        flash(f"조회 실패 ({e})")
        print(f"{e}")
    finally:
        cursor.close()
        conn.close()

    return render_template(
        'firmware_list.html',
        ecu_data=result,
        ecu_map=ecu_map,
        title='펌웨어 전체 목록'
    )

def notify_broker(topic_base, encode_plain):
    # aes 암호화
    iv, cipher_text = encrypt_file_aes(encode_plain, aes_key)
    mqtt_payload = iv + cipher_text

    # 서명 생성
    signature = sign_file(encode_plain, private_key_path)

    # mqtt 연결
    client = mqtt.Client()
    client.username_pw_set("", "")
    client.connect("", 1883, 60)

    # 전송
    client.publish(f"{topic_base}/data", mqtt_payload)
    client.publish(f"{topic_base}/sign", signature)

    # 종료
    #time.sleep(1)
    client.disconnect()

@app.route('/release')
def release_page():
    try:
        conn = pymysql.connect(
            host=rds_host,
            user=rds_user,
            password=rds_password,
            database=rds_database,
            port=rds_port
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        ecu_ids = list(ecu_map.keys())
        ecu_data = {}

        for ecu_id in ecu_ids:
            cursor.execute("SELECT id, version, file_name FROM ecu_firmware WHERE ecu_id = %s ORDER BY upload_datetime DESC", (ecu_id,))
            ecu_data[ecu_id] = cursor.fetchall()

    except Exception as e:
        flash(f"조회 실패: {e}")
        ecu_data = {}

    finally:
        cursor.close()
        conn.close()

    return render_template(
        'release.html',
        ecu_data=ecu_data,
        ecu_map=ecu_map
    )

def save_integrated_firmware_to_db(version_name, request_form):
    firmware_ids = {}
    for ecu_id in range(1, 16):
        value = request_form.get(f'ecu_{ecu_id}')
        firmware_ids[ecu_id] = int(value) if value and value.lower() not in ['none', '0'] else None

    conn = pymysql.connect(
        host=rds_host,
        user=rds_user,
        password=rds_password,
        database=rds_database,
        port=rds_port
    )
    cursor = conn.cursor()

    try:
        sql = """
        INSERT INTO integrated_firmware (
            version_name,
            motor_fw_id, transmission_fw_id, bms_fw_id, abs_fw_id, brake_fw_id,
            steering_fw_id, adas_fw_id, vum_fw_id, telematic_fw_id, rain_fw_id,
            illuminate_fw_id, light_fw_id, seat_fw_id, obd_fw_id, cluster_fw_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """

        values = [
            version_name,
            firmware_ids[1], firmware_ids[2], firmware_ids[3], firmware_ids[4], firmware_ids[5],
            firmware_ids[6], firmware_ids[7], firmware_ids[8], firmware_ids[9], firmware_ids[10],
            firmware_ids[11], firmware_ids[12], firmware_ids[13], firmware_ids[14], firmware_ids[15]
        ]

        cursor.execute(sql, values)
        conn.commit()

    except Exception as e:
        raise e

    finally:
        cursor.close()
        conn.close()

    return firmware_ids

def send_firmware_via_mqtt(firmware_ids):
    conn = pymysql.connect(
        host=rds_host,
        user=rds_user,
        password=rds_password,
        database=rds_database,
        port=rds_port
    )
    cursor = conn.cursor()

    try:
        os.makedirs("tmp", exist_ok=True)  # tmp 디렉토리 없으면 생성

        for ecu_id, fw_id in firmware_ids.items():
            if fw_id is None:
                continue

            cursor.execute("SELECT version, file_name, file_size FROM ecu_firmware WHERE id = %s", (fw_id,))
            row = cursor.fetchone()
            if row:
                version = row[0]
                file_name = row[1]
                file_size = row[2]
                ecu_name = ecu_map.get(ecu_id, f"ecu{ecu_id}")

                metadata_str = f"ecu_name:{ecu_name},version:{version},file_name:{file_name},file_size:{file_size}"
                notify_broker('update/metadata', metadata_str.encode())
                print(f"{ecu_name}_{file_name} metadata send!")

                local_path = f"tmp/{file_name}"
                s3.download_file(S3_BUCKET, file_name, local_path)

                with open(local_path, "rb") as f:
                    file_bytes = f.read()
                notify_broker('update/data', file_bytes)
                print(f"{ecu_name}_{file_name} data send!")

    except Exception as e:
        raise e

    finally:
        cursor.close()
        conn.close()

@app.route('/release_file', methods=['POST'])
def release_file():
    try:
        version_name = request.form.get('version_name')
        firmware_ids = save_integrated_firmware_to_db(version_name, request.form)
        send_firmware_via_mqtt(firmware_ids)
        flash("배포 완료!")
    except Exception as e:
        flash(f"배포 실패: {e}")
    return redirect(url_for('release_page'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)