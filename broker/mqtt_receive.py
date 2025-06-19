import paho.mqtt.client as mqtt
import socket
import os
import struct
from hashlib import sha256
from crypto import decrypt_file_aes, verify_sign

aes_key_hex = ''
aes_key = bytes.fromhex(aes_key_hex)
public_key_path = "key/Public_key1.pem"

decrypted = None

def send_file_over_ethernet(file_path, receiver_ip, port):
        filename = os.path.basename(file_path).encode()
        with open(file_path, 'rb') as f:
                data = f.read()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((receiver_ip, port))
                s.sendall(struct.pack('!I', len(filename)))
                s.sendall(filename)
                s.sendall(data)
                print(f"file {file_path} send complete!")

def on_message(client, userdata, msg):
    global decrypted

    if msg.topic == "update/metadata/data":
        data = msg.payload
        iv = data[:16]
        cipher_text = data[16:]

        try:
            decrypted = decrypt_file_aes(cipher_text, aes_key, iv)
            print("message: ", decrypted.decode())
        except Exception as e:
            print("fail: ", e)

    elif msg.topic == "update/data/data":
        data = msg.payload
        iv = data[:16]
        cipher_text = data[16:]

        try:
            decrypted = decrypt_file_aes(cipher_text, aes_key, iv)
            print("message: ", decrypted.decode())
        except Exception as e:
            print("fail: ", e)

    elif msg.topic == "update/metadata/sign":
        signature = msg.payload
        is_valid = verify_sign(signature, decrypted, public_key_path)
        print("success" if is_valid else "fail")

    elif msg.topic == "update/data/sign":
        signature = msg.payload
        is_valid = verify_sign(signature, decrypted, public_key_path)
        print("success" if is_valid else "fail")
        
        # file_bytes = base64.b64decode(filedata)
        # save_path = f"./{filename}"
        # with open(save_path, 'wb') as f:
        #         f.write(file_bytes)
        #         print(f"file {save_path} save complete!")

        # receiver_ip = ""
        # port = 9000
        # send_file_over_ethernet(save_path, receiver_ip, port)


client = mqtt.Client()
client.username_pw_set("", "")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("update/metadata/data")
client.subscribe("update/metadata/sign")
client.subscribe("update/data/data")
client.subscribe("update/data/sign")

client.loop_forever()