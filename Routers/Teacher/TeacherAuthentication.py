
from typing import Annotated, Optional

from fastapi import HTTPException, APIRouter
from fastapi.params import Depends, Body
from pydantic import BaseModel
from pydantic.v1 import EmailStr
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse

from Database.DB import sessionDep, Teacher, EDU_QUA, SpcField, User
from Dependencies.Redis import r
from Dependencies.Tasks import generate_code
from Routers.Auths.MainAuth import authorization, UserCode

router = APIRouter(prefix='/teacher/profile')

async def get_teacher(session:sessionDep,payload: Annotated[authorization, Depends()]):
    user_id = payload['user_id']
    get_types = r.get(f'teacher-types{user_id}')
    if not get_types:
        try:
            teacher = session.query(Teacher).filter(Teacher.user_id==user_id).first().id
        except:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        r.set(f'teacher-types{user_id}',teacher)
        get_types = r.get(f'teacher-types{user_id}')

    return {'teacher':get_types}


@router.get('')
async def get_profile(session:sessionDep,user_types: Annotated[get_teacher, Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    teacher,user = (session.query(Teacher,User).filter(Teacher.id==teacher_id)
                    .join(User,User.id==Teacher.user_id)
                    ).first()
    result = {'name':user.name,'last_name':user.last_name,
              'school_name':teacher.school_name,'specialized_field':teacher.specialized_field,
              'educational_qualification':teacher.educational_qualification,'email':user.email,
              'mobile':user.mobile}
    return JSONResponse(content={'teacher_info':result})

class TeacherInfo(BaseModel):
    name: Optional[str] = Field(None, max_length=30, min_length=4)
    last_name: Optional[str] = Field(None, max_length=30, min_length=4)
    specialized_field: Optional[SpcField] = Field(None)
    educational_qualification: Optional[EDU_QUA] = Field(None)

@router.post('/add/personal')
async def add_personal(session:sessionDep,user_types: Annotated[get_teacher, Depends()],items:Annotated[TeacherInfo,Body()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    teacher = session.query(Teacher).filter(Teacher.id==teacher_id)
    selected_teacher = teacher.first()
    teacher_val = {
        'educational_qualification': items.educational_qualification,
        'specialized_field':items.specialized_field
    }
    update_teacher = teacher.update(teacher_val)
    if items.name or items.last_name:
        user_val = {
            'name':items.name,
            'last_name':items.last_name
        }
        user = session.query(User).filter(User.id==selected_teacher.user_id)
        user_update = user.update(user_val)

    session.commit()

    return JSONResponse(content={'profile':'updated'},status_code=200)

class TeacherContact(BaseModel):
    mobile: str = Field(max_length=11, min_length=11, regex=r'^09[0-3,9]\d{8}$')
    email: Optional[str] = Field(None)
    school_name: Optional[str] = Field(min_length=4, max_length=20)

async def send_otp_change(mobile,user_id):
    exist_code = r.get(f'OTP:{mobile}')
    if not exist_code:
        code = generate_code()
    else:
        code = exist_code.decode('utf-8')
    # send code by sms panel
    print(code)
    r.set(f'OTP:{mobile}', code, ex=120)
    r.set(f'user_id:{mobile}', user_id, ex=120)

async def check_mobile(old,new,user_id):
    if old != new:
        await send_otp_change(new,user_id)
        return True
    return False

@router.post('/add/contact')
async def add_contact(session:sessionDep,user_types: Annotated[get_teacher, Depends()],items:Annotated[TeacherContact,Body()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    teacher = session.query(Teacher).filter(Teacher.id==teacher_id)
    user_id = teacher.first().user_id
    teacher_val = {
        'school_name':items.school_name
    }
    teacher_update = teacher.update(teacher_val)
    user = session.query(User).filter(User.id==user_id)
    user_mobile = user.first().mobile
    is_new = await check_mobile(user_mobile,items.mobile,user_id)

    if items.email:
        user_val = {
            'email':items.email
        }
        user.update(user_val)
    content = {'new':True if is_new else False,'mobile':items.mobile if is_new else ''}
    session.commit()
    return JSONResponse(status_code=status.HTTP_200_OK,content=content)



@router.post('/verify')
async def add_contact(session:sessionDep,user_types: Annotated[get_teacher, Depends()],items:Annotated[UserCode,Body()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    original_code = (r.get(f'OTP:{items.mobile}')).decode('utf-8')
    user_id = (r.get(f'user_id:{items.mobile}')).decode('utf-8')
    if original_code == items.code:
        user = session.query(User).filter(User.id==user_id)
        user.update({'mobile':items.mobile})
        session.commit()
        return JSONResponse(content={'change mobile':'successful'},status_code=status.HTTP_200_OK)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
