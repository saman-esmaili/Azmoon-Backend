from datetime import date, time,datetime
from typing import Optional, Annotated
from fastapi.params import Depends
from pydantic import EmailStr
from sqlalchemy import ForeignKey, create_engine
from enum import Enum
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel,Field

class UserTypes(str,Enum):
    student= 'student'
    teacher= 'teacher'
    admin= 'admin'

class BaseUser(SQLModel):
    membership_date: date = Field()
    type: UserTypes = Field(default=UserTypes.teacher)

class User(BaseUser,table=True):
    id: int = Field(primary_key=True)
    password: Optional[str] = Field(min_length=5)
    name: Optional[str] = Field(None, max_length=30, min_length=4)
    last_name: Optional[str] = Field(None, max_length=30, min_length=4)
    mobile: str = Field(max_length=11, min_length=11,regex=r'^09[0-3,9]\d{8}$')
    last_login: date = Field(None)
    email: Optional[EmailStr] = Field(None)


class EDU_QUA(str,Enum):
    diploma='دیپلم'
    high_diploma= 'فوق دیپلم'
    bachelor= 'لیسانس'
    high_bachelor= 'فوق لیسانس'
    phd= 'دکترا'

class SpcField(str,Enum):
    art='هنر'
    experimental= 'علوم تجربی'
    humanities= 'علوم انسانی'
    mathemetics= 'ریاضی فیزیک'
    foreign= 'زبان های خارجی'

class Teacher(SQLModel,table=True):
    id: int = Field(primary_key=True)
    school_name: Optional[str] = Field(min_length=4,max_length=20)
    educational_qualification: Optional[EDU_QUA] = Field(None)
    specialized_field: Optional[SpcField] = Field(None)
    user_id: int = Field(ForeignKey('user.id'))

class Student(SQLModel,table=True):
    id: int = Field(primary_key=True)
    user_id: int = Field(ForeignKey('user.id'))


class Admin(SQLModel,table=True):
    id: int = Field(primary_key=True)
    user_id: int = Field(ForeignKey('user.id'))

class Plan(SQLModel,table=True):
    id: int = Field(primary_key=True)
    name: str = Field(min_length=4,max_length=25)
    price: int = Field(ge=500_000)
    student_number: int = Field()
    exam_number: int = Field()

class UpdatePlan(Plan):
    name: Optional[str] = Field(min_length=4, max_length=25)
    price: Optional[int] = Field(ge=500_000)
    student_number: Optional[int] = Field()
    exam_number: Optional[int] = Field()

class Cart(SQLModel,table=True):
    id: int = Field(primary_key=True)
    teacher_id: int = Field(ForeignKey('teacher.id'))
    plan_id: int = Field(ForeignKey('plan.id'))

class STATUS_TARANS(str,Enum):
    complete='complete'
    incomplete='incomplete'

class Transaction(SQLModel,table=True):
    id: int = Field(primary_key=True)
    trans_id: str = Field()
    status: STATUS_TARANS = Field(default=STATUS_TARANS.incomplete)
    payment_date: date = Field()
    price: int= Field(ge=0)
    payment_gateway: str = Field()
    cart_id: int = Field(ForeignKey('cart.id'))

class UpdateTransaction(Transaction):
    status: STATUS_TARANS = Field()
    price: Optional[int] = Field(ge=0)
    payment_gateway: Optional[str] = Field()

class UserPlan(SQLModel,table=True):
    id: int = Field(primary_key=True)
    student_count: int = Field(ge=0)
    exam_count: int = Field(ge=0)
    is_active: bool = Field()
    transaction_id: int = Field()
    teacher_id: int = Field(ForeignKey('teacher.id'))
    plan_id: int = Field(ForeignKey('plan.id'))

class CreateUserPlan(UserPlan):
    pass

class UpdateUserPlan(UserPlan):
    student_count: Optional[int] = Field(ge=0)
    exam_count: Optional[int] = Field(ge=0)
    is_active: Optional[bool] = Field()


class Comment(SQLModel,table=True):
    id: int = Field(primary_key=True)
    comment: str = Field(min_length=20,max_length=250)
    star: float = Field(ge=0,le=5)
    teacher_id: int = Field(ForeignKey('teacher.id'))
    plan_id: int = Field(ForeignKey('plan.id'))

class CreateComment(Comment):
    pass

class UpdateComment(Comment):
    comment: Optional[str] = Field(min_length=20,max_length=250)
    star: Optional[float] = Field(ge=0,le=5)




class Class(SQLModel,table=True):
    id: int = Field(primary_key=True)
    name: str = Field(min_length=4,max_length=25)
    lesson: str = Field(min_length=4,max_length=25)
    grade: str = Field()
    signup_link: str = Field()
    description: Optional[str] = Field(min_length=4, max_length=200)
    date: datetime = Field()
    teacher_id: int = Field(ForeignKey('teacher.id'))

class UpdateClass(Class):
    name: Optional[str] = Field(min_length=4, max_length=25)
    lesson: Optional[str] = Field(min_length=4, max_length=25)
    grade: Optional[str] = Field()
    description: Optional[str] = Field(min_length=4, max_length=200)

class StudentClass(SQLModel,table=True):
    id: int = Field(primary_key=True)
    student_id: int = Field(ForeignKey('student.id'))
    class_id: int = Field(ForeignKey('class.id'))
    is_active: Optional[bool] = Field()


class ORDER(str,Enum):
    ordered='ordered'
    unordered='unordered'


class Exam(SQLModel,table=True):
    id: int = Field(primary_key=True)
    name: str = Field(min_length=4,max_length=25)
    exam_date: str = Field()
    start_time: time = Field()
    exam_time: int = Field()
    # graded: bool = Field()
    question_number: int = Field(gt=0)
    order_type: ORDER = Field(default=ORDER.ordered)
    description: Optional[str] = Field(min_length=4,max_length=200)
    score: int = Field()
    class_id: int = Field(ForeignKey('class.id'))

class UpdateExam(Exam):
    name: Optional[str] = Field(min_length=4, max_length=25)
    exam_date: Optional[str] = Field()
    start_time: Optional[time] = Field()
    exam_time: Optional[int] = Field()
    question_number: Optional[int] = Field(gt=0)
    order_type: ORDER = Field(default=ORDER.ordered)
    score: Optional[int] = Field()
    class_id: Optional[int] = Field(ForeignKey('class.id'))

class StudentScore(SQLModel,table=True):
    id: int = Field(primary_key=True)
    student_id: int = Field(ForeignKey('student.id'))
    exam_id: int = Field(ForeignKey('exam.id'))
    score: float = Field()
    trues: int = Field()
    falses: int = Field()
    not_answered: int = Field()
    date_score : date = Field()


class ControlExam(SQLModel,table=True):
    id: int = Field(primary_key=True)
    enter_time: time = Field()
    number_exit: int = Field(ge=0,le=4)
    exam_id: int = Field(ForeignKey('exam.id'))
    student_id: int = Field(ForeignKey('student.id'))

class UpdateControlExam(ControlExam):
    enter_time: Optional[time] = Field()
    number_exit: Optional[int] = Field(ge=0, le=4)


class QUE_TYPES(str,Enum):
    essay='essay'
    test='test'
    true_false='true_false'

class Difficulties(str,Enum):
    easy= 'easy'
    medium= 'medium'
    hard= 'hard'

class Question(SQLModel,table=True):
    id: int = Field(primary_key=True)
    question: str = Field(min_length=4,max_length=350)
    question_date: date = Field()
    type: QUE_TYPES = Field(default=QUE_TYPES.test)
    score: float = Field(gt=0)
    category: str = Field()
    difficulty: str = Field(default=Difficulties.easy)
    image: Optional[str] = Field(None)
    teacher_id: int = Field(ForeignKey('teacher.id'))

class UpdateQuestion(Question):
    question: Optional[str] = Field(min_length=4, max_length=350)
    score: Optional[float] = Field(gt=0)
    category: Optional[str] = Field()

class QuestionExam(SQLModel,table=True):
    id: int = Field(primary_key=True)
    exam_id: int = Field(ForeignKey('exam.id'))
    question_id: int = Field(ForeignKey('question.id'))


class StudentExam(SQLModel,table=True):
    id: int = Field(primary_key=True)
    answer: Optional[str] = Field(None,min_length=1,max_length=500)
    question_exam_id: int = Field(ForeignKey('questionexam.id'))
    visited: bool = Field()
    score: Optional[float] = Field(None)
    student_id: int = Field(ForeignKey('student.id'))

class UpdateStudentExam(StudentExam):
    answer: str = Field(None,min_length=1, max_length=500)

class TestQuestion(SQLModel,table=True):
    id: int = Field(primary_key=True)
    A: str = Field()
    A_image: Optional[str] = Field(None)
    B: str = Field()
    B_image: Optional[str] = Field(None)
    C: str = Field()
    C_image: Optional[str] = Field(None)
    D: str = Field()
    D_image: Optional[str] = Field(None)
    # true_answer: str = Field(max_length=1,min_length=1)
    question_id: int = Field(ForeignKey('question.id'))


class UpdateTestQuestion(TestQuestion):
    A: Optional[str] = Field()
    B: Optional[str] = Field()
    C: Optional[str] = Field()
    D: Optional[str] = Field()
    # true_answer: Optional[str] = Field(max_length=1, min_length=1)

class EssayQuestion(SQLModel,table=True):
    id: int = Field(primary_key=True)
    question_id: int = Field(ForeignKey('question.id'))
    essay_image: Optional[str] = Field(None)
#
# class UpdateEssayQuestion(EssayQuestion):
#     true_answer: Optional[str] = Field(min_length=1, max_length=500)
#
#
# class TrueFalseQuestion(SQLModel,table=True):
#     id: int = Field(primary_key=True)
#     # true_answer: bool
#     question_id: int = Field(ForeignKey('question.id'))
#
# class UpdateTrueFalseQuestion(TrueFalseQuestion):
#     true_answer: Optional[bool]

class TrueAnswerQuestion(SQLModel,table=True):
    id: int = Field(primary_key=True)
    true_answer: str = Field(min_length=1, max_length=800)
    question_id: int = Field(ForeignKey('question.id'))

DATABASE_URL = "postgresql://exam:saman123@localhost:5433/Exam"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# async def get_session(engine):
#     with Session(engine) as session:
#         yield session

async def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

sessionDep = Annotated[Session,Depends(get_session)]

def create_db_table():
    SQLModel.metadata.create_all(engine)