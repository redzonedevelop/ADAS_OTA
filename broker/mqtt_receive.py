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

received_part = {"data": None, "sign": None, "type": None}

def send_ethernet(message, receiver_ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (receiver_ip, port))
    #print(f"send complete")
    sock.close()

def notify_ethernet(data, type):
    global received_part

    if type == "metadata":
        type_byte = b'\x01'
    elif type == "data":
        type_byte = b'\x02'
    else:
        print("no type error")
        return

    iv, cipher_text = encrypt_file_aes(data, new_aes_key)
    encrypt_data = iv + cipher_text
    signature = sign_file(data, private_key_path)

    raw_payload = (
        type_byte +
        struct.pack('!I', len(encrypt_data)) + encrypt_data +
        struct.pack('!I', len(signature)) + signature
    )

    transfer_id = uuid.uuid4().bytes[:4]
    total_parts = math.ceil(len(raw_payload) / MAX_PACKET_SIZE)

    for index in range(total_parts):
        part_data = raw_payload[index * MAX_PACKET_SIZE : (index + 1) * MAX_PACKET_SIZE]

        header = ( type_byte + transfer_id + total_parts.to_bytes(2, 'big') + index.to_bytes(2, 'big') )
        packet = header + part_data
        send_ethernet(packet, cgw_ip, cgw_port)
        print(f"send: {index+1}/{total_parts}, size: {len(packet)}B")
        # payload = (type_byte + struct.pack('!I', len(encrypt_data)) + encrypt_data + struct.pack('!I', len(signature)) + si>

def on_message(client, userdata, msg):
    global received_part

    if msg.topic.endswith("/data"):
        data = msg.payload
        iv = data[:16]
        cipher_text = data[16:]

        try:
            decrypted = decrypt_file_aes(cipher_text, aes_key, iv)
            #print("message: ", decrypted.decode())
            print("message receive")
            received_part["data"] = decrypted

            if "metadata" in msg.topic:
                received_part["type"] = "metadata"
            elif "data" in msg.topic:
                received_part["type"] = "data"

        except Exception as e:
            print("message fail: ", e)

    elif msg.topic.endswith("/sign"):
        received_part["sign"] = msg.payload

        if received_part["data"] is None:
            print("no data")
            return

        is_valid = verify_sign (received_part["sign"], received_part["data"], public_key_path)
        if not is_valid:
            print("verify fail")
        else:
            print("verify success")
            notify_ethernet(received_part["data"], received_part["type"])

        received_part = {"data": None, "sign": None, "type": None}

client = mqtt.Client()
client.username_pw_set("", "")
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("update/metadata/data")
client.subscribe("update/metadata/sign")
client.subscribe("update/data/data")
client.subscribe("update/data/sign")
client.loop_forever()