from fastapi import APIRouter
from pygments import highlight
from starlette.responses import JSONResponse

from Database.DB import sessionDep, Plan, UserPlan

router = APIRouter()

@router.get('/plan')
async def get_plan(session:sessionDep):
    plans = session.query(Plan)
    result = []
    i = 1
    for plan in plans:
        result.append({'id':plan.id,'name':plan.name,'exam_number':plan.exam_number,
                       'question_number':plan.question_number,'student_number':plan.student_number,'price':plan.price,'highlight': True if i == 2 else False
                       })
        i+=1

    return JSONResponse(content={'plans':result})