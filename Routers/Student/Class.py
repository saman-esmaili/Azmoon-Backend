
from math import ceil
from typing import Annotated

from fastapi.params import Query, Depends, Body
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse

from Routers.Student.Authentication import get_student
from fastapi import APIRouter, HTTPException
from Database.DB import sessionDep, StudentClass, Class, Teacher, User, UserPlan, Plan, Student

router = APIRouter(prefix='/student')


@router.get('/class')
async def get_class(session: sessionDep, user_type: Annotated[get_student, Depends()], page: int = Query(1, ge=1),
                    size: int = Query(10, ge=1, le=100), search: str = Query()):
    student_id = (user_type['student']).decode('utf-8')
    query = (session.query(StudentClass, Class, Teacher, User)
             .filter(StudentClass.student_id == student_id)
             .outerjoin(Class, Class.id == StudentClass.class_id)
             .outerjoin(Teacher, Teacher.id == Class.teacher_id)
             .outerjoin(User, User.id == Teacher.user_id)
             )
    total = query.count()
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            or_(
                Class.name.contains(search_term),
                Class.lesson.contains(search_term),
                (User.name + ' ' + User.last_name).contains(search_term)
            )
        )
    classes = (
        query
        .order_by(StudentClass.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size)
    result = []
    for sc, c, t, u in classes:
        result.append({'id': sc.id, 'name': c.name, 'teacher': f'{u.name} {u.last_name}', 'subject': c.lesson})
    return JSONResponse(content={'classes': result, 'pages': pages})


class Link(BaseModel):
    link: str = Field()


@router.post('/class/join')
async def join_class(session: sessionDep, user_type: Annotated[get_student, Depends()],
                     class_link: Annotated[Link, Body()]):
    student_id = (user_type['student']).decode('utf-8')
    cls = session.query(Class).filter(Class.signup_link == class_link.link).first()
    if cls:
        std_class = session.query(StudentClass).filter(StudentClass.class_id == cls.id,
                                                       StudentClass.student_id == student_id).first()
        if std_class:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT)
        else:
            user_plan = session.query(UserPlan).filter(UserPlan.teacher_id==cls.teacher_id,UserPlan.is_active==True).first()
            if user_plan:
                plan = session.query(Plan).filter(Plan.id==user_plan.plan_id).first()

                if 0 <= cls.student_number < plan.student_number:
                    cls.student_number += 1
                    student_class = StudentClass(
                        student_id=student_id,
                        class_id=cls.id,
                        is_active=True
                    )
                    session.add(student_class)
                    session.commit()
                    session.refresh(student_class)
                    return JSONResponse({'data':{'name':cls.name}})
                else:
                    raise HTTPException(status_code=400)
            else:
                raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)