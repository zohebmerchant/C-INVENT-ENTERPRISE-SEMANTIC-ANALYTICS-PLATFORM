import argparse, hashlib, secrets

p=argparse.ArgumentParser(description='Generate a C INVENT Streamlit Secrets password hash')
p.add_argument('password')
a=p.parse_args()
salt=secrets.token_hex(16)
digest=hashlib.pbkdf2_hmac('sha256', a.password.encode(), bytes.fromhex(salt), 200_000).hex()
print('salt =', repr(salt))
print('password_hash =', repr(digest))
