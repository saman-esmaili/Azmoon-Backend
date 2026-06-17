import datetime
from math import ceil
from typing import Annotated, Optional

import jdatetime
from fastapi.params import Depends, Body, Path, Query
from pydantic import BaseModel
from sqlalchemy import select, exists, func, or_
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Database.DB import sessionDep, StudentClass, Exam, UserPlan
from Database.DB import Class
from Dependencies.Tasks import generate_link
from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter, HTTPException

from permissions.Teacher import plan_permit

router = APIRouter(prefix='/teacher')


class ClsItem(BaseModel):
    name: str = Field(min_length=4, max_length=25)
    lesson: str = Field(min_length=4, max_length=25)
    grade: str
    description: Optional[str] = Field(None, min_length=4, max_length=200)


@router.post('/add/class')
async def add_class(cls_items: Annotated[ClsItem, Body()], user_types: Annotated[get_teacher, Depends()],
                    session: sessionDep):
    teacher_id = (user_types['teacher']).decode('utf-8')
    has_permit = await plan_permit(teacher_id, session)
    if not has_permit:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED)
    link = await generate_link(session)
    name_is_exist = session.scalar(
        select(exists().where((Class.teacher_id == teacher_id) & (Class.name == cls_items.name)))
    )
    if name_is_exist:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)

    cls = Class(
        name=cls_items.name,
        lesson=cls_items.lesson,
        grade=cls_items.grade,
        description=cls_items.description,
        teacher_id=teacher_id,
        signup_link=link,
        date=datetime.datetime.now()
    )
    session.add(cls)
    session.commit()
    session.refresh(cls)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={'Status': 'Ok'})


@router.get('/class/header')
async def get_class_header(session: sessionDep, user_types: Annotated[get_teacher, Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    class_count = select(
        Class.teacher_id.label('class_teacher_id'),
        func.count(func.distinct(Class.id)).label('class_count')
    ).group_by(Class.teacher_id).subquery()
    count_exam = select(
        Exam.class_id.label('exam_class_id'),
        func.count(func.distinct(Exam.id)).label('exam_count')
    ).group_by(Exam.class_id).subquery()
    count_student = select(
        StudentClass.class_id.label('sc_class_id'),
        func.count(func.distinct(StudentClass.id)).label('student_count')
    ).group_by(StudentClass.class_id).subquery()

    now = jdatetime.datetime.now()

    next_exam_subq = (
        select(
            Exam.class_id.label("class_id"),
            Exam.exam_date.label("exam_date"),
            Exam.name.label("exam_name"),
            Exam.exam_time.label("exam_time"),
        )
        .where(
            func.concat(Exam.exam_date, ' ', Exam.exam_time) >
            now.strftime('%Y-%m-%d %H:%M:%S')
        )
        .order_by(
            func.concat(Exam.exam_date, ' ', Exam.exam_time)
        )
        .limit(1)
        .subquery()
    )

    q = (
        session.query(
            Class,
            class_count.c.class_count,
            count_exam.c.exam_count,
            count_student.c.student_count,
            next_exam_subq.c.exam_name,
            next_exam_subq.c.exam_date,
            next_exam_subq.c.exam_time,
        )
        .filter(Class.teacher_id == teacher_id)
        .outerjoin(class_count, class_count.c.class_teacher_id == Class.teacher_id)
        .outerjoin(count_exam, count_exam.c.exam_class_id == Class.id)
        .outerjoin(count_student, count_student.c.sc_class_id == Class.id)
        .outerjoin(next_exam_subq, next_exam_subq.c.class_id == Class.id)
        .with_entities(
            func.coalesce(class_count.c.class_count, 0).label('class_count'),
            func.coalesce(count_exam.c.exam_count, 0).label('exam_count'),
            func.coalesce(count_student.c.student_count, 0).label('student_count'),
            next_exam_subq.c.exam_name,
            next_exam_subq.c.exam_date,
            next_exam_subq.c.exam_time,
        )
    )

    res = q.first()
    if res:
        result = {'class_count': res.class_count, 'exam_count': res.exam_count, 'student_count': res.student_count,
                  'next_exam_name': res.exam_name, 'next_exam_date': res.exam_date}
    else:
        result = {'class_count': 0, 'exam_count': 0, 'student_count': 0,
                  'next_exam_name': '-', 'next_exam_date': '-'}

    return JSONResponse(status_code=status.HTTP_200_OK, content={'all_info': result})


@router.get('/class')
async def show_class(session: sessionDep, user_types: Annotated[get_teacher, Depends()]
                     , page: int = Query(1, ge=1), size: int = Query(6, ge=1, le=100),
                     search: str = Query()
                     ):
    teacher_id = (user_types['teacher']).decode('utf-8')
    count_student = select(
        StudentClass.class_id.label('student_class_id'),
        func.count(StudentClass.id).label('student_count')
    ).group_by(StudentClass.class_id).subquery()
    query = (session.query(Class, count_student.c.student_count)
             .filter(Class.teacher_id == teacher_id)
             .outerjoin(count_student, count_student.c.student_class_id == Class.id)
             .with_entities(Class.id, Class.name, Class.lesson, Class.grade, Class.description, Class.signup_link,
                            func.coalesce(count_student.c.student_count, 0).label('student_count'))
             .order_by(Class.date))
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Class.name.contains(search_term),
                Class.lesson.contains(search_term),
                Class.grade.contains(search_term),
            )
        )

    total = query.count()
    get_classes = (
        query
        .order_by(Class.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    classes = [
        {'id': c.id, 'name': c.name, 'subject': c.lesson, 'grade': c.grade, 'description': c.description,
         'link': c.signup_link, 'student_count': c.student_count} for c in get_classes
    ]
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={'class': classes, 'pages': ceil(total / size) if total else 1})


@router.put('/edit/class/{class_id}')
async def edit_class(cls_item: Annotated[ClsItem, Body()], session: sessionDep,
                     user_types: Annotated[get_teacher, Depends()], class_id: Annotated[int, Path()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    my_class = session.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher_id)
    name_is_exist = session.scalar(
        select(exists().where((Class.teacher_id == teacher_id) & (Class.name == cls_item.name)))
    )
    if name_is_exist:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)

    class_vals = {
        'name': cls_item.name,
        'lesson': cls_item.lesson,
        'grade': cls_item.grade,
        'description': cls_item.description
    }
    update_class = my_class.update(class_vals)
    session.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content={'status': 'ok'})


@router.delete('/delete/class/{class_id}')
async def delete_class(session: sessionDep, user_types: Annotated[get_teacher, Depends()],
                       class_id: Annotated[int, Path()]):
    session.query(StudentClass).filter(StudentClass.class_id == class_id).delete()
    selected_class = session.query(Class).filter(Class.id == class_id).first()
    session.query(Exam).filter(Exam.class_id == class_id).delete()
    session.delete(selected_class)
    session.commit()
    return JSONResponse(content={'status': 'deleted'}, status_code=status.HTTP_200_OK)
