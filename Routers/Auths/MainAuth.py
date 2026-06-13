import datetime
import random
import secrets
from datetime import timedelta
from typing import Annotated
import jwt
import redis.exceptions
from fastapi import APIRouter, HTTPException,Response,Request
from fastapi.params import Body, Depends, Header, Query, Cookie
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Database.DB import User, sessionDep, Teacher, Student, StudentClass, Admin, Class
from Dependencies.Hashing import hash_token, hash_pass, verify_pass
from Dependencies.Redis import r
import os
from Dependencies.Tasks import auth_scheme, generate_code

router = APIRouter()
current_dir = os.path.dirname(os.path.abspath(__file__))
secret_file_path = os.path.join(current_dir, '..', '..', 'Dependencies', 'secret.txt')
with open(secret_file_path, 'r') as file:
    secret = file.read()

# for OAUTH2
REFRESH_EXPIRE_TIME = 24*7*60*60
auth2 = OAuth2PasswordBearer(tokenUrl='verify-code')
ALGORITHM = 'HS256'

# Send Code

class MobileUser(BaseModel):
    mobile: str = Field(max_length=11, min_length=11,regex=r'^09[0-3,9]\d{8}$')
    type: str

@router.post('/send-otp')
async def send_otp(mobile:Annotated[MobileUser,Body()],session:sessionDep,Admin:Annotated[str | None,Query()]=None,class_url:Annotated[str | None,Query()]=None):
    try:
        exist_code = r.get(f'OTP:{mobile.mobile}')
        if not exist_code:
            code = generate_code()
        else:
            code = exist_code.decode('utf-8')
        # send code by sms panel
        print(code)
        if class_url and class_url != 'null':
            r.setex(f'class_url:{mobile.mobile}',500,class_url)

        if Admin and Admin != 'null':
            await admin_user(Admin,mobile,session=session)
            r.set(f'TYPE:{mobile.mobile}', 'admin', ex=200)
        else:
            r.set(f'TYPE:{mobile.mobile}',mobile.type,ex=200)
        r.set(f'OTP:{mobile.mobile}', code, ex=120)
        # End
        return JSONResponse(status_code=status.HTTP_200_OK,content={'status':'ok'})
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Mobile Incorrect')


async def admin_user(Admin,mobile,session):
    admin = session.query(User).filter(User.mobile == mobile.mobile).first()
    password = admin.password
    is_admin = verify_pass(Admin,password)
    if is_admin:
        return 'admin'
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Mobile Incorrect')


class UserCode(BaseModel):
    code: str = Field(min_length=5,max_length=5)
    mobile: str = Field(max_length=11, min_length=11,regex=r'^09[0-3,9]\d{8}$')

@router.post('/verify-code/')
async def verify_code(user_code:Annotated[UserCode,Body()],session:sessionDep):
    try:
        original_code = (r.get(f'OTP:{user_code.mobile}')).decode('utf-8')
        if original_code == user_code.code:
            user_type = (r.get(f'TYPE:{user_code.mobile}')).decode('utf-8')
            raw_refresh,access_token =  await check_user_exist(user_code.mobile,session)
            response = JSONResponse(content={'role':user_type})
            response.set_cookie(
                key='access_token',
                value=access_token,
                max_age=15 * 60,
                httponly=True,
                secure=False, # true in https (product)
                samesite='lax',
                path='/'
            )
            response.set_cookie(
                key='refresh_token',
                value=raw_refresh,
                max_age=REFRESH_EXPIRE_TIME,
                httponly=True,
                secure=False,
                samesite='lax',
                path='/'
            )
            return response
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='dissimilar code')
    except redis.exceptions.TimeoutError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Timeout')

async def check_user_exist(mobile,session):
    user_type = (r.get(f'TYPE:{mobile}')).decode('utf-8')
    is_exist = session.query(User).filter(User.mobile == mobile).first()
    if is_exist:
        user_id = is_exist.id
        if user_type == 'student':
            is_exist_type = session.query(Student).filter(Student.user_id==user_id).first()
        elif user_type == 'teacher':
            is_exist_type = session.query(Teacher).filter(Teacher.user_id==user_id).first()
        else:
            is_exist_type = session.query(Admin).filter(Admin.user_id == user_id).first()

        if is_exist_type:
            return await login(user_id,session)
        elif not is_exist_type:
            if user_type!='admin':
                return await signup(session, mobile, user_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    else:
        return await signup(session,mobile,user_id=-1)

def create_access_token(user_id:int):
    # exp should be 15 min
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + timedelta(minutes=1)
    }
    access_token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    return access_token

def create_refresh_token():
    raw = secrets.token_urlsafe(32)
    return raw,hash_token(raw)

# @router.post('/login')
async def login(user_id:int,session):
    if user_id:
        access_token = create_access_token(user_id)
        raw_refresh,refresh_hash = create_refresh_token()
        r.setex(refresh_hash,REFRESH_EXPIRE_TIME,user_id)
        user_select = session.query(User).filter(User.id==user_id).first()
        user_select.last_login = datetime.datetime.now().date()
        session.commit()
        mobile = user_select.mobile
        try:
            class_id = (r.get(f'class_url:{mobile}')).decode('utf-8')
            await save_class(class_id,user_id,session)
        except:
            pass
        return (raw_refresh,access_token)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='Mobile Not Found')

async def get_refresh_token(refresh_token: Annotated[str | None, Cookie()] = None):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token cookie not found"
        )
    return refresh_token
async def get_access_token(access_token: Annotated[str | None, Cookie()] = None):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token cookie not found"
        )
    return access_token
@router.post('/refresh')
async def refresh_token(refresh_token: Annotated[str, Depends(get_refresh_token)]):
    response = JSONResponse(content={'refresh_status':'ok'})
    passed_hash_refresh = hash_token(refresh_token)
    user_id = r.get(passed_hash_refresh)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='invalid refresh token')
    user_id = user_id.decode('utf-8')
    raw_refresh,hashed_refresh = create_refresh_token()
    r.setex(hashed_refresh,REFRESH_EXPIRE_TIME,user_id)
    access_token = create_access_token(user_id)
    r.delete(passed_hash_refresh)
    r.setex(passed_hash_refresh,10,user_id)
    response.set_cookie(
        key='access_token',
        value=access_token,
        max_age=15*60,
        httponly=True,
        secure=False,
        samesite='lax',
        path='/'
    )
    response.set_cookie(
        key='refresh_token',
        value=raw_refresh,
        max_age=REFRESH_EXPIRE_TIME,
        httponly=True,
        secure=False,
        samesite='lax',
        path = '/'
    )
    return response

async def signup(session,mobile,user_id):
    if mobile:
        user_type = (r.get(f'TYPE:{mobile}')).decode('utf-8')
        if user_id == -1:
            user = User(
                mobile=mobile,
                type=user_type,
                membership_date=datetime.datetime.now().date(),
                last_login=datetime.datetime.now().date()
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            user_id = user.id

        if user_type == 'student':
            await save_student(user_id,session)
        elif user_type == 'teacher':
            await save_teacher(user_id,session)

        return await login(user_id,session)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mobile Not Found')

async def save_teacher(user_id,session):
    teacher = Teacher(
        user_id=user_id
    )
    session.add(teacher)
    session.commit()
    session.refresh(teacher)

async def save_student(user_id,session):
    student = Student(
        user_id=user_id
    )
    session.add(student)
    session.commit()
    session.refresh(student)


@router.get('/authorization')
async def authorization(token: Annotated[str, Depends(get_access_token)]):
    try:
        # token = creds.credentials
        payload = jwt.decode(token,secret,algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Expired Token')
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Token')

async def save_class(class_url,user_id,session):
    student_id = session.query(Student).filter(Student.user_id==user_id).first().id
    class_id = session.query(Class).filter(Class.signup_link==class_url).first().id
    student_class = StudentClass(
        student_id=student_id,
        class_id=class_id,
        is_active=True
    )
    session.add(student_class)
    session.commit()
    session.refresh(student_class)


@router.post('/logout')
async def logout(raw_refresh:Annotated[str,Header()]):
    hash_refresh = hash_token(raw_refresh)
    user_id = r.get(hash_refresh)
    r.delete(hash_refresh)
    r.delete(f'teacher-types{user_id}')
    r.delete(f'admin-types{user_id}')
    r.delete(f'student-types{user_id}')
    return {'status':'logged out'}



@router.post('/revoke')
async def revoke(access_token: Annotated[str | None, Cookie()] = None,refresh_token: Annotated[str | None, Cookie()] = None):
    hash_refresh = hash_token(refresh_token)
    user_id = r.get(hash_refresh)
    r.delete(hash_refresh)
    r.delete(access_token)
    r.delete(f'teacher-types{user_id}')
    r.delete(f'admin-types{user_id}')
    r.delete(f'student-types{user_id}')
    return {'revoke_status':'ok'}