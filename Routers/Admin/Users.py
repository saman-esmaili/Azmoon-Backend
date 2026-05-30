from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Query, Path
from sqlalchemy import func
from starlette import status
from starlette.responses import JSONResponse

from Database.DB import sessionDep, User, UserPlan, Plan, Teacher, Student, Exam, Class
from Routers.Admin.Authentication import get_admin

router = APIRouter(prefix='/admin')

@router.get('/users')
async def get_users(session:sessionDep,is_admin:Annotated[get_admin,Depends()],q:Annotated[str | None,Query()]=None):
    query_builder = session.query(UserPlan,User,Plan).outerjoin(User,UserPlan.user_id==User.id).outerjoin(Plan,UserPlan.plan_id==Plan.id)
    if q:
        query_builder = query_builder.filter(
            (User.name.contains(q)) |
            (User.last_name.contains(q)) |
            (User.mobile.contains(q)) |
            (Plan.name.contains(q))
        )

    users = query_builder.all()
    result = []
    for up,u,p in users:
        dic_res = {'id':u.id,'name':f'{u.name} {u.last_name}','mobile':u.mobile,
                   'last_login':str(u.last_login),'membership_date':str(u.membership_date),'plan':p.name}
        result.append(dic_res)
    return JSONResponse({'users':result},status_code=status.HTTP_200_OK)


@router.get('/user/{user_id}')
async def get_user(session:sessionDep,get_user:Annotated[get_admin,Depends()],user_id:Annotated[int,Path()]):
    sub_query = session.query(
        Exam.class_id,
        func.count(Exam.id).label('exam_count')
    ).group_by(Exam.class_id).subquery()

    user = (session.query(UserPlan,User,Teacher,Student,Plan,Class,sub_query.c.exam_count).filter(UserPlan.user_id==user_id,UserPlan.is_active==True)
            .outerjoin(User, User.id == UserPlan.user_id)
            .outerjoin(Student,Student.user_id==UserPlan.user_id)
            .outerjoin(Teacher,Teacher.user_id==UserPlan.user_id)
            .outerjoin(Plan,Plan.id==UserPlan.plan_id)
            .outerjoin(Class,Class.teacher_id==Teacher.id)
            .outerjoin(sub_query,sub_query.c.class_id==Class.id)
            .all()
            )
    result = []
    for up,u,t,s,p,c,exam_count in user:
        is_student = 1 if s else 0
        is_teacher = 1 if t else 0
        dic_res = {'name':f'{u.name} {u.last_name}','email':u.email,'mobile':u.mobile,'plan':p.name,'membership_date':str(u.membership_date),
                   'last_login':str(u.last_login),'is_student':is_student,'is_teacher':is_teacher,'exam_count':exam_count}
        result.append(dic_res)
    return JSONResponse({'user':result},status_code=status.HTTP_200_OK)




