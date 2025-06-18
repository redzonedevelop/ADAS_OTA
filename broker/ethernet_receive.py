import socket
import os
import struct

def receive_file(save_dir="./received", port=9000):
    os.makedirs(save_dir, exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", port))
        s.listen(1)
        print(f"[🔌] 포트 {port}에서 수신 대기 중...")

        conn, addr = s.accept()
        with conn:
            print(f"[📥] 연결 수신: {addr}")

            # 파일 이름 길이 수신 (4바이트)
            filename_len = struct.unpack('!I', conn.recv(4))[0]
            # 파일 이름 수신
            filename = conn.recv(filename_len).decode()

            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            save_path = os.path.join(save_dir, filename)
            with open(save_path, "wb") as f:
                f.write(data)
            print(f"[✔] 파일 저장 완료: {save_path}")

# 실행
receive_file()
