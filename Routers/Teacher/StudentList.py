from math import ceil
from typing import Annotated
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Query, Path
from sqlalchemy import select, func, or_
from starlette import status
from starlette.responses import JSONResponse

from Database.DB import sessionDep, Class, Student, StudentClass, User, StudentScore, Exam, Teacher
from Routers.Teacher.TeacherAuthentication import get_teacher

router = APIRouter(prefix='/teacher')


@router.get('/students')
async def get_student(session: sessionDep, user_types: Annotated[get_teacher, Depends()], page: int = Query(1, ge=1),
                      size: int = Query(10, ge=1, le=100), search: str = Query()):
    teacher_id = (user_types['teacher']).decode('utf-8')
    mean_score = select(
        StudentScore.student_id.label('student_score_id'),
        func.avg(StudentScore.score).label('mean_score')
    ).group_by(StudentScore.student_id).subquery()

    query = (session.query(StudentClass, Class, Student, User, Exam, mean_score.c.mean_score)
             .join(Class, Class.id == StudentClass.class_id)
             .filter(Class.teacher_id == teacher_id)
             .join(Student, Student.id == StudentClass.student_id)
             .join(User, User.id == Student.user_id)
             .outerjoin(Exam, Exam.class_id == Class.id)
             .outerjoin(mean_score, mean_score.c.student_score_id == StudentClass.student_id)
             )
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Class.name.contains(search_term),
                User.name.contains(search_term),
                User.last_name.contains(search_term),
                User.mobile.contains(search_term),
                (User.name + ' ' + User.last_name).contains(search_term),
            )
        )

    total = query.count()
    students = (
        query
        .order_by(StudentClass.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    result = []
    for sc, c, s, u, e, mean in students:
        exam_score = None
        if e:
            exam_score = e.score
        dic_res = {'student_class_id': sc.id, 'student_id': s.id,'student_email':u.email, 'student_name': u.name,
                   'student_last_name': u.last_name,
                   'student_mobile': u.mobile,'class_id':c.id, 'class_name': c.name, 'mean_score': mean, 'total_score': exam_score}
        result.append(dic_res)
    return JSONResponse({'students': result, 'pages': ceil(total / size) if total else 1, })


@router.delete('/student/{student_class_id}')
async def remove_student(session: sessionDep, user_types: Annotated[get_teacher, Depends()],
                         student_class_id: Annotated[int, Path()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected = session.query(StudentClass).filter(StudentClass.id==student_class_id)
    if selected:
        selected.delete()


@router.get('/student/score/{student_id}/{class_id}')
async def get_score_detail(session: sessionDep, user_types: Annotated[get_teacher, Depends()],student_id: Annotated[int, Path()],class_id: Annotated[int, Path()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    query = (session.query(StudentScore,Exam,Class)
             .join(Exam,Exam.id==StudentScore.exam_id)
             .join(Class,Class.id==Exam.class_id)
             .filter(StudentScore.student_id==student_id,
                     Class.teacher_id==teacher_id,
                     Class.id==class_id)
             )
    max_score = -100
    result = []
    for sc,e,c in query:
        if sc.score > max_score:
            max_score = sc.max_score
        result.append({'student_score':sc.score,'exam_score':e.score,'date':e.date,'exam':e.name})
    return JSONResponse({'scores':result,'maxScore':max_score})
