import os
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

def compute_password_hash(password: str) -> str:
    sha256 = hashlib.sha256()
    sha256.update(password.encode('utf-8'))
    return sha256.hexdigest()

def encrypt_file_aes(file_data, aes_key):
    block_size = algorithms.AES.block_size

    padder = PKCS7(block_size).padder()
    padded_data = padder.update(file_data) + padder.finalize()

    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(aes_key),modes.CBC(iv), backend = default_backend())
    encryptor = cipher.encryptor()
    cipher_text = encryptor.update(padded_data) + encryptor.finalize()
    return iv, cipher_text

def decrypt_file_aes(cipher_text, aes_key, iv):
    block_size = algorithms.AES.block_size

    try:
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(cipher_text) + decryptor.finalize()

        unpadder = PKCS7(block_size).unpadder()
        decrypted_text = unpadder.update(padded_data) + unpadder.finalize()
        return decrypted_text
    
    except Exception as e:
        raise ValueError(f'Decryption failed: {e}')

def rsa_key_generation():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm = serialization.BestAvailableEncryption(b'private')
    )

    public_pem = public_key.public_bytes(
        encoding = serialization.Encoding.PEM,
        format = serialization.PublicFormat.SubjectPublicKeyInfo
    )

    key_path = os.path.join(os.getcwd(), 'key')
    os.makedirs(key_path, exist_ok= True)

    private_key_path = os.path.join(key_path, "Private_key1.pem")
    with open(private_key_path, 'wb') as key_file:
        key_file.write(private_pem)

    public_key_path = os.path.join(key_path, "Public_key1.pem")
    with open(public_key_path, 'wb') as key_file:
        key_file.write(public_pem)

def encrypt_file_rsa(file_data, public_key_path):
    with open(public_key_path, 'rb') as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
            backend = default_backend()
        )
    encrypted_file = public_key.encrypt(
        file_data,
        padding.OAEP(
            mgf = padding.MGF1(algorithm = hashes.SHA256()),
            algorithm = hashes.SHA256(),
            label = None
        )
    )
    return encrypted_file

def decrypt_file_rsa(encrypted_data, private_key_path):
    with open(private_key_path, 'rb') as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password = b'private',
            backend = default_backend()
        )
    decrypted_file = private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf = padding.MGF1(algorithm = hashes.SHA256()),
            algorithm = hashes.SHA256(),
            label = None
            )
        )
    return decrypted_file

def compute_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def sign_file(file_data, private_key_path):
    with open(private_key_path, 'rb') as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password = b'private',
            backend = default_backend()
        )

    signature = private_key.sign(
        file_data,
        padding.PSS(
            mgf = padding.MGF1(hashes.SHA256()),
            salt_length = padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature

def verify_sign(signature, file_data, public_key_path):
    with open(public_key_path, 'rb') as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
            backend = default_backend()
        )
    try:
        public_key.verify(
            signature,
            file_data,
            padding.PSS(
                mgf = padding.MGF1(hashes.SHA256()),
                salt_length = padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    
    except Exception:
        return False
        
def main():
    aes_key = os.urandom(32)
    print('AES key: ', aes_key)
    with open("C:/PICT/test.txt", 'rb') as file:
        file_data = file.read()
    print('Plain text: ', file_data)

    iv, encrypted_text = encrypt_file_aes(file_data, aes_key)
    print('AES Encrypted text: ', encrypted_text)

    decrypted_text = decrypt_file_aes(encrypted_text, aes_key, iv)
    print('AES Decrypted text: ', decrypted_text)

    rsa_encrypted_file =  encrypt_file_rsa(file_data, "C:/PICT/Key/Public_key.pem")
    print('RSA Encrypted text: ', rsa_encrypted_file)

    rsa_decrypted_file = decrypt_file_rsa(rsa_encrypted_file, "C:/PICT/Key/Private_key.pem")
    print('RSA Decrypted text: ', rsa_decrypted_file)
    file_hash = compute_file_hash("C:/PICT/test.txt")
    print("File hash: ", file_hash)

    signature = sign_file(file_data, "C:/PICT/Key/Private_key.pem")
    print('Signature of the file: ', signature)

    if verify_sign(signature, file_data, "C:/PICT/Key/Public_key.pem"):
        print('Verify success')
    else:
        print('verify failed')
