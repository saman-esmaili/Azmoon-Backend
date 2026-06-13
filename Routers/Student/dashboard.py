import datetime
from typing import Annotated
from fastapi.params import Depends
from sqlalchemy import func, Case, select, DateTime, or_, and_
from sqlalchemy.sql.functions import coalesce
from starlette.responses import JSONResponse

from Routers.Student.Authentication import get_student
from fastapi import APIRouter
from Database.DB import sessionDep, StudentClass, Student, User, Exam, Class, StudentScore, StudentExam

router = APIRouter(prefix='/student')

@router.get('/dashboard')
async def student_dashboard(session:sessionDep,get_type:Annotated[get_student,Depends()]):
    student_id = (get_type['student']).decode('utf-8')
    res = {
        'exam_name0': None,
        'student_score0': 0,
        'exam_score0': 0,
        'exam_name1': None,
        'student_score1': 0,
        'exam_score1': 0,
        'user_name': '',
        'remain_exam': 0,
        'exams': 0,
        'exam_count': 0,
        'passed_exam': 0,
        'class_count': 0,
        'avg_score': 0,
        'max_score': 0,
        'messages': 0,
    }
    exam_count = (
        select(
            Class.id.label("class_id"),
            func.count(Exam.id).label("exam_count")
        )
        .join(Exam, Class.id == Exam.class_id)
        .group_by(Class.id)
        .subquery()
    )

    class_count = select(
        StudentClass.id.label('StudentClass_id'),
        func.count(StudentClass.class_id).label('class_count')
    ).group_by(StudentClass.id).subquery()

    mean_score = select(
        StudentScore.student_id.label('student_id'),
        func.avg(coalesce(
            Case((StudentScore.exam_id==Exam.id,StudentScore.score),else_=0),
            0
        )).label('mean_score')
    ).group_by(StudentScore.student_id).subquery()

    max_score = select(
        StudentScore.student_id.label('student_id'),
        func.max(StudentScore.score).label('max_score')
    ).group_by(StudentScore.student_id).subquery()

    passed_exam = select(
        StudentExam.student_id.label('student_id'),
        func.count(Case((Student.id==StudentExam.student_id,StudentExam.student_id),else_=0),distinct=True).label('passed_exam_count')
    ).group_by(StudentExam.student_id).subquery()

    last_two_exam_score = (session.query(StudentScore,Exam)
                           .filter(StudentScore.student_id==student_id)
                           .join(Exam,Exam.id==StudentScore.exam_id)
                           ).order_by('date_score').limit(2)

    student_info = (session.query(StudentClass,Student,Class,User,exam_count.c.exam_count,class_count.c.class_count,
                                  mean_score.c.mean_score,max_score.c.max_score,passed_exam.c.passed_exam_count)
                    .filter(StudentClass.student_id==student_id)
                    .join(Class, StudentClass.class_id == Class.id)
                    .join(Student,StudentClass.student_id==student_id)
                    .join(User,User.id==Student.user_id)
                    .outerjoin(exam_count,exam_count.c.class_id==Class.id)
                    .outerjoin(class_count,class_count.c.StudentClass_id==StudentClass.id)
                    .outerjoin(mean_score,mean_score.c.student_id==Student.id)
                    .outerjoin(max_score,max_score.c.student_id==Student.id)
                    .outerjoin(passed_exam,passed_exam.c.student_id==Student.id)
                    )
    last_two_results = last_two_exam_score.all()
    for index,(score,exm) in enumerate(last_two_results):
        res[f'exam_name{index}'] = exm.name
        res[f'student_score{index}'] = exm.score
        res[f'exam_score{index}'] = score.score

    for student_cls,student,clas,user,exam_cnt,class_cnt,avg_score,maxscore,passed_exam_c in student_info:
        res['user_name'] = f'{user.name} {user.last_name}'
        res['remain_exam'] = (exam_cnt or 0)-(passed_exam_c or 0)
        res['exams'] = exam_cnt or 0
        res['exam_count'] = exam_cnt or 0
        res['passed_exam'] = passed_exam_c or 0
        res['class_count'] = class_cnt or 0
        res['avg_score'] = avg_score or 0
        res['max_score'] = maxscore or 0
        res['messages'] = 0

    return JSONResponse(content={'student_dash':res})
