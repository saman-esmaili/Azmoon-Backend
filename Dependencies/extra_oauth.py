# current_dir = os.path.dirname(os.path.abspath(__file__))
# secret_file_path = os.path.join(current_dir, '..', '..', 'Dependencies', 'secret.txt')
# with open(secret_file_path, 'r') as file:
#     secret = file.read()

# for OAUTH2
# REFRESH_EXPIRE_TIME = 24*7*60*60
# auth2 = OAuth2PasswordBearer(tokenUrl='verify-code')
# ALGORITHM = 'HS256'


# def create_access_token(user_id:int):
#     # exp should be 15 min
#     payload = {
#         'user_id': user_id,
#         'exp': datetime.datetime.utcnow() + timedelta(minutes=15)
#     }
#     access_token = jwt.encode(payload, secret, algorithm=ALGORITHM)
#     return access_token


#
# def create_refresh_token():
#     raw = secrets.token_urlsafe(32)
#     return raw,hash_token(raw)


# in login def
# access_token = create_access_token(user_id)
# raw_refresh, refresh_hash = create_refresh_token()
# r.setex(refresh_hash, REFRESH_EXPIRE_TIME, user_id)



#async def get_refresh_token(refresh_token: Annotated[str | None, Cookie()] = None):
#     if not refresh_token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Token cookie not found"
#         )
#     return refresh_token
# @router.post('/refresh')
# async def refresh_token(refresh_token: Annotated[str, Depends(get_refresh_token)],response:Response):
#     # response = Response()
#     hash_refresh = hash_token(refresh_token)
#     user_id = r.get(hash_refresh)
#     if not user_id:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='invalid refresh token')
#     user_id = user_id.decode('utf-8')
#     r.delete(hash_refresh)
#     raw_refresh,hashed_refresh = create_refresh_token()
#     r.setex(raw_refresh,REFRESH_EXPIRE_TIME,user_id)
#     access_token = create_access_token(user_id)
#     response.set_cookie(
#         key='access_token',
#         value=access_token,
#         max_age=15*60,
#         httponly=True,
#         secure=False,
#         samesite='none'
#     )
#     response.set_cookie(
#         key='refresh_token',
#         value=raw_refresh,
#         max_age=REFRESH_EXPIRE_TIME,
#         httponly=True,
#         secure=False,
#         samesite='none'
#     )
    # return response


# async def get_access_token(access_token: Annotated[str | None, Cookie()] = None):
#     if not access_token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Token cookie not found"
#         )
#     return access_token