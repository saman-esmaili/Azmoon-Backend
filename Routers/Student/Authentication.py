from typing import Annotated, Optional
from pydantic import BaseModel, EmailStr
from sqlalchemy.testing.suite.test_reflection import users
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Database.DB import sessionDep, User, Student, Class, StudentClass
from fastapi import APIRouter, HTTPException
from fastapi.params import Path, Body, Depends
from Dependencies.Redis import r
from Routers.Auths.MainAuth import authorization, UserCode
from Routers.Teacher.TeacherAuthentication import check_mobile

router = APIRouter(prefix='/student')

class SignClassItem(BaseModel):
    mobile: str = Field(max_length=11, min_length=11,regex=r'^09[0-3,9]\d{8}$')

@router.post('/class-sign/{url}')
async def signup_class(session:sessionDep,url:Annotated[str,Path()],item:Annotated[SignClassItem,Body()]):
    class_exists = session.query(Class).filter(Class.signup_link==url).first()
    if not class_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    class_id = class_exists.id
    r.set(f'class_mobile:{item.mobile}',class_id,ex=200)
    return JSONResponse({'status':{'mobile':item.mobile,'class_id':class_id}},status.HTTP_200_OK)



async def get_student(payload: Annotated[authorization, Depends()],session:sessionDep):
    user_id = payload['user_id']
    get_types = r.get(f'student-types{user_id}')
    if not get_types:
        try:
            student = session.query(Student).filter(Student.user_id==user_id).first().id
            r.set(f'student-types{user_id}', student)
            get_types = r.get(f'student-types{user_id}')
        except:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    return {'student':get_types}


@router.get('/info')
async def student_info(session:sessionDep,get_student_type:Annotated[get_student,Depends()]):
    student_id = (get_student_type['student']).decode('utf-8')
    student = (session.query(Student,User)
               .filter(Student.id == student_id)
               .outerjoin(User,User.id==Student.user_id)
               )
    result = {}
    for st,user in student:
        result['name'] = user.name
        result['last_name'] = user.last_name
        result['mobile'] = user.mobile
        result['email'] = user.email
    return JSONResponse({'student_info':result},status_code=status.HTTP_200_OK)

class StudentInfo(BaseModel):
    name: Optional[str] = Field(None, max_length=30, min_length=4)
    last_name: Optional[str] = Field(None, max_length=30, min_length=4)
    mobile: str = Field(max_length=11, min_length=11, regex=r'^09[0-3,9]\d{8}$')
    email: Optional[EmailStr] = Field(None)


@router.post('/info')
async def update_student_info(session:sessionDep,get_student_type:Annotated[get_student,Depends()],item:Annotated[StudentInfo,Body()]):
    student_id = (get_student_type['student']).decode('utf-8')
    user_id = session.query(Student).filter(Student.id == student_id).first().user_id
    user_val = {
        'name': item.name,
        'last_name': item.last_name,
        'email': item.email
    }
    user = session.query(User).filter(User.id==user_id)
    user_mobile = user.first().mobile
    is_new = await check_mobile(user_mobile,item.mobile,user_id)
    user.update(user_val)
    content = {'new':True if is_new else False,'mobile':item.mobile if is_new else ''}
    session.commit()
    return JSONResponse(status_code=status.HTTP_200_OK,content=content)



@router.post('/verify')
async def change_mobile(session:sessionDep,get_student_type:Annotated[get_student,Depends()],items:Annotated[UserCode,Body()]):
    student_id = (get_student_type['student']).decode('utf-8')
    original_code = (r.get(f'OTP:{items.mobile}')).decode('utf-8')
    user_id = (r.get(f'user_id:{items.mobile}')).decode('utf-8')
    if original_code == items.code:
        user = session.query(User).filter(User.id==user_id)
        user.update({'mobile':items.mobile})
        session.commit()
        return JSONResponse(content={'change mobile':'successful'},status_code=status.HTTP_200_OK)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)


