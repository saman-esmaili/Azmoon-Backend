from typing import Annotated

from sqlalchemy import select, and_
from starlette import status
from starlette.responses import JSONResponse

from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter
from fastapi.params import Body, Depends
from pydantic import BaseModel
from Database.DB import sessionDep, UserPlan, Cart, Plan

router = APIRouter(prefix='/cart')

class CartItem(BaseModel):
    plan_id:int

@router.post('/add')
async def add_to_cart(session:sessionDep,item:Annotated[CartItem,Body()],user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    is_exist_plan = session.execute(select(UserPlan).where(and_(UserPlan.teacher_id==teacher_id,UserPlan.is_active==True)))
    if not is_exist_plan:
        cart = Cart(
            plan_id=item.plan_id,
            teacher_id=teacher_id
        )
        session.add(cart)
        session.commit()
        session.refresh(cart)


@router.get('/')
async def add_to_cart(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    plan_cart = session.execute(select(Cart,Plan).where(Cart.teacher_id==teacher_id)
                                      .join(Plan,Plan.id==Cart.plan_id)
                                      ).fetchone()
    result = {}
    for c,p in plan_cart:
        result['cart_id'] = c.id
        result['plan_name'] = p.name
        result['plan_price'] = p.price
        result['plan_student_number'] = p.student_number
        result['plan_exam_number'] = p.exam_number

    return JSONResponse({'plan_cart':result},status_code=status.HTTP_200_OK)





