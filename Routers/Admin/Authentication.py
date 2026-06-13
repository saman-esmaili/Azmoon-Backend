from typing import Annotated
from fastapi import HTTPException
from fastapi.params import Depends
from starlette import status
from Database.DB import sessionDep, Admin
from Routers.Auths.MainAuth import authorization
from Dependencies.Redis import r

async def get_admin(session:sessionDep,payload: Annotated[authorization, Depends()]):
    user_id = payload['user_id']
    get_types = r.get(f'admin-types{user_id}')
    if not get_types:
        try:
            admin = session.query(Admin).filter(Admin.user_id==user_id).first().id
            r.set(f'admin-types{user_id}', admin)
            get_types = r.get(f'admin-types{user_id}')
        except:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    return {'admin':get_types}
