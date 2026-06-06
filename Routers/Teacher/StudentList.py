# from typing import Annotated
# from fastapi import APIRouter, HTTPException
# from fastapi.params import Depends
# from sqlalchemy import select, func
# from starlette import status
# from Database.DB import sessionDep, Class, Student, StudentClass, User, StudentScore
# from Routers.Teacher.TeacherAuthentication import get_teacher
#
# router = APIRouter(prefix='/teacher')
#
# @router.get('/students')
# async def get_student(session:sessionDep,user_types:Annotated[get_teacher,Depends()]):
#     teacher_id = (user_types['teacher']).decode('utf-8')
#     mean_score = select(
#         StudentScore.id.label('student_score_id'),
#         func.avg(StudentScore.score).filter(StudentScore.student_id==Student.id,StudentScore)
#     )
#     if teacher_id != 'None':
#         students = (session.query(StudentClass,Class,Student,User)
#                     .filter(Class.teacher_id == teacher_id)
#                     .join(Class, Class.id == StudentClass.class_id)
#                     .join(Student,Student.id==StudentClass.student_id)
#                     .join(User,User.id==Student.user_id)
#                     .join()
#                     .all()
#                     )
#         result = []
#         for sc,c,s,u in students:
#             dic_res = {'student_id':s.id,'student_name':f'{u.name} {u.last_name}','student_mobile':u.mobile,'status':sc.is_active,'class_name':c.name}
#             print(sc)
#             print(c)
#             print(s)
#             print(u)
#             break
#         return {'1':'1'}
#     return HTTPException(status_code=status.HTTP_403_FORBIDDEN)
#
#
#
