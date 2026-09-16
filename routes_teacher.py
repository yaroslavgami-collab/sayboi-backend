from flask import Blueprint, render_template, request, redirect, url_for, flash

from auth import login_required
from database import (
    list_all_lessons,
    get_lesson,
    create_lesson,
    update_lesson,
    delete_lesson,
    get_assignments_by_lesson,
    create_assignment,
    update_assignment,
    delete_assignment,
    get_assignment,
    list_students,
    get_student_lessons_with_status,
    get_submissions_for_student,
    get_submissions_for_assignment,
    grade_submission,
)

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")

COURSES = ["starter", "plus", "premium"]


@teacher_bp.route("/")
@login_required(role="teacher")
def dashboard(account):
    lessons = list_all_lessons()

    lessons_by_course = {course: [] for course in COURSES}

    for lesson in lessons:
        lessons_by_course.setdefault(lesson["course"], []).append(lesson)

    students = list_students()

    return render_template(
        "teacher/dashboard.html",
        account=account,
        lessons_by_course=lessons_by_course,
        courses=COURSES,
        students_count=len(students),
    )


@teacher_bp.route("/lessons/new", methods=["GET", "POST"])
@login_required(role="teacher")
def new_lesson(account):
    if request.method == "POST":
        course = request.form.get("course")
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        video_url = request.form.get("video_url", "").strip() or None
        scheduled_at = request.form.get("scheduled_at", "").strip() or None
        order_index = int(request.form.get("order_index") or 0)

        if not title or course not in COURSES:
            flash("Заповніть назву та оберіть курс", "error")
            return render_template("teacher/lesson_form.html", account=account, courses=COURSES, lesson=None)

        lesson_id = create_lesson(course, title, content, video_url, scheduled_at, order_index)

        flash("Урок створено", "success")
        return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

    return render_template("teacher/lesson_form.html", account=account, courses=COURSES, lesson=None)


@teacher_bp.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@login_required(role="teacher")
def edit_lesson(account, lesson_id):
    lesson = get_lesson(lesson_id)

    if lesson is None:
        flash("Урок не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    if request.method == "POST":
        course = request.form.get("course")
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "")
        video_url = request.form.get("video_url", "").strip() or None
        scheduled_at = request.form.get("scheduled_at", "").strip() or None
        order_index = int(request.form.get("order_index") or 0)
        is_published = request.form.get("is_published") == "on"

        if not title or course not in COURSES:
            flash("Заповніть назву та оберіть курс", "error")
            return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

        update_lesson(lesson_id, course, title, content, video_url, scheduled_at, order_index, is_published)

        flash("Зміни збережено", "success")
        return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))

    assignments = get_assignments_by_lesson(lesson_id)

    return render_template(
        "teacher/lesson_form.html",
        account=account,
        courses=COURSES,
        lesson=lesson,
        assignments=assignments,
    )


@teacher_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required(role="teacher")
def remove_lesson(account, lesson_id):
    delete_lesson(lesson_id)
    flash("Урок видалено", "success")
    return redirect(url_for("teacher.dashboard"))


@teacher_bp.route("/lessons/<int:lesson_id>/assignments/new", methods=["POST"])
@login_required(role="teacher")
def new_assignment(account, lesson_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "")
    order_index = int(request.form.get("order_index") or 0)

    if title:
        create_assignment(lesson_id, title, description, order_index)
        flash("Завдання додано", "success")
    else:
        flash("Вкажіть назву завдання", "error")

    return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))


@teacher_bp.route("/assignments/<int:assignment_id>/edit", methods=["POST"])
@login_required(role="teacher")
def edit_assignment(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "")
    order_index = int(request.form.get("order_index") or 0)

    if title:
        update_assignment(assignment_id, title, description, order_index)
        flash("Завдання оновлено", "success")

    return redirect(url_for("teacher.edit_lesson", lesson_id=assignment["lesson_id"]))


@teacher_bp.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
@login_required(role="teacher")
def remove_assignment(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    lesson_id = assignment["lesson_id"]
    delete_assignment(assignment_id)

    flash("Завдання видалено", "success")
    return redirect(url_for("teacher.edit_lesson", lesson_id=lesson_id))


@teacher_bp.route("/students")
@login_required(role="teacher")
def students(account):
    all_students = list_students()

    return render_template("teacher/students.html", account=account, students=all_students)


@teacher_bp.route("/students/<int:student_id>")
@login_required(role="teacher")
def student_detail(account, student_id):
    students_list = list_students()
    student = next((s for s in students_list if s["id"] == student_id), None)

    if student is None:
        flash("Учня не знайдено", "error")
        return redirect(url_for("teacher.students"))

    lessons_with_status = []

    if student["course"]:
        lessons_with_status = get_student_lessons_with_status(student_id, student["course"])

    for entry in lessons_with_status:
        entry["assignments"] = get_assignments_by_lesson(entry["lesson"]["id"])
        entry["submissions"] = get_submissions_for_student(student_id, entry["lesson"]["id"])

    return render_template(
        "teacher/student_detail.html",
        account=account,
        student=student,
        lessons_with_status=lessons_with_status,
    )


@teacher_bp.route("/assignments/<int:assignment_id>/submissions")
@login_required(role="teacher")
def assignment_submissions(account, assignment_id):
    assignment = get_assignment(assignment_id)

    if assignment is None:
        flash("Завдання не знайдено", "error")
        return redirect(url_for("teacher.dashboard"))

    submissions = get_submissions_for_assignment(assignment_id)

    return render_template(
        "teacher/submissions.html",
        account=account,
        assignment=assignment,
        submissions=submissions,
    )


@teacher_bp.route("/submissions/<int:submission_id>/grade", methods=["POST"])
@login_required(role="teacher")
def grade(account, submission_id):
    score = request.form.get("score", "").strip()
    feedback = request.form.get("feedback", "")
    redirect_to = request.form.get("redirect_to") or url_for("teacher.dashboard")

    grade_submission(submission_id, int(score) if score else None, feedback)

    flash("Оцінку збережено", "success")
    return redirect(redirect_to)
