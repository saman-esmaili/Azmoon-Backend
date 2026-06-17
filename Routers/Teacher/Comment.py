from typing import Annotated

import jdatetime
from select import select
from sqlalchemy import func, and_
from starlette import status
from starlette.responses import JSONResponse

from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter
from fastapi.params import Body, Depends, Path
from pydantic import BaseModel, Field
from Database.DB import sessionDep, UserPlan, Cart, Plan, Comment, Teacher, User

router = APIRouter(prefix='/comment')

class CommentItem(BaseModel):
    plan_id:int
    star:float = Field(gt=0,le=5)
    comment: str = Field(min_length=2,max_length=250)

@router.post('/add')
async def add_comment(session:sessionDep,item:Annotated[CommentItem,Body()],user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    comment = Comment(
        plan_id=item.plan_id,
        teacher_id=teacher_id,
        star=item.star,
        comment=item.comment,
        created_at=jdatetime.datetime.now().date()
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)

@router.get('')
async def comment(session:sessionDep):
    comments = (session.execute(select(Comment,Teacher,User))
                .join(Teacher,Teacher.id==Comment.teacher_id)
                .join(User,User.id==Teacher.user_id)
                .order_by(func.random()).limit(10))
    result = []
    for cmt,tch,u in comments:
        result.append({'comment_id':cmt.id,'user_name':f'{u.name} {u.last_name}','school_name':tch.school_name,'comment':cmt.comment,'star':cmt.star})

    return JSONResponse({'comments':result},status.HTTP_200_OK)


@router.put('/{comment_id}')
async def edit_comment(session:sessionDep,item:Annotated[CommentItem,Body()],comment_id:Annotated[int,Path()],user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected_comment = (session.execute(select(Comment)
                                       .where(and_(Comment.id==comment_id)))
                        .fetchone())
    val = {
        'plan_id':item.plan_id,
        'teacher_id':teacher_id,
        'comment':item.comment,
        'star':item.star,
    }
    update = selected_comment.update(val)
    session.commit()

@router.delete('/{comment_id}')
async def delete_comment(session:sessionDep,comment_id:Annotated[int,Path()],user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    selected_comment = (session.execute(select(Comment)
                                       .where(and_(Comment.id==comment_id,Comment.teacher_id==teacher_id)))
                        .fetchone())
    if selected_comment:
        session.delete(selected_comment)
        session.commit()

@router.get('/teacher')
async def get_teacher_comment(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    comments = (session.query(Comment,Plan)
                .filter(Comment.teacher_id==teacher_id)
                .outerjoin(Plan,Plan.id == Comment.plan_id)
                )
    result = []
    for comment,plan in comments:
        result.append({'comment_id':comment.id,'plan_name':plan.name,'rating':comment.star,'comment':comment.comment,'created_at':comment.created_at})

    return JSONResponse({'comment':result})