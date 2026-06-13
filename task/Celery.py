from celery import Celery

celery_app = Celery(
    'exam_system',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)
import task.tasks