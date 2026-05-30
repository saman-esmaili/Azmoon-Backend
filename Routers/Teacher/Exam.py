from datetime import date, time
from typing import Annotated, Optional, List, ClassVar
from pydantic import BaseModel
from sqlalchemy import func, case, select
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Database.DB import sessionDep, ORDER, Class, Exam, QuestionExam, Question, TestQuestion, \
    TrueAnswerQuestion, StudentExam
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
    question_number: int = Field(gt=0)
    order_type: ORDER = Field(default=ORDER.ordered)
    description: Optional[str] = Field(None, min_length=4, max_length=200)
    score: int = Field()
    class_id: int


@router.get('/exam/add')
async def add_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep):
    teacher_id = (user_types['teacher']).decode('utf-8')
    cls = session.query(Class).filter(Class.teacher_id == teacher_id).with_entities(Class.id, Class.name)
    res = {c.id: c.name for c in cls}
    return JSONResponse({'classes': res},status_code=status.HTTP_201_CREATED)


@router.post('/exam/add')
async def add_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                   items: Annotated[ExamItem, Body()]):
    exam = Exam(
        name=items.name,
        question_number=items.question_number,
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
        dic = {'exam_id': exm.id, 'exam_name': exm.name, 'class_name': cls.name,
               'question_number': exm.question_number, 'exam_date': exm.exam_date, 'exam_time': exm.exam_time,
               'exam_start': exm.start_time, 'question_selected': 0}
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


@router.put('/exam/edit/{exam_id}')
async def edit_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                    items: Annotated[ExamItem, Body()], exam_id: Annotated[int, Path()]):
    selected_exam = session.query(Exam).filter(Exam.id == exam_id)
    exam_val = {
        'name': items.name,
        'question_number': items.question_number,
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


@router.delete('/exam/delete/{exam_id}')
async def delete_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                      exam_id: Annotated[int, Path()]):
    selected_exam = session.query(Exam).filter(Exam.id == exam_id).first()
    selected_question_exam = session.query(QuestionExam).filter(QuestionExam.id == exam_id).delete()
    session.delete(selected_exam)
    session.commit()
    return JSONResponse({'status': 'exam deleted'}, status_code=status.HTTP_200_OK)


class QuestionExamItem(BaseModel):
    question_id: List[int]

@router.post('/exam/question/add/{exam_id}')
async def add_question_exam(user_types: Annotated[get_teacher, Depends()], session: sessionDep,
                            exam_id: Annotated[int, Path()], items: Annotated[QuestionExamItem, Body()]):
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
        TrueFalseQuestion,
        func.coalesce(sub_query.c.is_selected, False).label('selected')
    )
                            .filter(Question.teacher_id == teacher_id)
                            .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                            .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                            .outerjoin(TrueFalseQuestion, TrueFalseQuestion.question_id == Question.id)
                            .join(sub_query, Question.id == sub_query.c.question_id, isouter=True)
                            )

    result = []
    ids = set()
    for q, tq, eq, tfq,selected in selected_items_query:
        dic_res = {'id': q.id, 'question': q.question, 'score': q.score, 'category': q.category,
                   'difficulty': q.difficulty, 'selected': selected}
        if tq:
            dic_res.update({'A': tq.A, 'B': tq.B, 'C': tq.C, 'D': tq.D, 'true_answer': tq.true_answer})
        elif eq:
            dic_res.update({'true_answer': eq.true_answer})
        elif tfq:
            dic_res.update({'true_answer': tfq.true_answer})
        result.append(dic_res)
        ids.add(q.id)
    return JSONResponse({'questions': result},status.HTTP_200_OK)



# @router.get('/exam/correction/{student_id}/{exam_id}')
# async def get_exam_correction(session:sessionDep,exam_id:Annotated[int,Path()],student_id:Annotated[int,Path()],user_types: Annotated[get_teacher, Depends()]):
#     teacher_id = (user_types['teacher']).decode('utf-8')
#     get_essay_question = session.execute(select(
#         QuestionExam,Question,TrueAnswerQuestion
#     ).where(QuestionExam.exam_id==exam_id))