import datetime
from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, func, Case, exists
from sqlalchemy.sql.functions import coalesce
from starlette import status
from starlette.responses import JSONResponse
from Dependencies.Calculate import calc_exam_status, calc_time
from Database.DB import sessionDep, StudentClass, Class, Exam, StudentExam, StudentScore, Student, QuestionExam, \
    Question, TestQuestion, ORDER, ControlExam
from Dependencies.Redis import r
from Routers.Student.Authentication import get_student
from task.tasks import grade_exam

router = APIRouter(prefix='/student/exam')

@router.get('')
async def get_exams(session:sessionDep,user_type:Annotated[get_student,Depends()]):
    student_id = (user_type['student']).decode('utf-8')

    mean_score = select(
        StudentScore.student_id.label('student_id'),
        func.avg(coalesce(
            Case((StudentScore.exam_id==Exam.id,StudentScore.score),else_=0),
            0
        )).label('mean_score')
    ).group_by(StudentScore.student_id).subquery()

    exam_count = (
        select(
            Class.id.label("class_id"),
            func.count(Exam.id).label("exam_count")
        )
        .join(Exam, Class.id == Exam.class_id)
        .group_by(Class.id)
        .subquery()
    )

    passed_exam = select(
        StudentExam.student_id.label('student_id'),
        func.count(Case((Student.id==StudentExam.student_id,StudentExam.student_id),else_=0),distinct=True).label('passed_exam_count')
    ).group_by(StudentExam.student_id).subquery()

    info_exam = (session.query(StudentClass,Class,mean_score.c.mean_score,exam_count.c.exam_count,passed_exam.c.passed_exam_count)
            .filter(StudentClass.student_id==student_id)
            .outerjoin(Class, Class.id == StudentClass.class_id)
            .outerjoin(mean_score,mean_score.c.student_id==student_id)
            .outerjoin(exam_count,exam_count.c.class_id==Class.id)
            .outerjoin(passed_exam,passed_exam.c.student_id==student_id)
            )

    exam = (session.query(StudentClass,Class,Exam,StudentScore)
            .filter(StudentClass.student_id==student_id)
            .outerjoin(Class,Class.id==StudentClass.class_id)
            .outerjoin(Exam,Exam.class_id==Class.id)
            .outerjoin(StudentScore, StudentScore.student_id == student_id)
            )
    result = {'header':{},'exams':[]}
    for sc,cls,mean_sc,exam_cnt,passed_exm in info_exam:
        result['header']['avg_score'] = mean_sc or 0
        result['header']['exams'] = exam_cnt or 0
        result['header']['passed_exam'] = passed_exm or 0
        result['header']['remain'] = (exam_cnt or 0)-(passed_exm or 0)

    for student_class,cls,exm,student_score in exam:
        if not student_score:
            score = '-'
        else:
            score = student_score.score
        get_status = calc_exam_status(exm.exam_date,exm.exam_time,exm.start_time)
        dic_res = {'exam_id':exm.id,'exam_name':exm.name,'exam_date':str(exm.exam_date),'exam_time':exm.exam_time,
                   'start_time':str(exm.start_time),'question_number':exm.question_number,'class_name':cls.name,
                   'status':get_status,'score':score}
        result['exams'].append(dic_res)

    return JSONResponse({'exam':result},status.HTTP_200_OK)


@router.get('/score/{exam_id}')
async def get_score(session:sessionDep,user_type:Annotated[get_student,Depends()],exam_id:Annotated[int,Path()]):
    student_id = (user_type['student']).decode('utf-8')

    score_query = session.query(StudentScore).filter(StudentScore.exam_id==exam_id,StudentScore.student_id==student_id)

    score = score_query.one()
    result = {}
    result['true'] = score.trues
    result['false'] = score.falses
    result['not_answered'] = score.not_answered
    result['score'] = score.score

    return JSONResponse({'exam_score':result},status.HTTP_200_OK)



@router.get('/review/{exam_id}')
async def get_score(session:sessionDep,user_type:Annotated[get_student,Depends()],exam_id:Annotated[int,Path()]):
    student_id = (user_type['student']).decode('utf-8')
    # is_exist_score = session.query(StudentScore).filter(StudentScore.exam_id==exam_id,StudentScore.student_id==student_id).first()
    result = []
    # if is_exist_score:
    question_exam = (session.query(StudentScore,QuestionExam,Question,StudentExam,TestQuestion,TrueFalseQuestion,EssayQuestion)
                     .filter(StudentScore.exam_id==exam_id)
                     .join(QuestionExam, StudentScore.exam_id == QuestionExam.exam_id)
                     .join(Question,Question.id==QuestionExam.question_id)
                     .join(StudentExam,StudentExam.question_id==Question.id)
                     .outerjoin(TestQuestion,TestQuestion.question_id==Question.id)
                     .outerjoin(TrueFalseQuestion,TrueFalseQuestion.question_id==Question.id)
                     .outerjoin(EssayQuestion,EssayQuestion.question_id==Question.id)
                     )
    for std_sc,qe,question,std_exm,test_question,tf_question,essay_question in question_exam:
        dic_res = {'question':question.question,'q_image':question.image,'student_answer':std_exm.answer}
        if test_question:
            dic_res.update({'A':test_question.A,'A_image':test_question.A_image,'B':test_question.B,'B_image':test_question.B_image,
                            'C':test_question.C,'C_image':test_question.C_image,'D':test_question.D,'D_image':test_question.D_image,'true_answer':test_question.true_answer})
        elif tf_question:
            dic_res.update({'true_answer':tf_question.true_answer})
        else:
            dic_res.update({'true_answer': essay_question.true_answer})

    return JSONResponse({'exam_score':result})



# start exam
async def create_exam(session,exam_id,student_id):
    exists_question = (session.query(exists()
        .where(QuestionExam.exam_id == exam_id)
        .where(StudentExam.question_exam_id==QuestionExam.id)
    )).scalar()

    if not exists_question:
        exam_order_type = session.query(Exam).filter(Exam.id == exam_id).first().order_type
        query_question_exam = session.query(QuestionExam).filter(QuestionExam.exam_id == exam_id)
        if exam_order_type == ORDER.ordered:
            get_question_exam = query_question_exam.order_by(QuestionExam.id.asc()).all()
        else:
            get_question_exam = query_question_exam.order_by(func.random()).all()

        student_exam = [StudentExam(
            visited=False,
            student_id=student_id,
            question_exam_id=q.id
        ) for q in get_question_exam
        ]
        session.add_all(student_exam)
        session.commit()

    get_question = (session.query(QuestionExam,StudentExam)
                       .filter(QuestionExam.exam_id==exam_id)
                       .join(StudentExam,StudentExam.question_exam_id==QuestionExam.id)
                       .all()
                       )

    result = {}
    for index, (qe, se) in enumerate(get_question):
        result[index + 1] = [qe.question_id,qe.id]

    return result



@router.post('/get-permission/{exam_id}')
async def check_permission(session:sessionDep,user_type:Annotated[get_student,Depends()],exam_id:Annotated[int,Path()]):
    student_id = (user_type['student']).decode('utf-8')
    exam = session.query(Exam).filter(Exam.id == exam_id).first()
    duration,end_time = await calc_time(exam.start_time, exam.exam_time)
    r.setex(f'{student_id}{exam_id}',duration,end_time)
    control_exam = session.query(ControlExam).filter(ControlExam.student_id == student_id,
                                                      ControlExam.exam_id == exam_id).first()
    if control_exam:
        if control_exam.number_exit > 4:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        else:
            control_exam.number_exit += 1
            session.commit()

    else:
        control_exam = ControlExam(
            enter_time=datetime.datetime.now().time(),
            number_exit=0,
            student_id=student_id,
            exam_id=exam_id
        )
        session.add(control_exam)
        session.commit()
        session.refresh(control_exam)

    exam_status = calc_exam_status(exam.exam_date,exam.exam_time,exam.start_time)
    if status != 'درحال برگزاری':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return {'duration':duration}



async def show_question(session,question_id):
    questions = (session.query(QuestionExam,StudentExam,Question, TestQuestion, EssayQuestion, TrueFalseQuestion)
                 .filter(Question.id == question_id)
                 .join(Question,Question.id==QuestionExam.question_id)
                 .join(StudentExam,StudentExam.question_exam_id==QuestionExam.id)
                 .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                 .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                 .outerjoin(TrueFalseQuestion, TrueFalseQuestion.question_id == Question.id)
                 )
    dic_res = {}
    for qe,se,q, tq, eq, tfq in questions:
        dic_res = {'id': q.id, 'question': q.question,'question_image': q.image, 'score': q.score, 'category': q.category,'type': q.type}
        if tq:
            dic_res.update({'A': tq.A, 'A_image': tq.A_image, 'B': tq.B,
                            'B_image': tq.B_image,
                            'C': tq.C, 'C_image': tq.C_image, 'D': tq.D,
                            'D_image': tq.D_image})

        dic_res.update({'answer':se.answer})

    return dic_res


@router.post('/start/{exam_id}')
async def start_exam(session:sessionDep,user_type:Annotated[get_student,Depends()],exam_id:Annotated[int,Path()]):
    student_id = (user_type['student']).decode('utf-8')
    duration = await check_permission(session,user_type, exam_id)
    questions = await create_exam(session, exam_id, student_id)
    question_id = questions.get(1)
    get_question = await show_question(session, question_id)
    result = {}
    result['questions'] = questions
    result['show_question'] = get_question
    result['duration'] = duration['duration']
    grade_exam.apply_async(
        args=[session,student_id,exam_id],
        countdown=(duration['duration']+5)*60
    )
    return JSONResponse({'contents':result},status.HTTP_200_OK)

async def question_registration(session,student_id,question_exam_id,answer):
    student_question = session.query(StudentExam).filter(StudentExam.student_id==student_id,StudentExam.question_exam_id==question_exam_id).first()
    val = {
        'answer':answer,
        'visited':True,
        'student_id':student_id,
        'question_exam_id':question_exam_id
    }
    updated = student_question.update(val)
    session.commit()


class QuestionSelected(BaseModel):
    question_id: int = Field(ge=1)
    question_exam_id: int
    question_answer: Optional[str]

@router.post('/question-move/{exam_id}')
async def move(session:sessionDep,user_type:Annotated[get_student,Depends()],exam_id:Annotated[int,Path()],item:Annotated[QuestionSelected,Body()]):
    student_id = (user_type['student']).decode('utf-8')
    await question_registration(session,student_id,item.question_exam_id,item.question_answer)
    get_question = await show_question(session, item.question_id)
    end_time_exam = (r.get(f'{student_id}{exam_id}')).decode()
    now = datetime.datetime.now()
    res_time = end_time_exam-now
    if res_time < 0:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)

    return JSONResponse({'show_question':get_question},status_code=status.HTTP_200_OK)

class EndExamItem(BaseModel):
    question_exam_id: int
    question_answer: Optional[str]

@router.post('/end/{exam_id}')
async def end_exam(session:sessionDep,user_type:Annotated[get_student,Depends()],exam_id:Annotated[int,Path()],item:Annotated[EndExamItem,Body()]):
    student_id = (user_type['student']).decode('utf-8')
    await question_registration(session, student_id, item.question_exam_id, item.question_answer)
    control_exam = session.query(ControlExam).filter(ControlExam.student_id==student_id,ControlExam.exam_id==exam_id)
    control_exam.number_exit = 5
    session.commit()
    return JSONResponse({'exam_state':'end'},status.HTTP_200_OK)



