import datetime
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Optional
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.params import Body, Depends, Path, Form, File
from pydantic import BaseModel
from sqlalchemy import select, func, case, exists
import json
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Routers.Teacher.TeacherAuthentication import get_teacher
from Database.DB import sessionDep, QUE_TYPES, Difficulties, Question, TestQuestion, QuestionExam, Class, Exam, \
    EssayQuestion

router = APIRouter(prefix='/teacher/question')

class QuestionItem(BaseModel):
    question: str = Field(min_length=4, max_length=350)
    type: QUE_TYPES = Field(default=QUE_TYPES.test)
    score: float = Field(gt=0)
    category: str = Field()
    difficulty: str = Field(default=Difficulties.easy)
    a: Optional[str] = Field(None)
    b: Optional[str] = Field(None)
    c: Optional[str] = Field(None)
    d: Optional[str] = Field(None)
    true_answer: Optional[str] = Field(None)

async def generate_image_name(teacher_id,old_name):
    image_name,image_format = old_name.split('.')
    new_name = f"{teacher_id}_{uuid.uuid4()}_{image_name}"
    return f'{new_name}.{image_format}'

async def save_image(path,teacher_id,image:UploadFile):
    new_name = await generate_image_name(teacher_id,image.filename)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = f'{BASE_DIR}/{path}/{new_name}'
    with open(file_path,'wb') as f:
        shutil.copyfileobj(image.file,f)
    return new_name

async def remove_image(image_name,path):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = Path(f'{current_dir}/{path}/{image_name}')
    if file_path.exists():
        os.remove(file_path)

@router.post('/add')
async def add_question(session:sessionDep,user_types:Annotated[get_teacher,Depends()],question_data:Annotated[str,Form()],
                       question_image:Annotated[UploadFile | None, File()] = None,
                       A_image: Annotated[UploadFile | None, File()] = None,
                       B_image: Annotated[UploadFile | None, File()] = None,
                       C_image: Annotated[UploadFile | None, File()] = None,
                       D_image: Annotated[UploadFile | None, File()] = None,
                       essay_image: Annotated[UploadFile | None, File()] = None,
                       ):
    items = QuestionItem(**json.loads(question_data))
    teacher_id = (user_types['teacher']).decode('utf-8')

    if question_image:
        image_name = await save_image('Question',teacher_id,question_image)
    else:
        image_name = None


    q = Question(
        question=items.question,
        type=items.type,
        score=items.score,
        category=items.category,
        dfficulty=items.difficulty,
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
            await add_test_question(session,teacher_id,q_id,items.a,items.b,items.c,items.d,A_image,B_image,C_image,D_image)
        elif items.type == QUE_TYPES.essay:
            await add_essay_question(session,teacher_id,q_id,essay_image)
    except:
        selected_question = session.query(Question).filter(Question.id==q_id)
        await remove_image(selected_question.image,'Question')
        session.delete(selected_question)
        session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    return JSONResponse(content={'status':'ok'},status_code=status.HTTP_201_CREATED)


async def add_test_question(session,teacher_id,q_id,a,b,c,d,a_image,b_image,c_image,d_image):
    if a_image:
        a_image_name = await save_image('Question', teacher_id, a_image)
    else:
        a_image_name = None
    if b_image:
        b_image_name = await save_image('Question', teacher_id, a_image)
    else:
        b_image_name = None
    if c_image:
        c_image_name = await save_image('Question', teacher_id, a_image)
    else:
        c_image_name = None

    if d_image:
        d_image_name = await save_image('Question', teacher_id, a_image)
    else:
        d_image_name = None

    test_q = TestQuestion(
        A=a,
        B=b,
        C=c,
        D=d,
        question_id=q_id,
        A_image=a_image_name,
        B_image=b_image_name,
        C_image=c_image_name,
        D_image=d_image_name
    )
    session.add(test_q)
    session.commit()
    session.refresh(test_q)

async def add_essay_question(session,teacher_id,q_id,essay_image:UploadFile):
    if essay_image:
        image_name = await save_image('Question', teacher_id, essay_image)
    else:
        image_name = None
    essay_question = EssayQuestion(
        question_id=q_id,
        essay_image=image_name
    )
    session.add(essay_question)
    session.commit()
    session.refresh(essay_question)
@router.get('')
async def show_question(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):

    teacher_id = (user_types['teacher']).decode('utf-8')
    use = select(
        QuestionExam.exam_id.label('exam_id'),
        func.count(func.distinct(QuestionExam.exam_id)).label('count_use')
    ).group_by(QuestionExam.exam_id).subquery()
    header = {}
    use_q = (session.query(Class,Exam,use.c.count_use)
             .filter(Class.teacher_id==teacher_id)
             .outerjoin(Exam,Exam.class_id==Class.id)
             .outerjoin(use,use.c.exam_id==Exam.id)
             .with_entities(func.coalesce(use.c.count_use, 0).label('count_use'))
             )
    header['use_count'] = use_q.count_use
    questions = session.query(
        Question,
        TestQuestion,
        func.sum(case((Question.type == QUE_TYPES.test, 1), else_=0)).label('count_test'),
        func.sum(case((Question.type == QUE_TYPES.essay, 1), else_=0)).label('count_essay'),
        func.sum(case((Question.type == QUE_TYPES.true_false, 1), else_=0)).label('count_true_false')
    ).filter(
        Question.teacher_id == teacher_id
    ).outerjoin(
        TestQuestion, TestQuestion.question_id == Question.id
    ).group_by(
        Question.id
    )
    result = []

    count = 1
    for q,tq,ct,ce,ctf in questions:
        if count == 1:
            header['test_count'] = ct
            header['essay_count'] = ce
            header['true_false_count'] = ctf
            header['all'] = ct+ce+ctf
            count+=1
        dic_res ={'id': q.id, 'question': q.question, 'score': q.score, 'category': q.category,
            'difficulty': q.difficulty,'type':q.type,'true_answer':q.true_answer}
        if tq:
            dic_res.update({'A':tq.A,'B':tq.B,'C':tq.C,'D':tq.D})
        result.append(dic_res)
    return JSONResponse(content={'questions':result,'questions_info':header})


@router.put('/edit/{question_id}')
async def edit_question(items:Annotated[QuestionItem,Body()],session:sessionDep,user_types: Annotated[get_teacher, Depends()],question_id:Annotated[int,Path()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected_question = session.query(Question).filter(Question.id==question_id)
    question_val = {
        'question':items.question,
        'score':items.score,
        'type':items.type,
        'category':items.category,
        'difficulty':items.difficulty,
    }

    if items.type == QUE_TYPES.test:
        selected_type_question = session.query(TestQuestion).filter(TestQuestion.question_id==question_id)
        type_val = {
            'A': items.a,
            'B': items.b,
            'C': items.c,
            'D': items.d,
            'true_answer':items.true_test
        }
    elif items.type == QUE_TYPES.true_false:
        selected_type_question = session.query(TrueFalseQuestion).filter(TrueFalseQuestion.question_id==question_id)
        type_val = {
            'true_answer': items.true_false
        }
    else:
        selected_type_question = session.query(EssayQuestion).filter(EssayQuestion.question_id==question_id)
        type_val = {
            'true_answer': items.text_answer
        }
    update_question = selected_question.update(question_val)
    update_type = selected_type_question.update(type_val)
    session.commit()
    return JSONResponse(content={'status':'updated'},status_code=status.HTTP_200_OK)

@router.delete('/delete/{question_id}')
async def delete_question(session:sessionDep,question_id:Annotated[int,Path()],user_types: Annotated[get_teacher, Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected_question = session.query(Question).filter(Question.teahcher_id==teacher_id,Question.id==question_id).first()
    if selected_question.type == QUE_TYPES.test:
        selected_q_type = session.query(TestQuestion).filter(TestQuestion.question_id == question_id).first()
    elif selected_question.type == QUE_TYPES.true_false:
        selected_q_type = session.query(TrueFalseQuestion).filter(TestQuestion.question_id == question_id).first()
    else:
        selected_q_type = session.query(EssayQuestion).filter(TestQuestion.question_id == question_id).first()
    session.delete(selected_q_type)
    session.delete(selected_question)
    session.commit()
    return JSONResponse(content={'status': 'deleted'}, status_code=status.HTTP_200_OK)


# show questions
    # all_questions = select(
    #     Question.id.label('question_id'),
    #     func.count(Question.id).label('all_question')
    # ).group_by(Question.id).subquery()
    #
    # count_tq = select(
    #     Question.id.label('question_id'),
    #     func.count(case(Question.type==QUE_TYPES.test,Question.id),else_=0).label('count_test')
    # ).group_by(Question.id).subquery()
    # count_essay = select(
    #     Question.id.label('question_id'),
    #     func.count(case(Question.type == QUE_TYPES.essay, Question.id), else_=0).label('count_essay')
    # ).group_by(Question.id).subquery()
    #
    # count_tf = select(
    #     Question.id.label('question_id'),
    #     func.count(case(Question.type == QUE_TYPES.true_false, Question.id), else_=0).label('count_true_false')
    # ).group_by(Question.id).subquery()
    #

    # questions = (session.query(Question,TestQuestion,count_tq.c.count_test,count_essay.c.count_essay,count_tf.c.count_true_false)
    #              .filter(Question.teacher_id==teacher_id)
    #              .outerjoin(TestQuestion,TestQuestion.question_id==Question.id)
    #              .outerjoin(count_tq,count_tq.c.question_id==Question.id)
    #              .outerjoin(count_essay,count_essay.c.question_id==Question.id)
    #              .outerjoin(count_tf,count_tf.c.question_id==Question.id)
    #              )