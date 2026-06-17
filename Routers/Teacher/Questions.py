import datetime
import json
import math
import os
import shutil
import uuid
from pathlib import Path as pth
from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.params import Body, Depends, Path, Form, File, Query
from pydantic import BaseModel
from sqlalchemy import select, func, case, exists, or_, cast, String
import json
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Routers.Teacher.TeacherAuthentication import get_teacher
from Database.DB import sessionDep, QUE_TYPES, Difficulties, Question, TestQuestion, QuestionExam, Class, Exam, \
    EssayQuestion, UserPlan, Plan
from permissions.Teacher import plan_permit

router = APIRouter(prefix='/teacher/question')
IMAGE_FORMAT = ["jpeg", "jpg", "png", "webp"]


class QuestionItem(BaseModel):
    question: str = Field(None, max_length=350)
    type: QUE_TYPES = Field(default=QUE_TYPES.test)
    score: float = Field(gt=0)
    category: str = Field()
    difficulty: str = Field(default=Difficulties.easy)
    a: Optional[str] = Field(None)
    b: Optional[str] = Field(None)
    c: Optional[str] = Field(None)
    d: Optional[str] = Field(None)
    true_answer: Optional[str] = Field(None)


async def generate_image_name(teacher_id, old_name):
    image_name = old_name.split('.')
    image_format = image_name[-1]
    if image_format not in IMAGE_FORMAT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{timestamp}{teacher_id}_{uuid.uuid4()}"
    return f'{new_name}.{image_format}'


async def save_image(path, teacher_id,session, image: UploadFile):
    user_plan = session.query(UserPlan).filter(UserPlan.teacher_id==teacher_id,UserPlan.is_active==True).first()
    plan = session.query(Plan).filter(Plan.id==user_plan.plan_id).first()
    if 0 <= user_plan.image_count <= plan.image_number:
        new_name = await generate_image_name(teacher_id, image.filename)
        BASE_DIR = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
        file_path = f'{BASE_DIR}/{path}/{new_name}'
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(image.file, f)
        user_plan.image_count += 1
        return new_name
    raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE)


async def remove_image(session,teacher_id,image_name, path):
    user_plan = session.query(UserPlan).filter(UserPlan.teacher_id == teacher_id, UserPlan.is_active == True).first()
    BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
    file_path = pth(f'{BASE_DIR}/{path}/{image_name}')
    if file_path.exists():
        os.remove(file_path)
    if user_plan.image_count > 0:
        user_plan.image_count -= 1


@router.post('/add')
async def add_question(session: sessionDep, user_types: Annotated[get_teacher, Depends()],
                       question_data: Annotated[str, Form()],
                       question_image: Annotated[UploadFile | None, File()] = None,
                       A_image: Annotated[UploadFile | None, File()] = None,
                       B_image: Annotated[UploadFile | None, File()] = None,
                       C_image: Annotated[UploadFile | None, File()] = None,
                       D_image: Annotated[UploadFile | None, File()] = None,
                       essay_image: Annotated[UploadFile | None, File()] = None,
                       ):
    items = QuestionItem(**json.loads(question_data))
    teacher_id = (user_types['teacher']).decode('utf-8')
    has_permit = await plan_permit(teacher_id,session)
    if not has_permit:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED)
    if question_image:
        image_name = await save_image('Questions', teacher_id,session, question_image)
    else:
        image_name = None
    q = Question(
        question=items.question,
        type=items.type,
        score=items.score,
        category=items.category,
        difficulty=items.difficulty,
        teacher_id=teacher_id,
        question_date=datetime.datetime.now().date(),
        true_answer=items.true_answer,
        image=image_name
    )
    session.add(q)
    session.commit()
    session.refresh(q)
    q_id = q.id
    try:
        if items.type == QUE_TYPES.test:
            await add_test_question(session, teacher_id, q_id, items.a, items.b, items.c, items.d, A_image, B_image,
                                    C_image, D_image)
        elif items.type == QUE_TYPES.essay:
            await add_essay_question(session, teacher_id, q_id, essay_image)
    except:
        selected_question = session.query(Question).filter(Question.id == q_id)
        image = selected_question.first().image
        await remove_image(session,teacher_id,image, 'Questions')
        session.delete(selected_question)
        session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    return JSONResponse(content={'status': 'ok'}, status_code=status.HTTP_201_CREATED)


async def add_test_question(session, teacher_id, q_id, a, b, c, d, a_image, b_image, c_image, d_image):
    images = [a_image, b_image, c_image, d_image]
    names = ['A', 'B', 'C', 'D']
    dict = {}
    for name, img in zip(names, images):
        if img:
            image_name = await save_image('Questions', teacher_id,session, img)
        else:
            image_name = None
        dict[name] = image_name

    test_q = TestQuestion(
        A=a,
        B=b,
        C=c,
        D=d,
        question_id=q_id,
        A_image=dict['A'],
        B_image=dict['B'],
        C_image=dict['C'],
        D_image=dict['D']
    )
    session.add(test_q)
    session.commit()
    session.refresh(test_q)


async def add_essay_question(session, teacher_id, q_id, essay_image: UploadFile):
    if essay_image:
        image_name = await save_image('Questions', teacher_id,session ,essay_image)
    else:
        image_name = None
    essay_question = EssayQuestion(
        question_id=q_id,
        essay_image=image_name
    )
    session.add(essay_question)
    session.commit()
    session.refresh(essay_question)

@router.get('/header')
async def question_header(session: sessionDep, user_types: Annotated[get_teacher, Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    use_q = (
        session.query(
            func.count(QuestionExam.exam_id)
        )
        .join(Exam, Exam.id == QuestionExam.exam_id)
        .join(Class, Class.id == Exam.class_id)
        .filter(Class.teacher_id == teacher_id)
    )
    q = session.query(
        func.count(
            case((Question.type==QUE_TYPES.test,1))
        ).label('test_count'),
        func.count(
            case((Question.type == QUE_TYPES.essay, 1))
        ).label('essay_count'),
        func.count(
            case((Question.type == QUE_TYPES.true_false, 1))
        ).label('true_false_count'),
    ).filter(Question.teacher_id==teacher_id).first()
    header = {}
    header['test_count'] = q.test_count
    header['essay_count'] = q.essay_count
    header['true_false_count'] = q.true_false_count
    header['all'] = q.test_count+q.essay_count+q.true_false_count
    header['use_count'] = int(use_q.scalar() or 0)
    return JSONResponse({'questions_info': header},status_code=200)

@router.get('')
async def show_question(session: sessionDep, user_types: Annotated[get_teacher, Depends()], page : int = Query(1, ge=1), size: int = Query(5, ge=1, le=100),search: str = Query()):
    teacher_id = (user_types['teacher']).decode('utf-8')
    query = session.query(
        Question,
        TestQuestion,
        EssayQuestion
    ).filter(
        Question.teacher_id == teacher_id
    ).outerjoin(
        TestQuestion, TestQuestion.question_id == Question.id
    ).outerjoin(
        EssayQuestion, EssayQuestion.question_id == Question.id
    )
    dic = {
        'تشریحی':'essay',
        'تستی':'test',
        'صحیح غلط':'true_false',
    }
    if search in dic.keys():
        search = dic[search]
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Question.question.contains(search_term),
                cast(Question.type, String).ilike(search_term),
                Question.difficulty.contains(search_term),
            )
        )

    total = query.count()
    questions = (
        query
        .order_by(Question.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    result = []
    for q, tq, eq in questions:
        dic_res = {'id': q.id, 'text': q.question, 'score': float(q.score), 'cat': q.category,
                   'diff': q.difficulty, 'type': q.type, 'true_answer': q.true_answer, 'question_image': q.image}
        if tq:
            dic_res.update({'A': tq.A, 'B': tq.B, 'C': tq.C, 'D': tq.D, 'A_image': tq.A_image, 'B_image': tq.B_image,
                            'C_image': tq.C_image, 'D_image': tq.D_image})
        if eq:
            dic_res.update({'essay_image': eq.essay_image})
        result.append(dic_res)
    return JSONResponse(content={'questions': result,'pages':math.ceil(total/size)})


async def check_image(session,past_image_name, new_image_name, teacher_id):
    if not past_image_name and not new_image_name:
        return None
    elif past_image_name and not new_image_name:
        await remove_image(session,teacher_id,past_image_name, 'Questions')
        return None
    elif new_image_name and not past_image_name:
        new = await save_image('Questions', teacher_id,session, new_image_name)
        return new
    else:
        if new_image_name == past_image_name:
            return new_image_name
        else:
            await remove_image(session,teacher_id,past_image_name, 'Questions')
            new = await save_image('Questions', teacher_id,session, new_image_name)
            return new



class EditQuestionItem(BaseModel):
    question: str = Field(None, max_length=350)
    type: QUE_TYPES = Field(default=QUE_TYPES.test)
    score: float = Field(gt=0)
    category: str = Field()
    difficulty: str = Field(default=Difficulties.easy)
    a: Optional[str] = Field(None)
    b: Optional[str] = Field(None)
    c: Optional[str] = Field(None)
    d: Optional[str] = Field(None)
    true_answer: Optional[str] = Field(None)
    q_prev_image: Optional[str] = Field(None)
    essay_prev: Optional[str] = Field(None)
    a_prev: Optional[str] = Field(None)
    b_prev: Optional[str] = Field(None)
    c_prev: Optional[str] = Field(None)
    d_prev: Optional[str] = Field(None)

@router.put('/edit/{question_id}')
async def edit_question(session: sessionDep,user_types: Annotated[get_teacher, Depends()], question_id: Annotated[int, Path()],question_data: Annotated[str, Form()],
                       question_image: Annotated[UploadFile | None, File()] = None,
                       A_image: Annotated[UploadFile | None, File()] = None,
                       B_image: Annotated[UploadFile | None, File()] = None,
                       C_image: Annotated[UploadFile | None, File()] = None,
                       D_image: Annotated[UploadFile | None, File()] = None,
                       essay_image: Annotated[UploadFile | None, File()] = None,):
    teacher_id = (user_types['teacher']).decode('utf-8')
    items = EditQuestionItem(**json.loads(question_data))
    selected_question = session.query(Question).filter(Question.id == question_id)
    select_q = selected_question.first()
    q_img = question_image if question_image else (items.q_prev_image).split('/')[-1] if items.q_prev_image else None
    new_name = await check_image(session,select_q.image, q_img, teacher_id)
    question_val = {
        'question': items.question,
        'score': items.score,
        'type': items.type,
        'category': items.category,
        'difficulty': items.difficulty,
        'true_answer': items.true_answer,
        'image': new_name
    }

    if items.type == QUE_TYPES.test:
        selected_type_question = session.query(TestQuestion).filter(TestQuestion.question_id == question_id)
        selected_q = selected_type_question.first()
        past_image_name = [selected_q.A_image, selected_q.B_image, selected_q.C_image, selected_q.D_image]
        new_image_name = [A_image, B_image, C_image, D_image]
        prev_image_name = [items.a_prev, items.b_prev, items.c_prev, items.d_prev]
        names = ['A_image', 'B_image', 'C_image', 'D_image']
        res_dict = {}
        for name, past, new,prv in zip(names, past_image_name, new_image_name,prev_image_name):
            test_img = new if new else prv.split('/')[-1] if prv else None
            test_name = await check_image(session,past, test_img, teacher_id)
            res_dict[name] = test_name
        type_val = {
            'A': items.a,
            'B': items.b,
            'C': items.c,
            'D': items.d,
        }
        type_val.update(res_dict)
    elif items.type == QUE_TYPES.essay:
        selected_type_question = session.query(EssayQuestion).filter(EssayQuestion.question_id == question_id)
        select_essay = selected_type_question.first()
        choose_essay_img = essay_image if essay_image else items.essay_prev.split('/')[-1] if items.essay_prev else None
        essay_img = await check_image(session,select_essay.essay_image, choose_essay_img, teacher_id)
        type_val = {
            'essay_image': essay_img
        }
    else:
        selected_type_question = None
    update_question = selected_question.update(question_val)
    if selected_type_question:
        update_type = selected_type_question.update(type_val)
    session.commit()
    return JSONResponse(content={'status': 'updated'}, status_code=status.HTTP_200_OK)


@router.delete('/delete/{question_id}')
async def delete_question(session: sessionDep, question_id: Annotated[int, Path()],
                          user_types: Annotated[get_teacher, Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected_question = session.query(Question).filter(Question.teacher_id == teacher_id,
                                                       Question.id == question_id).first()
    if not selected_question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='question not found')
    question_image = selected_question.image
    if question_image:
        await remove_image(session,teacher_id,question_image, 'Questions')
    if selected_question.type == QUE_TYPES.test:
        selected_q_type = session.query(TestQuestion).filter(TestQuestion.question_id == question_id).first()
        option_image = [selected_q_type.A_image, selected_q_type.B_image, selected_q_type.C_image,
                        selected_q_type.D_image]
        for img in option_image:
            if img:
                await remove_image(session,teacher_id,img, 'Questions')
    elif selected_question.type == QUE_TYPES.essay:
        selected_q_type = session.query(EssayQuestion).filter(EssayQuestion.question_id == question_id).first()
        essay_img = selected_q_type.essay_image
        if essay_img:
            await remove_image(session,teacher_id,essay_img, 'Questions')
    else:
        selected_q_type = None
    if selected_q_type:
        session.delete(selected_q_type)
    session.delete(selected_question)
    session.commit()
    return JSONResponse(content={'status': 'deleted'}, status_code=status.HTTP_200_OK)
