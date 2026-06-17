from math import ceil
from typing import Annotated

from sqlalchemy import func
from starlette import status
from starlette.middleware.errors import JS
from starlette.responses import JSONResponse

from Dependencies.Calculate import to_jalali, months_remaining
from Routers.Teacher.TeacherAuthentication import get_teacher
from fastapi import APIRouter
from fastapi.params import Depends, Query
from Database.DB import sessionDep, Cart, Transaction, Plan

router = APIRouter(prefix='/teacher/transaction')


@router.get('')
async def transaction(session: sessionDep, user_type: Annotated[get_teacher, Depends()],
                      page : int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)):
    teacher_id = (user_type['teacher']).decode('utf-8')
    query = (session.query(Transaction, Cart, Plan)
             .outerjoin(Cart, Transaction.cart_id == Cart.id)
             .filter(Cart.teacher_id == teacher_id)
             .outerjoin(Plan, Plan.id == Cart.plan_id)
             )
    total = query.count()

    trans = (
        query
        .order_by(Transaction.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    result = []
    for tr, c, p in trans:
        result.append(
            {'id': tr.id, 'price': tr.price, 'status': tr.status, 'name': p.name, 'gateway': tr.payment_gateway,
             'date': to_jalali(tr.payment_date), 'trans_id': tr.trans_id})

    return JSONResponse({
        'items': result,
        'page': page,
        'size': size,
        'total': total,
        'pages': ceil(total / size) if total else 1,
    }, status_code=status.HTTP_200_OK)

@router.get('/trans/info')
async def trans_info(session: sessionDep, user_type: Annotated[get_teacher, Depends()]):
    teacher_id = (user_type['teacher']).decode('utf-8')
    complete_count = (
        session.query(Transaction)
        .join(Cart, Transaction.cart_id == Cart.id)
        .filter(
            Cart.teacher_id == teacher_id,
            Transaction.status == "complete"
        )
        .count()
    )

    incomplete_count = (
        session.query(Transaction)
        .join(Cart, Transaction.cart_id == Cart.id)
        .filter(
            Cart.teacher_id == teacher_id,
            Transaction.status == "incomplete"
        )
        .count()
    )

    total_amount = (
            session.query(func.sum(Transaction.price))
            .join(Cart, Transaction.cart_id == Cart.id)
            .filter(
                Cart.teacher_id == teacher_id,
                Transaction.status == "complete"
            )
            .scalar() or 0
    )

    return JSONResponse({"stats": {
            "total_amount": total_amount,
            "complete_count": complete_count,
            "incomplete_count": incomplete_count
        }},status_code=200)