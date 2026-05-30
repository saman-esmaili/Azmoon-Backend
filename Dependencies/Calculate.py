import datetime
from datetime import timedelta
import jdatetime

def calc_exam_status(exm_date,exm_time,start_time):
    if isinstance(exm_date,str):
        exm_date = jdatetime.datetime.strptime(exm_date,"%Y-%m-%d").date()
    elif not isinstance(exm_date, jdatetime.date):
        exm_date = jdatetime.date(exm_date.year, exm_date.month, exm_date.day)
    if isinstance(start_time,str):
        start_time = jdatetime.datetime.strptime(start_time, "%H:%M").time()
    elif not isinstance(start_time,jdatetime.time):
        start_time = jdatetime.time(start_time.hour, start_time.minute, start_time.second)
    exam_start_datetime = jdatetime.datetime.combine(exm_date, start_time)
    exam_end_datetime = exam_start_datetime + timedelta(minutes=exm_time)
    date_now = jdatetime.datetime.now()
    if exam_start_datetime > date_now:
        status = 'پیش رو'
    elif date_now > exam_end_datetime:
        status = 'برگزار شد'
    else:
        status = 'درحال برگزاری'
    return status
            


async def calc_time(start_time,long_time):
    now_datetime = datetime.datetime.now()
    start_datetime = datetime.datetime.combine(now_datetime.date(), start_time)
    now = datetime.datetime.now()
    end_time = start_datetime + datetime.timedelta(minutes=long_time)
    result = end_time - now
    minute = int(result.total_seconds()/60)
    return minute,end_time


