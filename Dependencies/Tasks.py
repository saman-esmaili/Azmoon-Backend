from fastapi.security import HTTPBearer
import string
import random
from sqlalchemy import select, exists
from Database.DB import Class
import jdatetime
auth_scheme = HTTPBearer()

async def generate_link(session):
    chars = string.ascii_letters + string.digits
    while True:
        random_str = ''.join(random.choice(chars) for _ in range(15))
        is_exist = session.scalar(
            select(exists().where(Class.signup_link==random_str))
        )
        if not is_exist:
            break
    return random_str

def generate_code():
    return str(random.randint(10000, 99999))

