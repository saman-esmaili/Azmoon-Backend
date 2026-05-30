import datetime

import jdatetime
import sqlalchemy
from sqlalchemy import select, Case, and_, func, join

from Database.DB import QuestionExam, StudentExam, Question, TestQuestion, TrueAnswerQuestion, StudentScore
from Dependencies.Celery import celery_app


@celery_app.task
async def grade_exam(session,student_id,exam_id):
    question_exam = session.query(QuestionExam).subquery()
    student_exam = session.query(StudentExam).subquery()
    question = session.query(Question).subquery()
    true_answer_question = session.query(TrueAnswerQuestion).subquery()
    student_exam_ids = []

    stmt_tf_test = (
        select(
            student_exam.c.id.label('student_Exam_id'),

            Case(
                and_(
                    question.c.type == 'true_false',
                    func.cast(true_answer_question.c.true_answer, sqlalchemy.Boolean) == student_exam.c.answer
                ),
                question.c.score
            ),
            (
                and_(
                    question.c.type=='test',
                    true_answer_question.c.true_answer==student_exam.c.answer
                ),
                question.c.score
            ),
            else_=0
        ).label('calculated_score')
    ).select_from(
        join(student_exam,question_exam,student_exam.c.question_exam_id==question_exam.c.id)
        .join(question,question.c.id==question_exam.c.question_id)
        .outerjoin(true_answer_question,true_answer_question.c.question_id==question.c.id)
    ).filter(
        and_(
            question_exam.c.exam_id == exam_id,
            student_exam.c.student_id == student_id,
            question.c.type.in_(['true_false', 'test'])
        )
    )

    results_tf_test = session.execute(stmt_tf_test).fetchall()
    update_data_tf_test = []
    for row in results_tf_test:
        update_data_tf_test.append({"id": row.student_exam_id, "score": row.calculated_score})
        student_exam_ids.append(row.student_exam_id)

    if update_data_tf_test:
        session.bulk_update_mappings(StudentExam, update_data_tf_test)

    stmt_essay = (
        select(StudentExam.c.id).label('student_exam_id')
        .select_from(
            join(StudentExam, QuestionExam, StudentExam.c.question_exam_id == QuestionExam.c.id)
            .join(Question, Question.c.id == QuestionExam.c.question_id)
        )
        .filter(
            and_(
                QuestionExam.c.exam_id == exam_id,
                StudentExam.c.student_id == student_id,
                Question.c.type == 'essay',
                StudentExam.c.score.is_(None)
            )
        )
    )

    essay_questions_to_grade = session.execute(stmt_essay).fetchall()
    student_exam_ids.append(row[0] for row in essay_questions_to_grade)
    if not essay_questions_to_grade:
        sum_scores = select(
            StudentExam,
            func.sum(
                Case(
                    (StudentExam.id.in_(student_exam_ids),StudentExam.score),else_=0
                )
            )
        ).where(StudentExam.student_id==student_id)
        get_score = session.execute(sum_scores).scalar()

        count_not_answer_stmt = (
            select(func.count(StudentExam.id).label('not_answered_count'))
            .join(QuestionExam, StudentExam.c.question_exam_id == QuestionExam.c.id)
            .where(and_(
                QuestionExam.c.exam_id == exam_id,
                StudentExam.c.student_id == student_id,
                StudentExam.c.answer.is_(None)
            ))
        )
        tf_test_results_for_counting = (
            select(
                func.coalesce(
                    Case(
                        [
                            (and_(
                                question.c.type.in_(['true_false', 'test']),
                                true_answer_question.c.true_answer.isnot(None),
                                func.cast(true_answer_question.c.true_answer, sqlalchemy.Boolean) == func.cast(
                                    student_exam_alias.c.answer, sqlalchemy.Boolean)
                            ), 1)],
                        else_=0
                    ),
                    0
                ).label('is_correct_count'),
                func.coalesce(
                    Case(
                        [
                            (and_(
                                question.c.type.in_(['true_false', 'test']),
                                true_answer_question.c.true_answer.isnot(None),
                                func.cast(true_answer_question.c.true_answer, sqlalchemy.Boolean) != func.cast(
                                    student_exam.c.answer, sqlalchemy.Boolean)
                            ), 1)],
                        else_=0
                    ),
                    0
                ).label('is_incorrect_count')
            ).select_from(
                join(student_exam, question_exam, student_exam.c.question_exam_id == question_exam.c.id)
                .join(question, question.c.id == question_exam.c.question_id)
                .outerjoin(true_answer_question, true_answer_question.c.question_id == question.c.id)
            ).filter(
                and_(
                    question_exam.c.exam_id == exam_id,
                    student_exam.c.student_id == student_id,
                    question.c.type.in_(['true_false', 'test']),
                    student_exam.c.answer.isnot(None),  # فقط پاسخ‌هایی که داده شده‌اند
                    student_exam.c.answer != ''
                )
            )
        )

        not_answered_result = session.execute(count_not_answer_stmt).scalar()

        counting_results = session.execute(tf_test_results_for_counting).fetchall()
        total_correct_count = 0
        total_incorrect_count = 0

        for row in counting_results:
            total_correct_count += row.is_correct_count
            total_incorrect_count += row.is_incorrect_count


        insert_student_score = StudentScore(
            student_id=student_id,
            exam_id=exam_id,
            score=get_score,
            date_score=jdatetime.datetime.now().date(),
            trues=total_correct_count,
            falses=total_incorrect_count,
            not_answered=not_answered_result
        )
        session.add(insert_student_score)
        session.commit()
        session.refresh(insert_student_score)

    session.commit()
