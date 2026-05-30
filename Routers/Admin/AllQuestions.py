from typing import Annotated

from fastapi import APIRouter
from fastapi.params import Depends
from sqlalchemy import Case, func
from starlette.responses import JSONResponse

from Database.DB import sessionDep, Question, TestQuestion
from Routers.Admin.Authentication import get_admin

router = APIRouter(prefix='/admin')

@router.get('/questions/')
async def questions(session:sessionDep,get_user:Annotated[get_admin,Depends()]):
    questions = (session.query(Question, TestQuestion, EssayQuestion, TrueFalseQuestion)
                 .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                 .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                 .outerjoin(TrueFalseQuestion, TrueFalseQuestion.question_id == Question.id)
                 )
    result = []
    for q, tq, eq, tfq in questions:
        dic_res = {'id': q.id, 'question': q.question, 'score': q.score, 'category': q.category,
                   'difficulty': q.difficulty, 'type': q.type}
        if tq:
            dic_res.update({'A': tq.A, 'B': tq.B, 'C': tq.C, 'D': tq.D, 'true_answer': tq.true_answer})
        elif eq:
            dic_res.update({'true_answer': eq.true_answer})
        elif tfq:
            dic_res.update({'true_answer': tfq.true_answer})
        result.append(dic_res)
    return JSONResponse(content={'result':result})

@router.get('/questions-info')
async def questions_info(session:sessionDep,get_user:Annotated[get_admin,Depends()]):
    test_count = func.sum(Case((Question.type=='test',1),else_=0)).label('test_count')
    essay_count = func.sum(Case((Question.type=='essay',1),else_=0)).label('essay_count')
    tf_count = func.sum(Case((Question.type=='true_false',1),else_=0)).label('tf_count')
    q = session.query(
        test_count,essay_count,tf_count
    ).select_from(Question)
    questions = {'all':0}
    for t,e,tf in q:
        questions['test'] = t
        questions['essay'] = e
        questions['true_false'] = tf
        questions['all'] = t+e+tf
    return {'question_info':questions}
