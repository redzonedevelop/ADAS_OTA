import paho.mqtt.client as mqtt
from hashlib import sha256
from crypto import encrypt_file_aes, decrypt_file_aes, sign_file, verify_sign
import struct
import socket
import uuid
import math

aes_key_hex = ''
aes_key = bytes.fromhex(aes_key_hex)
public_key_path = "key/Public_key1.pem"

new_aes_key_hex = ''
new_aes_key = bytes.fromhex(new_aes_key_hex)
private_key_path = "key/Private_key2.pem"

cgw_ip = ""
cgw_port = 9000
MAX_PACKET_SIZE = 1400

def send_ethernet(message, receiver_ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (receiver_ip, port))
    #print(f"send complete")
    sock.close

def notify_ethernet(data):
    iv, cipher_text = encrypt_file_aes(data, new_aes_key)
    encrypt_data = iv + cipher_text
    signature = sign_file(data, private_key_path)

    raw_payload = (
        struct.pack('!I', len(encrypt_data)) + encrypt_data +
        struct.pack('!I', len(signature)) + signature
    )

    transfer_id = uuid.uuid4().bytes[:4]
    total_parts = math.ceil(len(raw_payload) / MAX_PACKET_SIZE)

    for index in range(total_parts):
        part_data = raw_payload[index * MAX_PACKET_SIZE : (index + 1) * MAX_PACKET_SIZE]

        header = (
            transfer_id +
            total_parts.to_bytes(2, 'big') +
            index.to_bytes(2, 'big')
        )
        packet = header + part_data
        send_ethernet(packet, cgw_ip, cgw_port)
        print(f"send: {index+1}/{total_parts}, size: {len(packet)}B")

def on_message(client, userdata, msg):

    if msg.topic == "update":
        try:
            data = msg.payload
            len_data = struct.unpack('!I', data[:4])[0]
            cipher_data = data[4:4+len_data]

            sig_offset = 4 + len_data
            len_sig = struct.unpack('!I', data[sig_offset:sig_offset+4])[0]
            signature = data[sig_offset+4 : sig_offset+4+len_sig]

            iv = cipher_data[:16]
            cipher_text = cipher_data[16:]
            decrypted = decrypt_file_aes(cipher_text, aes_key, iv)

            if verify_sign(signature, decrypted, public_key_path):
                print("sign success")
                notify_ethernet(decrypted)
            else:
                print("sign fail")
        except Exception as e:
            print("message fail: ", e)


client = mqtt.Client()
client.username_pw_set("admin", "1234")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("update")
client.loop_forever()
