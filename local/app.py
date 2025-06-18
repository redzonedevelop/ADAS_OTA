from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from crypto import crypto
import boto3
import paho.mqtt.client as mqtt

app = Flask(__name__)
app.secret_key = 'redzone'

def notify_broker(ecu, version):
    client = mqtt.Client()
    client.connect("192.168.137.22", 1883, 60)  # 포트는 기본 MQTT 포트 1883

    payload = {
        "ecu": ecu,
        "version": version,
        "status": "ready"
    }

    import json
    client.publish("ota/update", json.dumps(payload))
    client.disconnect()

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
    ecu = request.form['ecu']
    file = request.files['file']

    if file:
        original_filename = file.filename
        _, ext = os.path.splitext(original_filename)
        ext = ext.lstrip('.')

        try:
            s3_filename = f"{ecu}_{version}.{ext}"
            s3.upload_fileobj(file, S3_BUCKET, s3_filename)
            flash(f"{s3_filename} 업로드 완료 (버전: {version}, ECU: {ecu})")
        except Exception as e:
            flash(f"업로드 실패 ({e})")
            print(f"Upload failed: {e}")

    else:
        flash("파일이 없습니다!")

    return redirect(url_for('upload_page'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)