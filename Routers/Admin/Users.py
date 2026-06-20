from math import ceil
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Query, Path
from sqlalchemy import func, and_, or_
from starlette import status
from starlette.responses import JSONResponse

from Database.DB import sessionDep, User, UserPlan, Plan, Teacher, Student, Exam, Class
from Routers.Admin.Authentication import get_admin

router = APIRouter(prefix='/admin')


@router.get('/users')
async def get_users(session: sessionDep, is_admin: Annotated[get_admin, Depends()], page: int = Query(1, ge=1),
                    size: int = Query(10, ge=1, le=100), search: str = Query()):
    plan_count = (
        session.query(
            UserPlan.teacher_id,
            func.count(UserPlan.id).label("total_plans")
        )
        .group_by(UserPlan.teacher_id)
        .subquery()
    )
    query_builder = (
        session.query(User, Teacher, UserPlan, Plan, plan_count.c.total_plans)
        .outerjoin(Teacher, Teacher.user_id == User.id)
        .outerjoin(
            UserPlan,
            and_(
                UserPlan.teacher_id == Teacher.id,
                UserPlan.is_active == True
            )
        )
        .outerjoin(Plan, Plan.id == UserPlan.plan_id)
        .outerjoin(plan_count, plan_count.c.teacher_id == Teacher.id)
    )
    total = query_builder.count()
    if search:
        search_term = f'%{search}%'
        query_builder = query_builder.filter(
            or_(
                User.name.contains(search_term),
                User.last_name.contains(search_term),
                User.mobile.contains(search_term),
                Plan.name.contains(search_term),
            )
        )
    users = (
        query_builder
        .order_by(User.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    pages = ceil(total / size)
    exam_count = session.query(Exam).count()
    # users = query_builder.all()
    result = []
    for u, t, up, p, plan_count in users:
        dic_res = {'id': u.id, 'name': f'{u.name} {u.last_name}', 'mobile': u.mobile, 'type': u.type, 'email': u.email,
                   'plan_count': plan_count,
                   'last_login': str(u.last_login), 'membership_date': str(u.membership_date),
                   'plan': p.name if p else '-'}
        result.append(dic_res)
    return JSONResponse({'users': result, 'exam': exam_count,'pages':pages}, status_code=status.HTTP_200_OK)
