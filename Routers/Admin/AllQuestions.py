from math import ceil
from typing import Annotated

from fastapi import APIRouter
from fastapi.params import Depends, Query
from sqlalchemy import Case, func, or_
from starlette.responses import JSONResponse

from Database.DB import sessionDep, Question, TestQuestion, EssayQuestion, QUE_TYPES
from Routers.Admin.Authentication import get_admin

router = APIRouter(prefix='/admin')

@router.get('/questions/')
async def questions(session:sessionDep,get_user:Annotated[get_admin,Depends()], page: int = Query(1, ge=1),
                    size: int = Query(10, ge=1, le=100), search: str = Query()):
    query = (session.query(Question, TestQuestion, EssayQuestion)
                 .outerjoin(TestQuestion, TestQuestion.question_id == Question.id)
                 .outerjoin(EssayQuestion, EssayQuestion.question_id == Question.id)
                 )
    total = query.count()
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            or_(
                Question.question.contains(search_term),
                Question.true_answer.contains(search_term),
                Question.category.contains(search_term),
            )
        )
    questions = (
        query
        .order_by(Question.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size)
    result = []
    for q, tq, eq in questions:
        dic_res = {'id': q.id, 'text': q.question,'question_image':q.image, 'score': q.score, 'cat': q.category,
                   'diff': q.difficulty, 'type': q.type,'true_answer': q.true_answer}
        if tq:
            dic_res.update({'A': tq.A, 'B': tq.B, 'C': tq.C, 'D': tq.D,'A_image':tq.A_image,'B_image':tq.B_image
                            ,'C_image':tq.C_image
                            ,'D_image':tq.D_image})
        elif eq:
            dic_res.update({'essay_image': eq.essay_image})
        result.append(dic_res)
    return JSONResponse(content={'result':result,'pages':pages})
#
# @router.get('/questions-info')
# async def questions_info(session:sessionDep,get_user:Annotated[get_admin,Depends()]):
#     test_count = func.sum(Case((Question.type==QUE_TYPES.test,1),else_=0)).label('test_count')
#     essay_count = func.sum(Case((Question.type==QUE_TYPES.essay,1),else_=0)).label('essay_count')
#     tf_count = func.sum(Case((Question.type==QUE_TYPES.true_false,1),else_=0)).label('tf_count')
#     q = session.query(
#         test_count,essay_count,tf_count
#     ).select_from(Question)
#     questions = {}
#     for t,e,tf in q:
#         questions['test'] = t
#         questions['essay'] = e
#         questions['true_false'] = tf
#     return {'question_info':questions}
