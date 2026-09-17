from flask import Blueprint, render_template, request, redirect, url_for, flash

from auth import login_required
from database import (
    get_student_lessons_with_status,
    get_assignments_by_lesson,
    get_submissions_for_student,
    mark_lesson_completed,
    submit_assignment,
    submit_quiz_answer,
    get_assignment,
    get_assignment_options,
    get_student_stats,
)

student_bp = Blueprint("student", __name__, url_prefix="/student")


def _progress_percent(lessons_with_status):
    if not lessons_with_status:
        return 0

    completed = sum(1 for entry in lessons_with_status if entry["status"] == "completed")

    return round(completed / len(lessons_with_status) * 100)


@student_bp.route("/")
@login_required(role="student")
def dashboard(account):
    celebrate = request.args.get("celebrate")

    if not account["course"]:
        return render_template("student/dashboard.html", account=account, lessons_with_status=[], progress=0, celebrate=celebrate)

    lessons_with_status = get_student_lessons_with_status(account["id"], account["course"])
    progress = _progress_percent(lessons_with_status)

    return render_template(
        "student/dashboard.html",
        account=account,
        lessons_with_status=lessons_with_status,
        progress=progress,
        celebrate=celebrate,
    )


@student_bp.route("/profile")
@login_required(role="student")
def profile(account):
    stats = get_student_stats(account["id"])

    progress = 0
    if account["course"]:
        lessons_with_status = get_student_lessons_with_status(account["id"], account["course"])
        progress = _progress_percent(lessons_with_status)

    return render_template(
        "student/profile.html",
        account=account,
        stats=stats,
        progress=progress,
    )


@student_bp.route("/lessons/<int:lesson_id>")
@login_required(role="student")
def lesson_view(account, lesson_id):
    lessons_with_status = get_student_lessons_with_status(account["id"], account["course"] or "")
    entry = next((e for e in lessons_with_status if e["lesson"]["id"] == lesson_id), None)

    if entry is None or entry["status"] == "locked":
        flash("Цей урок ще недоступний", "error")
        return redirect(url_for("student.dashboard"))

    assignments = get_assignments_by_lesson(lesson_id)
    submissions = get_submissions_for_student(account["id"], lesson_id)
    assignment_options = {a["id"]: get_assignment_options(a) for a in assignments}

    return render_template(
        "student/lesson_view.html",
        account=account,
        lesson=entry["lesson"],
        status=entry["status"],
        assignments=assignments,
        submissions=submissions,
        assignment_options=assignment_options,
        celebrate=request.args.get("celebrate"),
    )


@student_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@login_required(role="student")
def complete_lesson(account, lesson_id):
    lessons_with_status = get_student_lessons_with_status(account["id"], account["course"] or "")
    entry = next((e for e in lessons_with_status if e["lesson"]["id"] == lesson_id), None)

    if entry is None or entry["status"] == "locked":
        flash("Цей урок ще недоступний", "error")
        return redirect(url_for("student.dashboard"))

    mark_lesson_completed(account["id"], lesson_id)

    return redirect(url_for("student.dashboard", celebrate=lesson_id))


@student_bp.route("/assignments/<int:assignment_id>/submit", methods=["POST"])
@login_required(role="student")
def submit(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("student.dashboard"))

    if assignment["type"] == "quiz":
        options = get_assignment_options(assignment)
        selected_raw = request.form.get("selected_option")

        if selected_raw is None or not selected_raw.isdigit() or not (0 <= int(selected_raw) < len(options)):
            flash("Оберіть варіант відповіді", "error")
            return redirect(url_for("student.lesson_view", lesson_id=assignment["lesson_id"]))

        selected_index = int(selected_raw)
        is_correct = selected_index == assignment["correct_option"]

        submit_quiz_answer(account["id"], assignment_id, options[selected_index], is_correct)

        flash("Правильна відповідь! 🎉" if is_correct else "Неправильно, спробуйте ще раз", "success" if is_correct else "error")

        return redirect(url_for("student.lesson_view", lesson_id=assignment["lesson_id"], celebrate="quiz" if is_correct else None))

    answer_text = request.form.get("answer_text", "").strip()

    if not answer_text:
        flash("Введіть відповідь перед відправкою", "error")
        return redirect(url_for("student.lesson_view", lesson_id=assignment["lesson_id"]))

    submit_assignment(account["id"], assignment_id, answer_text)
    flash("Відповідь надіслано на перевірку", "success")

    return redirect(url_for("student.lesson_view", lesson_id=assignment["lesson_id"]))
