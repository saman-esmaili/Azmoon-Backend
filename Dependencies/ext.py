import datetime
from jose import jwt
from typing import Annotated
import jwt
from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Body, Depends, Header, Query, Cookie
from pydantic import BaseModel
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Database.DB import User, sessionDep, Teacher, Student, StudentClass
from Dependencies.Hashing import hash_token, hash_pass
from Dependencies.Redis import r
from Dependencies.Tasks import generate_code

router = APIRouter()


# Send Code

class MobileUser(BaseModel):
    mobile: str = Field(max_length=11, min_length=11, regex=r'^09[0-3,9]\d{8}$')
    type: str


@router.post('/send-otp')
async def send_otp(mobile: Annotated[MobileUser, Body()], Admin: Annotated[str | None, Query()] = None):
    try:
        exist_code = r.get(f'OTP:{mobile.mobile}')
        if not exist_code:
            code = generate_code()
        else:
            code = exist_code.decode('utf-8')
        # send code by sms panel
        print(code)
        if Admin:
            await admin_user(Admin, mobile, session=sessionDep)
            r.set(f'TYPE:{mobile.mobile}', 'admin', ex=200)
        else:
            r.set(f'TYPE:{mobile.mobile}', mobile.type, ex=200)
        r.set(f'OTP:{mobile.mobile}', code, ex=120)
        # End
        return JSONResponse(status_code=status.HTTP_200_OK, content={'status': 'ok'})
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mobile Incorrect')


async def admin_user(Admin, mobile, session):
    password = Admin[3:]
    hashed_pass = hash_pass(password)
    is_admin = session.query(User).filter(User.mobile == mobile, User.password == hashed_pass,
                                          User.type == 'admin').first()
    if is_admin:
        return 'admin'
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mobile Incorrect')


class UserCode(BaseModel):
    code: str = Field(min_length=5, max_length=5)
    mobile: str = Field(max_length=11, min_length=11, regex=r'^09[0-3,9]\d{8}$')


async def check_user_exist(mobile, session):
    user_type = (r.get(f'TYPE:{mobile}')).decode('utf-8')
    is_exist = session.query(User).filter(User.mobile == mobile).first()
    if is_exist:
        user_id = is_exist.id
        if user_type == 'student':
            is_exist_type = session.query(Student).filter(Student.user_id == user_id).first()
        elif user_type == 'teacher':
            is_exist_type = session.query(Teacher).filter(Teacher.user_id == user_id).first()

        if is_exist_type:
            return await login(user_id, session)
        elif not is_exist_type:
            if user_type != 'admin':
                return await signup(session, mobile, user_id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    else:
        return await signup(session, mobile, user_id=-1)


# @router.post('/login')
async def login(user_id: int, session):
    if user_id:
        user_select = session.query(User).filter(User.id == user_id).first()
        user_select.last_login = datetime.datetime.now().date()
        session.commit()
        mobile = user_select.mobile
        try:
            class_id = (r.get(f'class_mobile:{mobile}')).decode('utf-8')
            await save_class(class_id, user_id, session)
        except:
            pass
        return {'user_id': user_id}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mobile Not Found')


async def signup(session, mobile, user_id):
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
            await save_student(user_id, session)
        elif user_type == 'teacher':
            await save_teacher(user_id, session)

        return await login(user_id, session)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mobile Not Found')


async def save_teacher(user_id, session):
    teacher = Teacher(
        user_id=user_id
    )
    session.add(teacher)
    session.commit()
    session.refresh(teacher)


async def save_student(user_id, session):
    student = Student(
        user_id=user_id
    )
    session.add(student)
    session.commit()
    session.refresh(student)

async def save_class(class_id, user_id, session):
    student_id = session.query(Student).filter(Student.user_id == user_id).first().id
    student_class = StudentClass(
        student_id=student_id,
        class_id=class_id,
        is_active=True
    )
    session.add(student_class)
    session.commit()
    session.refresh(student_class)


def get_user_info_from_token(access_token: str):
    decoded = jwt.decode(
        access_token,
        options={'verify_signature': False}
    )
    return decoded.get('app_user_id')
