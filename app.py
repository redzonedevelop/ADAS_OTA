from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from crypto import crypto

app = Flask(__name__)
app.secret_key = 'redzone'

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
    return redirect(url_for('login_page'))

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)