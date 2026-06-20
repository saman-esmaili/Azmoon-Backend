from sys import path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os

from starlette.staticfiles import StaticFiles

from Database.DB import create_db_table, Teacher
from Dependencies.Redis import r
from Routers.Teacher import Class, Questions, Exam, StudentList, Myplan, Transaction, Comment
from Routers.Teacher import Exam as exam_teacher
from Routers.Auths import MainAuth
from Routers.Admin import Users,AllQuestions,AllPayments
from Routers.Student import Authentication, dashboard, Exam, Class
from Routers.Cart import Cart
from Routers.Teacher import TeacherAuthentication
from Routers.Landing import landing
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_methods=['*'],
    allow_credentials=True,
    allow_headers=['*'],
    allow_origins=["http://localhost:3000"]
)

app.include_router(MainAuth.router)
app.include_router(landing.router)

# ---   Teacher   ---
app.include_router(Class.router)
app.include_router(Questions.router)
app.include_router(Exam.router)
app.include_router(StudentList.router)
app.include_router(TeacherAuthentication.router)
app.include_router(exam_teacher.router)
app.include_router(Myplan.router)
app.include_router(Transaction.router)
app.include_router(Comment.router)

# ---   Admin   ---
app.include_router(Users.router)
app.include_router(AllQuestions.router)
app.include_router(AllPayments.router)


# ---   Student   ---
app.include_router(Authentication.router)
app.include_router(dashboard.router)
app.include_router(Exam.router)
app.include_router(Class.router)


app.mount("/Questions", StaticFiles(directory="Questions"), name="Questions")

# Cart
app.include_router(Cart.router)
@app.on_event('startup')
def startup():
    # r.flushdb()
    if not os.environ.get("TEST_MODE"):
        create_db_table()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(f'{current_dir}/Questions',exist_ok=True)


