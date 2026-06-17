import datetime
from Database.DB import UserPlan

async def plan_permit(teacher_id:int,session):
    user_plan = session.query(UserPlan).filter(UserPlan.teacher_id==teacher_id,UserPlan.is_active==True).first()
    if not user_plan:
       return False
    now = datetime.datetime.now().date()
    expire = user_plan.expired_date
    if expire > now:
        return True
    user_plan.is_active=False
    session.commit()
    return False
