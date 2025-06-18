import paho.mqtt.client as mqtt
import json
import base64
import socket
import os
import struct

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
        data = json.loads(msg.payload.decode())
        ecu = data.get("ecu")
        version = data.get("version")
        filename = data.get("file_name")
        filedata = data.get("file_data")
        print(f"subscribe: ECU={ecu}, VERSION={version}, filename={filename}")

        file_bytes = base64.b64decode(filedata)
        save_path = f"./{filename}"
        with open(save_path, 'wb') as f:
                f.write(file_bytes)
                print(f"file {save_path} save complete!")

        receiver_ip = ""
        port = 9000
        send_file_over_ethernet(save_path, receiver_ip, port)

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("ota/update")
client.loop_forever()