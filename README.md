# Vehicle OTA Update System

A prototype over-the-air (OTA) firmware update pipeline for in-vehicle ECUs, built with:

- **Flask** web server on AWS EC2  
- **RDS** (MySQL/PostgreSQL) for metadata  
- **S3** for firmware storage  
- **MQTT (paho-mqtt)** for control messages  
- **Raspberry Pi** as a combined MQTT/UDP bridge  
- **UDP** for high-throughput binary delivery to CANoe/STM32 ECU

---

## 🚀 Overview

1. **Admin UI (Flask)**
   - Login/logout  
   - Upload individual ECU firmware  
   - Create “integrated” firmware bundles  
   - Publish an encrypted+signed “update” message over MQTT

2. **Bridge (mqtt_receive.py)**
   - Subscribes to `update` topic  
   - Decrypts & verifies incoming payload  
   - Re-encrypts & re-signs, splits into MTU-sized UDP packets  
   - Sends packets to ECU LAN

3. **Receiver (ethernet_receive.py)**
   - Listens on UDP port 9000  
   - Buffers/fragments by transfer ID & sequence index  
   - Reassembles, decrypts & verifies full payload  
   - Pushes metadata & binary into CANoe variables (or writes `data.bin`)

---

## 🔧 Directory Structure

```
├── app.py                          # Flask server & MQTT publisher
├── mqtt_receive.py                 # Raspberry Pi bridge script
├── ethernet_receive.py             # UDP receiver & CANoe adapter
├── templates/                      # Jinja2 UI templates
│   ├── layout.html
│   ├── login.html
│   ├── upload.html
│   ├── firmware_list.html
│   ├── release.html
│   └── integrated_firmware_list.html
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

---

## ⚙️ Installation & Setup

1. **Clone repository**  
   ```bash
   git clone https://github.com/your-org/vehicle-ota.git
   cd vehicle-ota
   ```

2. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**  
   Create a `.env` or export:

   ```bash
   # Flask Server
   export FLASK_APP=app.py
   export FLASK_SECRET_KEY="your-flask-secret"
   export AWS_ACCESS_KEY_ID=…
   export AWS_SECRET_ACCESS_KEY=…
   export S3_BUCKET=your-bucket-name
   export DB_URL="mysql+pymysql://user:pass@hostname/dbname"

   # Crypto
   export AES_KEY="32-byte-base64-encoded"
   export RSA_PRIVATE_KEY="path/to/private.pem"
   export RSA_PUBLIC_KEY="path/to/public.pem"

   # Bridge & Receiver
   export BROKER_IP=""
   export BROKER_PORT=1883
   export CGW_IP=""
   export CGW_PORT=9000
   ```

---

## ▶️ Usage

### 1. Start Flask Server

```bash
flask run --host 0.0.0.0 --port 5000
```

- Visit `http://<EC2-IP>:5000/login`

### 2. Launch Bridge on Raspberry Pi

```bash
python mqtt_receive.py
```

- Subscribes to `update`  
- Sends UDP fragments to `CGW_IP:9000`

### 3. Start UDP Receiver (CANoe Host)

```bash
python ethernet_receive.py
```

- Listens on UDP port 9000  
- Reassembles & writes `data.bin` + updates CANoe variables

---

## 📦 Payload Formats

### MQTT Payload

```
[4B] len_encrypted_data
[ N ] IV (16B) + AES-256( metadata ∥ file_bytes )
[4B] len_signature
[ M ] RSA-signature( SHA256( metadata ∥ file_bytes ) )
```

- **len_encrypted_data**: 32-bit BE integer  
- **IV + cipher_text**: first 16 bytes = IV; rest = AES-256CBC(encrypted metadata||file)  
- **len_signature**: 32-bit BE integer  
- **signature**: RSA signature bytes

### UDP Packet Structure

```
[4B] transfer_id (first 4 bytes of UUID)
[2B] total_parts
[2B] index
[ ≤MAX_PACKET_SIZE ] fragment of raw_payload
```

- Reassemble by grouping same `transfer_id`, ordering by `index`, until `total_parts` received.

---

## 🏗️ Architecture Diagram

```mermaid
flowchart LR
  subgraph AWS
    EC2[EC2: Flask Server]
    RDS[(RDS)]
    S3[(S3)]
  end
  subgraph LAN
    Broker[Pi: MQTT→UDP Bridge]
    ECU[STM32/CANoe Host]
  end
  EC2 -- MQTT(update) --> Broker
  EC2 -- API --> S3_and_RDS
  Broker -- UDP(9000) --> ECU
```

---

## 🤝 Contributing

1. Fork & clone  
2. Create feature branch  
3. Commit & PR  
4. Ensure tests pass & documentation updated

---

## 📝 License

This project is licensed under the MIT License.  
See [LICENSE](./LICENSE) for details.
