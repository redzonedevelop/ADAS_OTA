from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from crypto import crypto
import boto3
import paho.mqtt.client as mqtt
import pymysql
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.secret_key = 'redzone'

S3_BUCKET = ''
s3 = boto3.client(
    's3',
    aws_access_key_id='',
    aws_secret_access_key='',
    region_name=''
)

rds_host=''
rds_user=''
rds_password=''
rds_database=''
rds_port=3306

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

    password_hash = crypto.compute_password_hash(password)

    with open("crypto/pwfile.txt", "r") as pwfile:
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)