from typing import Annotated

from sqlalchemy import select, func
from sqlmodel import case
from starlette.responses import JSONResponse

from Dependencies.Calculate import to_jalali, months_remaining
from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter
from fastapi.params import Depends
from Database.DB import sessionDep, Cart, Teacher, Plan, Transaction, UserPlan, Question, Student, StudentClass, Class

router = APIRouter(prefix='/teacher/plan')

@router.get('')
async def my_plan(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    get_info = (session.query(UserPlan,Plan)
                .filter(UserPlan.teacher_id==teacher_id,UserPlan.is_active==True)
                .outerjoin(Plan,Plan.id==UserPlan.plan_id)
                )

    result = {}
    for up,p in get_info:
        result['plan_id'] = p.id
        result['name'] = p.name
        result['remained_exam'] = p.exam_number-up.exam_count
        result['exam'] = p.exam_number
        result['exam_count'] = up.exam_count
        result['expired_date'] = to_jalali(up.expired_date)
        result['remained_expire'] = months_remaining(up.expired_date)
        result['image_number'] = p.image_number
        result['image_count'] = up.image_count

    return JSONResponse({'my_plan':result},status_code=200)
