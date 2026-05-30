
from typing import Annotated

from fastapi import HTTPException, APIRouter
from fastapi.params import Depends
from starlette import status

from Database.DB import sessionDep, Teacher
from Dependencies.Redis import r
from Routers.Auths.MainAuth import authorization

async def get_teacher(session:sessionDep,payload: Annotated[authorization, Depends()]):
    user_id = payload['user_id']
    get_types = r.get(f'teacher-types{user_id}')
    if not get_types:
        try:
            teacher = session.query(Teacher).filter(Teacher.user_id==user_id).first().id
        except:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        r.set(f'teacher-types{user_id}',teacher)
        get_types = r.get(f'teacher-types{user_id}')

    return {'teacher':get_types}