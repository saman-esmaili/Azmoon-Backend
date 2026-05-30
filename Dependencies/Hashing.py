import hashlib
from passlib.hash import argon2

def hash_pass(raw_pass: str) -> str:
    return argon2.hash(raw_pass)

def verify_pass(raw_pass: str, hashed_pass: str) -> bool:
    return argon2.verify(raw_pass, hashed_pass)

# def hash_token(token:str):
#     return hashlib.sha256(token.encode()).hexdigest()
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
