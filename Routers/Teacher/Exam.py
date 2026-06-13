from datetime import date, time, datetime
from typing import Annotated, Optional, List, ClassVar
from pydantic import BaseModel
from sqlalchemy import func, case, select, delete
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Database.DB import sessionDep, ORDER, Class, Exam, QuestionExam, Question, TestQuestion, \
    TrueAnswerQuestion, StudentExam, EssayQuestion, Student, User, StudentScore
from fastapi.params import Depends, Body, Path
from Dependencies.Calculate import calc_exam_status
from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix='/teacher')


class ExamItem(BaseModel):
    name: str = Field(min_length=4, max_length=25)
    exam_date: str = Field()
    start_time: time = Field()
    exam_time: int = Field()
    # question_number: int = Field(gt=0)
    order_type: ORDER = Field(default=ORDER.ordered)
    description: Optional[str] = Field(None, min_length=4, max_length=200)
    score: int = Field()
    class_id: int


@router.get('/exam/add')
async def add_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep):
    teacher_id = (user_types['teacher']).decode('utf-8')
    cls = session.query(Class).filter(Class.teacher_id == teacher_id).with_entities(Class.id, Class.name)
    res = [{'id':c.id, 'name':c.name} for c in cls]
    return JSONResponse({'classes': res},status_code=status.HTTP_200_OK)


@router.post('/exam/add')
async def add_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                   items: Annotated[ExamItem, Body()]):
    exam = Exam(
        name=items.name,
        exam_date=items.exam_date,
        exam_time=items.exam_time,
        start_time=items.start_time,
        description=items.description,
        score=items.score,
        order_type=items.order_type,
        class_id=items.class_id,
    )
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return JSONResponse({'status': 'exam added'}, status_code=status.HTTP_201_CREATED)


@router.get('/exam')
async def get_exam(session: sessionDep, user_types: Annotated[get_teacher, Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    exams = (session.query(Exam, Class).filter(Class.teacher_id == teacher_id)
             .outerjoin(Class, Exam.class_id == Class.id)
             )
    result = []
    ids = set()
    for exm, cls in exams:
        dic = {'exam_id': exm.id, 'exam_name': exm.name, 'class_name': cls.name,'class_id': cls.id,
               'exam_date': exm.exam_date, 'exam_time': str(exm.exam_time),'score':exm.score,
               'order_type': exm.order_type,'description':exm.description,
               'exam_start': str(exm.start_time), 'question_selected': 0}
        exam_status = calc_exam_status(exm.exam_date, exm.exam_time, exm.start_time)
        dic.update({'exam_status': exam_status})
        ids.add(exm.id)
        result.append(dic)
    count = session.query(
        QuestionExam.exam_id,
        func.count(QuestionExam.id).label('count')
    ).filter(
        QuestionExam.exam_id.in_(ids)
    ).group_by(
        QuestionExam.exam_id
    ).all()
    for (exam_id, counter) in count:
        for dics in result:
            if exam_id == dics['exam_id']:
                dics['question_selected'] = counter
                break
    return JSONResponse({'exams': result},status.HTTP_200_OK)


@router.put('/exam/{exam_id}')
async def edit_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                    items: Annotated[ExamItem, Body()], exam_id: Annotated[int, Path()]):
    selected_exam = session.query(Exam).filter(Exam.id == exam_id)
    exam_val = {
        'name': items.name,
        'exam_date': items.exam_date,
        'exam_time': items.exam_time,
        'start_time': items.start_time,
        'description': items.description,
        'score': items.score,
        'order_type': items.order_type,
        'class_id': items.class_id
    }
    update_exam = selected_exam.update(exam_val)
    session.commit()
    return JSONResponse({'status': 'exam updated'}, status_code=status.HTTP_200_OK)


@router.delete('/exam/{exam_id}')
async def delete_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                      exam_id: Annotated[int, Path()]):
    selected_exam = session.query(Exam).filter(Exam.id == exam_id).first()
    selected_question_exam = session.query(QuestionExam).filter(QuestionExam.id == exam_id).delete()
    session.delete(selected_exam)
    session.commit()
    return JSONResponse({'status': 'exam deleted'}, status_code=status.HTTP_200_OK)


async def add_question_exam_diff(session,exam_id,q_ids):
    question_exam_list = [
        QuestionExam(
            exam_id=exam_id,
            question_id=q_id
        ) for q_id in q_ids
    ]
    session.add_all(question_exam_list)
    session.commit()

async def remove_question_exam_diff(session,exam_id,q_ids):
    session.execute(
        delete(QuestionExam).where(
            QuestionExam.exam_id==exam_id,
            QuestionExam.question_id.in_(q_ids)
        )
    )
    session.commit()

class QuestionExamItem(BaseModel):
    question_id: List[int]

@router.post('/exam/question/add/{exam_id}')
async def add_question_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                            exam_id: Annotated[int, Path()], items: Annotated[QuestionExamItem, Body()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    qe_list = (session.query(QuestionExam)
               .filter(QuestionExam.exam_id==exam_id)
               .with_entities(QuestionExam.question_id)
               )
    past_q = {q[0] for q in qe_list}
    set_question_id = set(items.question_id)
    if past_q:
        remove = past_q.difference(items.question_id)
        add = set_question_id.difference(past_q)
        if remove:
            await remove_question_exam_diff(session,exam_id,remove)
        if add:
            await add_question_exam_diff(session,exam_id,add)
    else:
        question_exam_list = [
            QuestionExam(
                exam_id=exam_id,
                question_id=q_id
            ) for q_id in items.question_id
        ]
        session.add_all(question_exam_list)
        session.commit()
    return JSONResponse({'status': 'Question Exam added'}, status_code=status.HTTP_201_CREATED)


@router.delete('/exam/question/delete/{exam_id}')
async def add_question_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                            exam_id: Annotated[int, Path()], items: Annotated[QuestionExamItem, Body()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected_questions = session.query(QuestionExam).filter(QuestionExam.exam_id == exam_id,
                                                            QuestionExam.question_id.in_(
                                                                items.question_id)).delete()
    session.commit()
    return JSONResponse({'status': 'Question Exam deleted'}, status_code=status.HTTP_200_OK)


@router.get('/exam/question/{exam_id}')
async def get_question_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                            exam_id: Annotated[int, Path()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    sub_query = session.query(
        QuestionExam.question_id,
        case(
            (QuestionExam.exam_id == exam_id, True),
            else_=False
        ).label('is_selected')
    ).subquery()

    selected_items_query = (session.query(
        Question,
        TestQuestion,
        EssayQuestion,
        func.coalesce(sub_query.c.is_selected, False).label('selected'),
    )
                            .filter(Question.teacher_id == teacher_id)
                            .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                            .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                            .join(sub_query, Question.id == sub_query.c.question_id, isouter=True)
                            )
    exm,cls = (session.query(Exam,Class).filter(Exam.id==exam_id)
            .join(Class,Class.id==Exam.class_id)
           ).first()
    exam_info = {'name':exm.name,'class':cls.name,'duration':exm.exam_time,
                  'score':exm.score}


    result = []
    ids = set()
    for q, tq, eq,selected in selected_items_query:
        dic_res = {'id': q.id, 'text': q.question,'question_image':q.image, 'score': q.score, 'cat': q.category,
                   'diff': q.difficulty, 'selected': selected,'true_answer': q.true_answer,'type':q.type}
        if tq:
            dic_res.update({'A': tq.A, 'B': tq.B, 'C': tq.C, 'D': tq.D,'A_image':tq.A_image,'B_image':tq.B_image,'C_image':tq.C_image,'D_image':tq.D_image })
        elif eq:
            dic_res.update({'essay_image':eq.essay_image})
        result.append(dic_res)
        ids.add(q.id)

    return JSONResponse({'questions': result,'exam_info':exam_info},status.HTTP_200_OK)


@router.get('/exam/students/{exam_id}')
async def get_student_exam(session:sessionDep,exam_id:Annotated[int,Path()],user_types: Annotated[get_teacher, Depends()]):
    get_question = (session.query(QuestionExam,Question,TestQuestion,EssayQuestion)
                    .filter(QuestionExam.exam_id==exam_id)
                    .outerjoin(Question,Question.id==QuestionExam.question_id)
                    .outerjoin(TestQuestion,TestQuestion.question_id==Question.id)
                    .outerjoin(EssayQuestion,EssayQuestion.question_id==Question.id)
                    )
    get_exam,get_class = (session.query(Exam,Class)
                .filter(Exam.id==exam_id)
                .join(Class,Class.id==Exam.class_id)
                ).first()
    get_students = (session.query(QuestionExam,StudentExam,Student,User)
                    .filter(QuestionExam.exam_id==exam_id)
                    .outerjoin(StudentExam,StudentExam.question_exam_id==QuestionExam.id)
                    .outerjoin(Student,Student.id==StudentExam.student_id)
                    .join(User,User.id==Student.user_id)
                    ).distinct(Student.id)
    questions = []
    for qe,q,tq,eq in get_question:
        dic = {'question_exam_id':qe.id,'id':q.id,'type':q.type,'text':q.question,'maxScore':q.score,
                          'question_image':q.image,'true_answer':q.true_answer}
        if tq:
            dic.update({'A':tq.A,'B':tq.B,'C':tq.C,'D':tq.D,'A_image':tq.A_image,'B_image':tq.B_image,'C_image':tq.C_image,'D_image':tq.D_image})
        elif eq:
            dic.update({'essay_image':eq.essay_image})
        questions.append(dic)

    exam = {'id':get_exam.id,'name':get_exam.name,'class':get_class.name,'date':get_exam.exam_date,'totalScore':get_exam.score}

    students = []
    for qe,se,s,u in get_students:
        dic = {'id':s.id,'name':f'{u.name} {u.last_name}'}
        students.append(dic)

    return JSONResponse(content={'questions':questions,'exam':exam,'students':students})

@router.get('/exam/answers/{exam_id}/{student_id}')
async def get_exam_correction(session:sessionDep,exam_id:Annotated[int,Path()],student_id:Annotated[int,Path()],user_types: Annotated[get_teacher, Depends()]):
    student_answer = (session.query(QuestionExam,StudentExam,Question)
                      .filter(QuestionExam.exam_id==exam_id)
                      .outerjoin(StudentExam,StudentExam.question_exam_id==QuestionExam.id)
                      .filter(StudentExam.student_id==student_id)
                      .outerjoin(Question,Question.id==QuestionExam.question_id)
                      )
    result = []
    for qe,se,q in student_answer:
        dic = {'value':se.answer,'qId':q.id,'qeId':qe.id}
        result.append(dic)
    return JSONResponse(content={'student_id':student_id,'student_answer':result})


class QuestionGrade(BaseModel):
    question_exam_id: int
    score: float
class QSTAT(BaseModel):
    correct:int
    wrong:int
    answered:int
    unanswered:int
class GradingInfo(BaseModel):
    student_id: int
    total_score: float
    questions: list[QuestionGrade]
    stats: QSTAT
@router.post('/exam/grade/{exam_id}')
async def grading(session:sessionDep,exam_id:Annotated[int,Path()],data:Annotated[GradingInfo,Body()],user_types: Annotated[get_teacher, Depends()]):
    if data.questions:
        for item in data.questions:
            session.query(StudentExam).filter(
                StudentExam.student_id == data.student_id,
                StudentExam.question_exam_id == item.question_exam_id
            ).update({
                "score": item.score
            })
        session.commit()

        student_score = session.query(StudentScore).filter(StudentScore.student_id==data.student_id,StudentScore.exam_id==exam_id).first()
        if not student_score:
            create_ss = StudentScore(
                student_id=data.student_id,
                exam_id=exam_id,
                score=data.total_score,
                date_score=datetime.now().date(),
                trues=data.stats.correct,
                falses=data.stats.wrong,
                not_answered=data.stats.unanswered
            )
            session.add(create_ss)
            session.commit()
            session.refresh(create_ss)
        else:
            student_score.score = data.total_score
            student_score.date_score = datetime.now().date()
            student_score.trues = data.stats.correct
            student_score.falses = data.stats.wrong
            student_score.not_answered = data.stats.unanswered

            session.commit()
    return JSONResponse({'grading':'done'})