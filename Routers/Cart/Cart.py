import datetime
from datetime import timedelta
from typing import Annotated

import jdatetime

from sqlalchemy import select, and_
from sqlmodel import Field
from starlette import status
from starlette.responses import JSONResponse
from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter, HTTPException
from fastapi.params import Body, Depends
from pydantic import BaseModel
from Database.DB import sessionDep, UserPlan, Cart, Plan, Transaction, STATUS_TARANS

router = APIRouter(prefix='/cart')

class CartItem(BaseModel):
    plan_id:int

@router.post('/add')
async def add_to_cart(session:sessionDep,item:Annotated[CartItem,Body()],user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    is_exist_plan = session.execute(select(UserPlan).where(and_(UserPlan.teacher_id==teacher_id,UserPlan.is_active==True))).first()
    is_exist_cart = session.query(Cart).filter(Cart.plan_id==item.plan_id,Cart.teacher_id==teacher_id,Cart.done==False).first()
    if not is_exist_plan and not is_exist_cart:
        cart = Cart(
            plan_id=item.plan_id,
            teacher_id=teacher_id,
        )
        session.add(cart)
        session.commit()
        session.refresh(cart)
    elif is_exist_cart:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail='cart exist')
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail='userplan exist')


@router.get('')
async def add_to_cart(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    plan_cart = session.execute(select(Cart,Plan).where(Cart.teacher_id==teacher_id,Cart.done==False)
                                      .join(Plan,Plan.id==Cart.plan_id)
                                      )
    res = []
    for c,p in plan_cart:
        res.append({
            'cart_id':c.id,
            'plan_name':p.name,
            'plan_price':p.price,
            'plan_student_number':p.student_number,
            'plan_question_number':p.question_number,
            'plan_exam_number':p.exam_number,
            'tagline':p.tagline
        })

    return JSONResponse({'plan_cart':res},status_code=status.HTTP_200_OK)



@router.delete('')
async def remove_cart(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    session.query(Cart).filter(Cart.teacher_id==teacher_id,Cart.done==False).delete()
    session.commit()
    return JSONResponse({'cart':'removed'},status_code=200)

class PurchaseData(BaseModel):
    cart_id:int = Field()
    price: int = Field()

@router.post('/purchase')
async def purchase(session:sessionDep,user_types:Annotated[get_teacher,Depends()],items:Annotated[PurchaseData,Body()]):
    teacher_id = (user_types['teacher']).decode('utf-8')
    # send to gateway
    trans_id = f'{jdatetime.datetime.now().date()}'
    transaction = Transaction(
        trans_id=trans_id,
        status=STATUS_TARANS.complete,
        payment_date=datetime.datetime.now(),
        price=items.price,
        payment_gateway='paypal',
        cart_id=items.cart_id
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)

    cart = session.query(Cart).filter(Cart.id==items.cart_id).first()
    cart.done=True

    userplan = UserPlan(
        exam_count=0,
        image_count=0,
        is_active=True,
        transaction_id=transaction.id,
        expired_date=datetime.datetime.now() + timedelta(days=365),
        teacher_id=teacher_id,
        plan_id=cart.plan_id
    )

    session.add(userplan)
    session.commit()
    session.refresh(userplan)

    return JSONResponse({'purchase':'done'},status_code=status.HTTP_201_CREATED)
