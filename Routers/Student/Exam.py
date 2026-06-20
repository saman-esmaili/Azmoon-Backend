import datetime
from math import ceil
from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Path, Body, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, Case, exists, distinct
from sqlalchemy.sql.functions import coalesce
from starlette import status
from starlette.responses import JSONResponse
from Dependencies.Calculate import calc_exam_status, calc_time
from Database.DB import sessionDep, StudentClass, Class, Exam, StudentExam, StudentScore, Student, QuestionExam, \
    Question, TestQuestion, ORDER, ControlExam, EssayQuestion
from Dependencies.Redis import r
from Routers.Student.Authentication import get_student
from task.tasks import grade_exam

router = APIRouter(prefix='/student/exam')


@router.get('')
async def get_exams(session: sessionDep, user_type: Annotated[get_student, Depends()], page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100),):
    student_id = (user_type['student']).decode('utf-8')

    mean_score = select(
        StudentScore.student_id.label('student_id'),
        func.avg(coalesce(
            Case((StudentScore.exam_id == Exam.id, StudentScore.score), else_=0),
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
        func.count(Case((Student.id == StudentExam.student_id, StudentExam.student_id), else_=0), distinct=True).label(
            'passed_exam_count')
    ).group_by(StudentExam.student_id).subquery()

    info_exam = (session.query(StudentClass, Class, mean_score.c.mean_score, exam_count.c.exam_count,
                               passed_exam.c.passed_exam_count)
                 .filter(StudentClass.student_id == student_id)
                 .outerjoin(Class, Class.id == StudentClass.class_id)
                 .outerjoin(mean_score, mean_score.c.student_id == student_id)
                 .outerjoin(exam_count, exam_count.c.class_id == Class.id)
                 .outerjoin(passed_exam, passed_exam.c.student_id == student_id)
                 )
    class_query = session.query(StudentClass).filter(StudentClass.student_id == student_id).distinct(
        StudentClass.class_id).all()
    classes = [c.class_id for c in class_query]
    query = (session.query(Exam, Class, StudentScore)
            .filter(Exam.class_id.in_(classes))
            .outerjoin(Class, Class.id == Exam.class_id)
            .outerjoin(StudentScore, (StudentScore.student_id == student_id) & (StudentScore.exam_id == Exam.id))
            .distinct(Exam.id)
            )
    total = query.count()
    exam = (
        query
        .order_by(Exam.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    result = {'header': {}, 'exams': []}
    for sc, cls, mean_sc, exam_cnt, passed_exm in info_exam:
        result['header']['avg_score'] = mean_sc or 0
        # result['header']['exams'] = exam_cnt or 0
        # result['header']['passed_exam'] = passed_exm or 0
        # result['header']['remain'] = (exam_cnt or 0) - (passed_exm or 0)
    for exm, cls, student_score in exam:
        if not student_score:
            score = '-'
        else:
            score = student_score.score
        get_status = calc_exam_status(exm.exam_date, exm.exam_time, exm.start_time)
        dic_res = {'exam_id': exm.id, 'exam_name': exm.name, 'exam_date': str(exm.exam_date),
                   'exam_time': exm.exam_time,
                   'start_time': str(exm.start_time), 'exam_score': exm.score, 'status': get_status,
                   'class_name': cls.name, 'score': score}
        result['exams'].append(dic_res)

    return JSONResponse({'exam': result,'pages': ceil(total / size) if total else 1}, status.HTTP_200_OK)


@router.get('/score/{exam_id}')
async def get_score(session: sessionDep, user_type: Annotated[get_student, Depends()], exam_id: Annotated[int, Path()]):
    student_id = (user_type['student']).decode('utf-8')

    score_query = (session.query(StudentScore, Exam)
                   .filter(StudentScore.exam_id == exam_id,
                           StudentScore.student_id == student_id)
                   .outerjoin(Exam, Exam.id == StudentScore.exam_id)
                   )
    result = {}
    for score, exam in score_query:
        if score:
            result['true'] = score.trues
            result['false'] = score.falses
            result['not_answered'] = score.not_answered
            result['score'] = score.score
        result['exam_score'] = exam.score

    return JSONResponse({'exam_score': result}, status.HTTP_200_OK)


@router.get('/review/{exam_id}')
async def get_review(session: sessionDep, user_type: Annotated[get_student, Depends()],
                     exam_id: Annotated[int, Path()]):
    student_id = (user_type['student']).decode('utf-8')
    # is_exist_score = session.query(StudentScore).filter(StudentScore.exam_id==exam_id,StudentScore.student_id==student_id).first()
    result = []
    # if is_exist_score:
    question_exam = (session.query(StudentScore, QuestionExam, Question, StudentExam, TestQuestion, EssayQuestion)
                     .filter(StudentScore.exam_id == exam_id, StudentScore.student_id == student_id)
                     .join(QuestionExam, StudentScore.exam_id == QuestionExam.exam_id)
                     .join(Question, Question.id == QuestionExam.question_id)
                     .join(StudentExam, StudentExam.question_exam_id == QuestionExam.id)
                     .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                     .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                     )

    for std_sc, qe, question, std_exm, test_question, essay_question in question_exam:
        essay_correct = 0
        dic_res = {'question': question.question, 'q_image': question.image, 'student_answer': std_exm.answer,
                   'true_answer': question.true_answer, 'type': question.type}
        if test_question:
            dic_res.update({'A': test_question.A, 'A_image': test_question.A_image, 'B': test_question.B,
                            'B_image': test_question.B_image,
                            'C': test_question.C, 'C_image': test_question.C_image, 'D': test_question.D,
                            'D_image': test_question.D_image})
        elif essay_question:
            if 0 < std_sc.score < question.score:
                essay_correct = 1
            elif std_sc.score == question.score:
                essay_correct = 2
            dic_res.update({'essay_image': essay_question.essay_image, 'essay_correct': essay_correct})
        result.append(dic_res)

    return JSONResponse({'exam_score': result})


# start exam
async def create_exam(session, exam_id, student_id):
    exists_question = (session.query(exists()
                                     .where(QuestionExam.exam_id == exam_id)
                                     .where(StudentExam.question_exam_id == QuestionExam.id)
                                     )).scalar()
    is_first = False
    if not exists_question:
        is_first = True
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

    get_question = (session.query(QuestionExam, StudentExam)
                    .filter(QuestionExam.exam_id == exam_id)
                    .join(StudentExam, StudentExam.question_exam_id == QuestionExam.id)
                    .order_by(StudentExam.id.asc())
                    .all()
                    )

    result = {}
    for index, (qe, se) in enumerate(get_question):
        result[index + 1] = [qe.question_id, qe.id, se.answer]

    return result, is_first


@router.post('/get-permission/{exam_id}')
async def check_permission(session: sessionDep, user_type: Annotated[get_student, Depends()],
                           exam_id: Annotated[int, Path()]):
    student_id = (user_type['student']).decode('utf-8')
    exam = session.query(Exam).filter(Exam.id == exam_id).first()
    exam_status = calc_exam_status(exam.exam_date, exam.exam_time, exam.start_time)
    if exam_status != 'درحال برگزاری':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    duration, end_time = await calc_time(exam.start_time, exam.exam_time)
    if duration <= 0:
        duration = 1
    r.setex(f'{student_id}{exam_id}', duration * 60, str(end_time))
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

    return {'duration': duration}


async def show_question(session, question_id):
    questions = (session.query(QuestionExam, StudentExam, Question, TestQuestion)
                 # EssayQuestion
                 .filter(Question.id == question_id)
                 .join(Question, Question.id == QuestionExam.question_id)
                 .join(StudentExam, StudentExam.question_exam_id == QuestionExam.id)
                 .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                 # .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                 )
    dic_res = {}
    # eq
    for qe, se, q, tq in questions:
        dic_res = {'id': q.id, 'question': q.question, 'question_image': q.image, 'score': q.score,
                   'category': q.category, 'type': q.type}
        if tq:
            dic_res.update({'A': tq.A, 'A_image': tq.A_image, 'B': tq.B,
                            'B_image': tq.B_image,
                            'C': tq.C, 'C_image': tq.C_image, 'D': tq.D,
                            'D_image': tq.D_image})
        # elif eq:
        #     dic_res.update({'essay_image': eq.essay_image})

        dic_res.update({'answer': se.answer})

    return dic_res


@router.post('/start/{exam_id}')
async def start_exam(session: sessionDep, user_type: Annotated[get_student, Depends()],
                     exam_id: Annotated[int, Path()]):
    student_id = (user_type['student']).decode('utf-8')
    exam, clas = (session.query(Exam, Class)
                  .filter(Exam.id == exam_id)
                  .join(Class, Class.id == Exam.class_id)
                  ).first()

    duration = await check_permission(session, user_type, exam_id)
    questions, is_first = await create_exam(session, exam_id, student_id)
    question_id = questions.get(1)[0]
    get_question = await show_question(session, question_id)
    result = {}
    result['questions'] = questions
    result['show_question'] = get_question
    result['duration'] = duration['duration']
    result['topbar'] = {'exam_name': exam.name, 'class_name': clas.name}

    if is_first:
        grade_exam.apply_async(
            args=[student_id, exam_id],
            countdown=(result['duration'] + 1) * 60
        )
    return JSONResponse({'contents': result}, status.HTTP_200_OK)


async def question_registration(session, student_id, question_exam_id, answer):
    student_question = session.query(StudentExam).filter(StudentExam.student_id == student_id,
                                                         StudentExam.question_exam_id == question_exam_id)
    val = {
        'answer': answer,
        'visited': True,
        'student_id': student_id,
        'question_exam_id': question_exam_id
    }
    updated = student_question.update(val)
    session.commit()


class QuestionSelected(BaseModel):
    question_id: int = Field(ge=1)
    question_exam_id: int
    question_answer: Optional[str]


@router.post('/question-move/{exam_id}')
async def move(session: sessionDep, user_type: Annotated[get_student, Depends()], exam_id: Annotated[int, Path()],
               item: Annotated[QuestionSelected, Body()]):
    student_id = (user_type['student']).decode('utf-8')
    await question_registration(session, student_id, item.question_exam_id, item.question_answer)
    get_question = await show_question(session, item.question_id)
    end_time_exam = (r.get(f'{student_id}{exam_id}')).decode()
    end_time_exam = datetime.datetime.fromisoformat(end_time_exam)
    now = datetime.datetime.now()
    res_time = end_time_exam - now

    if res_time.total_seconds() < 0:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT)

    return JSONResponse({'show_question': get_question}, status_code=status.HTTP_200_OK)


class EndExamItem(BaseModel):
    question_exam_id: int
    question_answer: Optional[str]


@router.post('/end/{exam_id}')
async def end_exam(session: sessionDep, user_type: Annotated[get_student, Depends()], exam_id: Annotated[int, Path()],
                   item: Annotated[EndExamItem, Body()]):
    student_id = (user_type['student']).decode('utf-8')
    await question_registration(session, student_id, item.question_exam_id, item.question_answer)
    control_exam = session.query(ControlExam).filter(ControlExam.student_id == student_id,
                                                     ControlExam.exam_id == exam_id).first()
    control_exam.number_exit = 5
    session.commit()
    return JSONResponse({'exam_state': 'end'}, status.HTTP_200_OK)
