import jdatetime
import sqlalchemy
from sqlalchemy import select, case, and_, func, join
from Database.DB import QuestionExam, StudentExam, Question, TrueAnswerQuestion, StudentScore, sessionDep, SessionLocal, \
    QUE_TYPES
from task.Celery import celery_app

@celery_app.task
def grade_exam(student_id: int, exam_id: int):
    session = SessionLocal()

    try:
        student_exam_ids = []

        # -------------------------
        # تصحیح تستی و صحیح/غلط
        # -------------------------

        stmt = (
            select(
                StudentExam.id,
                StudentExam.answer,
                Question.type,
                Question.true_answer,
                Question.score,
            )
            .join(
                QuestionExam,
                StudentExam.question_exam_id == QuestionExam.id
            )
            .join(
                Question,
                Question.id == QuestionExam.question_id
            )
            .where(
                and_(
                    QuestionExam.exam_id == exam_id,
                    StudentExam.student_id == student_id,
                    Question.type.in_(["true_false", "test"])
                )
            )
        )

        rows = session.execute(stmt).all()

        update_data = []

        total_correct = 0
        total_incorrect = 0

        for row in rows:
            score = 0

            if row.type == QUE_TYPES.test:
                if str(row.answer or "").strip() == str(row.true_answer).strip():
                    score = row.score
                    total_correct += 1
                else:
                    total_incorrect += 1

            elif row.type == QUE_TYPES.true_false:
                if str(row.answer or "").lower() == str(row.true_answer).lower():
                    score = row.score
                    total_correct += 1
                else:
                    total_incorrect += 1

            update_data.append(
                {
                    "id": row.id,
                    "score": score
                }
            )

            student_exam_ids.append(row.id)

        if update_data:
            session.bulk_update_mappings(
                StudentExam,
                update_data
            )

        # -------------------------
        # سوالات تشریحی بررسی نشده
        # -------------------------

        essay_stmt = (
            select(StudentExam.id)
            .join(
                QuestionExam,
                StudentExam.question_exam_id == QuestionExam.id
            )
            .join(
                Question,
                Question.id == QuestionExam.question_id
            )
            .where(
                and_(
                    QuestionExam.exam_id == exam_id,
                    StudentExam.student_id == student_id,
                    Question.type == QUE_TYPES.essay,
                    StudentExam.score.is_(None)
                )
            )
        )

        essay_questions = session.execute(
            essay_stmt
        ).scalars().all()

        student_exam_ids.extend(essay_questions)

        # اگر هنوز تشریحی تصحیح نشده وجود دارد
        if essay_questions:
            session.commit()
            return

        # -------------------------
        # محاسبه نمره کل
        # -------------------------

        total_score_stmt = (
            select(
                func.coalesce(
                    func.sum(StudentExam.score),
                    0
                )
            )
            .where(
                StudentExam.student_id == student_id
            )
        )

        total_score = session.execute(
            total_score_stmt
        ).scalar_one()

        # -------------------------
        # تعداد بدون پاسخ
        # -------------------------

        not_answered_stmt = (
            select(
                func.count(StudentExam.id)
            )
            .join(
                QuestionExam,
                StudentExam.question_exam_id == QuestionExam.id
            )
            .where(
                and_(
                    QuestionExam.exam_id == exam_id,
                    StudentExam.student_id == student_id,
                    (
                        StudentExam.answer.is_(None)
                    )
                )
            )
        )

        not_answered = session.execute(
            not_answered_stmt
        ).scalar_one()

        # -------------------------
        # ثبت نتیجه
        # -------------------------

        exists_score = session.execute(
            select(StudentScore).where(
                and_(
                    StudentScore.student_id == student_id,
                    StudentScore.exam_id == exam_id
                )
            )
        ).scalar_one_or_none()

        if not exists_score:
            result = StudentScore(
                student_id=student_id,
                exam_id=exam_id,
                score=float(total_score),
                trues=total_correct,
                falses=total_incorrect,
                not_answered=not_answered,
                date_score=jdatetime.datetime.now().date()
            )

            session.add(result)

        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()