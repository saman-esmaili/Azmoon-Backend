import datetime
from typing import Annotated

import jdatetime
from fastapi import APIRouter
from fastapi.params import Depends
from psycopg2.extensions import STATUS_IN_TRANSACTION
from sqlalchemy import func, Case
from sqlalchemy.sql.functions import coalesce
from starlette import status
from starlette.responses import JSONResponse

from Database.DB import sessionDep, Transaction, Cart, User, Plan, STATUS_TARANS
from Routers.Admin.Authentication import get_admin

router = APIRouter(prefix='/admin')

@router.get('/payments')
async def payments(session:sessionDep,get_user:Annotated[get_admin,Depends()]):
    transaction = (session.query(Transaction,Cart,User,Plan)
                   .outerjoin(Cart,Cart.id==Transaction.cart_id)
                   .outerjoin(User,Cart.user_id==User.id)
                   .outerjoin(Plan,Cart.plan_id==Plan.id)
                   )
    result = []
    for trans,cart,user,plan in transaction:
        dic_res = {'id':trans.id,'trans_id':trans.trans_id,'status':trans.status,'payment_date':str(trans.payment_date),"price":trans.price,'gateway':trans.payment_gateway,'user_name':f'{user.name} {user.last_name}','plan':plan.name}
        result.append(dic_res)
    return JSONResponse({'transactions':result},status_code=status.HTTP_200_OK)


@router.get('/payments-info')
async def payments_info(session:sessionDep,get_user:Annotated[get_admin,Depends()]):
    # header
    now = datetime.datetime.utcnow()
    one_month_ago = now - datetime.timedelta(days=30)
    price_month = func.sum(Transaction.price).label('price')
    incomplete = coalesce(func.sum(Case((Transaction.status==STATUS_TARANS.incomplete,1),else_=0)),0).label('incomplete')
    complete = coalesce(func.sum(Case((Transaction.status==STATUS_TARANS.complete,1),else_=0)),0).label('complete')
    transactions = session.query(
        price_month,incomplete,complete
    ).filter(Transaction.payment_date >= one_month_ago)

    get_info = transactions.one()
    result = {'all':0}
    result['price'] = get_info.price
    result['incomplete'] = get_info.complete
    result['complete'] = get_info.incomplete
    result['all'] = get_info.complete + get_info.incomplete

    # diagram
    two_month_ago = now - datetime.timedelta(days=60)
    three_month_ago = now - datetime.timedelta(days=90)
    four_month_ago = now - datetime.timedelta(days=120)
    five_month_ago = now - datetime.timedelta(days=150)
    six_month_ago = now - datetime.timedelta(days=180)
    first_month = func.sum(Case(((now <= Transaction.payment_date) & (Transaction.payment_date <= one_month_ago),Transaction.price),else_=0)).label('first_month')
    second_month = func.sum(Case(((one_month_ago < Transaction.payment_date) & (Transaction.payment_date<= two_month_ago),Transaction.price),else_=0)).label('second_month')
    third_month = func.sum(Case(((two_month_ago < Transaction.payment_date) & (Transaction.payment_date <= three_month_ago),Transaction.price),else_=0)).label('third_month')
    fourth_month = func.sum(Case(((three_month_ago < Transaction.payment_date) & (Transaction.payment_date <= four_month_ago),Transaction.price),else_=0)).label('fourth_month')
    five_month = func.sum(Case(((four_month_ago < Transaction.payment_date) & (Transaction.payment_date<= five_month_ago),Transaction.price),else_=0)).label('five_month')
    six_month = func.sum(Case(((five_month_ago < Transaction.payment_date) & (Transaction.payment_date <= six_month_ago),Transaction.price),else_=0)).label('six_month')
    income = session.query(
        first_month,second_month,third_month,fourth_month,five_month,six_month
    ).select_from(Transaction)
    get_income = income.one()
    result['month_income'] = [get_income.first_month or 0,get_income.second_month or 0,get_income.third_month or 0,get_income.fourth_month or 0,get_income.five_month or 0,get_income.six_month or 0]
    # result['second'] = get_income.second_month
    # result['third'] = get_income.third_month
    # result['fourth'] = get_income.fourth_month
    # result['five'] = get_income.five_month
    # result['six'] = get_income.six_month
    month_number = jdatetime.datetime.now().month
    return JSONResponse({'payment_header':result,'month_number':month_number},status_code=status.HTTP_200_OK)

