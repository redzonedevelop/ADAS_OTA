import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import hashlib

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
