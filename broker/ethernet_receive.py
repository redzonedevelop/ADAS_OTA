import socket
import struct
import time
from collections import defaultdict
from crypto import decrypt_file_aes, verify_sign
import win32com.client

# 설정
UDP_PORT = 9000
AES_KEY_HEX = ''
PUBLIC_KEY_PATH = 'key/Public_key2.pem'
MAX_TIMEOUT = 5

aes_key = bytes.fromhex(AES_KEY_HEX)
buffer = defaultdict(dict)
meta = {}

# CANoe 연결
app = win32com.client.Dispatch("CANoe.Application")
system = app.System
namespace = system.Namespaces("VUM")

def handle_received_data(transfer_id, full_payload):
    # 1. 데이터 길이와 패킷 분리
    len_data = struct.unpack('!I', full_payload[0:4])[0]
    encrypted = full_payload[4:4+len_data]
    offset = 4 + len_data
    len_sig = struct.unpack('!I', full_payload[offset:offset+4])[0]
    signature = full_payload[offset+4 : offset+4+len_sig]

    # 2. 복호화
    iv = encrypted[:16]
    cipher_text = encrypted[16:]
    decrypted = decrypt_file_aes(cipher_text, aes_key, iv)

    # 3. 서명 검증
    valid = verify_sign(signature, decrypted, PUBLIC_KEY_PATH)
    if not valid:
        print("[❌] 서명 검증 실패: CANoe에 쓰지 않음")
        return

    print("[✅] 서명 검증 성공 — 전체 데이터 수신 및 검증 완료")
    #print(decrypted)
    split_index = decrypted.find(b"=")
    if split_index == -1:
        print("[❌] 구분자 '=' 없음 - 형식 오류")
        return

    metadata_bytes = decrypted[:split_index]
    file_bytes = decrypted[split_index+1:]

    # 3. 메타데이터 디코딩 및 canoe에 쓰기
    metadata_str = metadata_bytes.decode('utf-8', errors='replace')
    #print(f"[📝] 메타데이터: {metadata_str}")
    erged_str = decrypted.decode(errors='replace')
    pairs = metadata_str.split(',')
    info = dict(pair.split(':', 1) for pair in pairs)

    variable = namespace.Variables("ecu_number")
    ecu_id = int(info.get("ecu_id", 0))
    variable.Value = ecu_id

    variable = namespace.Variables("version")
    version = int(info.get("version", 0))
    variable.Value = version

    variable = namespace.Variables("file_size")
    file_size = int(info.get("file_size", 0))
    variable.Value = file_size
    print("데이터가 metadata 변수에 설정되었습니다.")


    # 4. 파일 저장
    with open("data.bin", "wb") as f:
        f.write(file_bytes)
    variable = namespace.Variables("fileupload")
    variable.Value = 1
    print(f"[📦] data.bin 파일 저장 완료 (크기: {len(file_bytes)} bytes)")
    print()

    # except Exception as e:
    #     print(f"[⚠️] 처리 실패: {e}")
    #     break

def receive_udp_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", UDP_PORT))
    print(f"🔄 UDP 수신 대기 중 (PORT {UDP_PORT})...")

    while True:
        try:
            data, addr = sock.recvfrom(65536)

            transfer_id = data[0:4]
            total_parts = int.from_bytes(data[4:6], 'big')
            index = int.from_bytes(data[6:8], 'big')
            payload = data[8:]

            buffer[transfer_id][index] = payload
            if transfer_id not in meta:
                meta[transfer_id] = {
                    'total': total_parts,
                    'start_time': time.time()
                }

            print(f"[📥] 수신: ID={transfer_id.hex()} Seq={index+1}/{total_parts}")

            if len(buffer[transfer_id]) == total_parts:
                print("[🔧] 전체 조립 완료, 처리 시작...")
                full_payload = b''.join(buffer[transfer_id][i] for i in range(total_parts))
                handle_received_data(transfer_id, full_payload)
                del buffer[transfer_id]
                del meta[transfer_id]

            # 타임아웃 처리
            now = time.time()
            for tid in list(meta.keys()):
                if now - meta[tid]['start_time'] > MAX_TIMEOUT:
                    print(f"[⏰] 타임아웃: ID {tid.hex()} 버림")
                    del buffer[tid]
                    del meta[tid]

        except Exception as e:
            print(f"[⚠️] 수신 예외: {e}")

# 실행
if __name__ == '__main__':
    receive_udp_loop()
