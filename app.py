from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify
from connections import SessionLocal
from models import User,StudentProfile,Lesson,Course,Module,LessonProgress
from utils_docx import parse_docx_lesson
import json

from datetime import datetime
 

import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_DOCX_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"docx"}


def allowed_docx(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload_lesson/<int:module_id>", methods=["GET", "POST"])
def upload_lesson(module_id):
    db = SessionLocal()
    try:
        module = db.query(Module).filter_by(id=module_id).first()
        if not module:
            flash("Module not found")
            return redirect(url_for("teacher_dashboard"))

        if request.method == "POST":
            file = request.files.get("lesson_file")
            title = request.form.get("title", "").strip()

            if not file or file.filename == "":
                flash("Please choose a DOCX file")
                return redirect(request.url)

            if not allowed_docx(file.filename):
                flash("Only .docx files are allowed")
                return redirect(request.url)

            os.makedirs(UPLOAD_DOCX_FOLDER, exist_ok=True)

            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_DOCX_FOLDER, filename)
            file.save(filepath)

            lesson_data, practical_task = parse_docx_lesson(filepath)

            if not title:
                title = os.path.splitext(filename)[0]

            last_lesson = (
                db.query(Lesson)
                .filter_by(module_id=module_id)
                .order_by(Lesson.lesson_order.desc())
                .first()
            )

            next_order = 1 if not last_lesson else last_lesson.lesson_order + 1

            teacher_id = session.get("user_id")
            if not teacher_id:
                flash("Please login first")
                return redirect(url_for("login"))

            lesson = Lesson(
                teacher_id=teacher_id,
                module_id=module_id,
                title=title,
                content=None,
                lesson_data=json.dumps(lesson_data),
                practical_task=json.dumps(practical_task),
                lesson_order=next_order
            )

            db.add(lesson)
            db.commit()

            flash("Lesson uploaded successfully")
            return redirect(url_for("view_lesson", lesson_id=lesson.id))

        return render_template("teacher/upload_lesson.html", module=module)

    finally:
        db.close()

@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Check passwords match
        if password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for("register"))

        db = SessionLocal()
        try:
            existing_user = db.query(User).filter_by(email=email).first()

            if existing_user:
                flash("Email already exists")
                return redirect(url_for("register"))

            new_user = User(
                email=email,
                password=password,
                role="student"
            )

            db.add(new_user)
            db.commit()

            flash("Account created successfully. Please login.")
            return redirect(url_for("login"))
        finally:
            db.close()

    return render_template("users/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = SessionLocal()
        try:
            user = db.query(User).filter_by(email=email).first()

            if user and user.password == password:
                session["user_id"] = user.id
                session["role"] = user.role

                flash("Login successful")

                if user.role == "admin":
                    return redirect(url_for("admin_dashboard"))
                
                if user.role == "teacher":
                    return redirect(url_for("teacher_dashboard"))

                elif user.role == "student":
                    profile = db.query(StudentProfile).filter_by(user_id=user.id).first()

                    if profile:
                        return redirect(url_for("student_dashboard"))
                    else:
                        return redirect(url_for("complete_profile"))
            else:
                flash("Invalid email or password")
                return redirect(url_for("login"))
        finally:
            db.close()

    return render_template("login.html")


@app.route("/complete_profile", methods=["GET", "POST"])
def complete_profile():
    if "user_id" not in session:
        flash("Please login first")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        existing_profile = db.query(StudentProfile).filter_by(user_id=session["user_id"]).first()

        if existing_profile:
            return redirect(url_for("student_dashboard"))

        courses = db.query(Course).order_by(Course.name.asc()).all()

        if request.method == "POST":
            full_name = request.form["full_name"]
            phone_number = request.form["phone_number"]
            guardian_number = request.form["guardian_number"]
            admission_number = request.form["admission_number"]
            course_id = request.form["course_id"]

            profile = StudentProfile(
                user_id=session["user_id"],
                full_name=full_name,
                phone_number=phone_number,
                guardian_number=guardian_number,
                admission_number=admission_number,
                course_id=course_id
            )

            db.add(profile)
            db.commit()

            flash("Profile completed successfully")
            return redirect(url_for("student_dashboard"))

        return render_template("users/complete_profile.html", courses=courses)
    finally:
        db.close()


@app.route("/student_dashboard")
def student_dashboard():
    if "user_id" not in session:
        flash("Please login first")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        profile = db.query(StudentProfile).filter_by(user_id=session["user_id"]).first()

        if not profile:
            flash("Please complete your profile first")
            return redirect(url_for("complete_profile"))

        modules = db.query(Module).filter_by(course_id=profile.course_id).order_by(Module.name.asc()).all()

        return render_template(
            "users/student_dashboard.html",
            profile=profile,
            modules=modules
        )
    finally:
        db.close()

@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied")
        return redirect(url_for("login"))

    return render_template("admin/admin_dashboard.html")

@app.route("/add_course", methods=["GET", "POST"])
def add_course():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        if request.method == "POST":
            name = request.form["name"]

            existing_course = db.query(Course).filter_by(name=name).first()
            if existing_course:
                flash("Course already exists")
                return redirect(url_for("add_course"))

            new_course = Course(name=name)
            db.add(new_course)
            db.commit()

            flash("Course added successfully")
            return redirect(url_for("add_course"))

        courses = db.query(Course).order_by(Course.name.asc()).all()
        return render_template("admin/add_course.html", courses=courses)

    finally:
        db.close()

@app.route("/add_teacher", methods=["GET", "POST"])
def add_teacher():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]

            if password != confirm_password:
                flash("Passwords do not match")
                return redirect(url_for("add_teacher"))

            existing_teacher = db.query(User).filter_by(email=email).first()
            if existing_teacher:
                flash("Email already exists")
                return redirect(url_for("add_teacher"))

            new_teacher = User(
                email=email,
                password=password,
                role="teacher"
            )

            db.add(new_teacher)
            db.commit()

            flash("Teacher added successfully")
            return redirect(url_for("add_teacher"))

        teachers = db.query(User).filter_by(role="teacher").order_by(User.id.desc()).all()
        return render_template("admin/add_teacher.html", teachers=teachers)

    finally:
        db.close()


@app.route("/teacher_dashboard")
def teacher_dashboard():
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Access denied")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        modules = db.query(Module).order_by(Module.id.desc()).all()
        return render_template("teacher/teacher_dashboard.html", modules=modules)
    finally:
        db.close()


# import json  # 🔥 add this at the top of your file

# @app.route("/add_lesson/<int:module_id>", methods=["GET", "POST"])
# def add_lesson(module_id):
#     if "user_id" not in session or session.get("role") != "teacher":
#         flash("Access denied")
#         return redirect(url_for("login"))

#     db = SessionLocal()
#     try:
#         module = db.query(Module).filter_by(id=module_id).first()

#         if not module:
#             flash("Module not found")
#             return redirect(url_for("teacher_dashboard"))

#         if request.method == "POST":
#             title = request.form["title"]

#             # ✅ NEW FIELDS
#             introduction = request.form["introduction"]
#             outline = request.form["outline"]

#             chapter_titles = request.form.getlist("chapter_title[]")
#             chapter_contents = request.form.getlist("chapter_content[]")

#             # ✅ Build chapters list
#             chapters = []
#             for i in range(len(chapter_titles)):
#                 chapters.append({
#                     "title": chapter_titles[i],
#                     "content": chapter_contents[i]
#                 })

#             # ✅ Combine everything
#             content_data = {
#                 "introduction": introduction,
#                 "outline": outline,
#                 "chapters": chapters
#             }

#             lesson = Lesson(
#                 teacher_id=session["user_id"],
#                 module_id=module.id,
#                 title=title,
#                 content=json.dumps(content_data),  # 🔥 STORE JSON
#                 practical_task=request.form["practical_task"],
#                 lesson_order=request.form["lesson_order"]
#             )

#             db.add(lesson)
#             db.commit()

#             flash("Lesson added successfully")
#             return redirect(url_for("teacher_dashboard"))

#         return render_template("teacher/add_lesson.html", module=module)

#     finally:
#         db.close()
    
@app.route("/add_module", methods=["GET", "POST"])
def add_module():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        courses = db.query(Course).order_by(Course.name.asc()).all()

        if request.method == "POST":
            name = request.form["name"]
            course_id = request.form["course_id"]

            existing_module = db.query(Module).filter_by(name=name, course_id=course_id).first()
            if existing_module:
                flash("Module already exists for this course")
                return redirect(url_for("add_module"))

            new_module = Module(
                name=name,
                course_id=course_id
            )
            db.add(new_module)
            db.commit()

            flash("Module added successfully")
            return redirect(url_for("add_module"))

        modules = db.query(Module).order_by(Module.id.desc()).all()
        return render_template("admin/add_module.html", courses=courses, modules=modules)

    finally:
        db.close()

@app.route("/view_module_lessons/<int:module_id>")
def view_module_lessons(module_id):
    if "user_id" not in session:
        flash("Please login first")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        profile = db.query(StudentProfile).filter_by(user_id=session["user_id"]).first()

        if not profile:
            flash("Please complete your profile first")
            return redirect(url_for("complete_profile"))

        module = db.query(Module).filter_by(id=module_id, course_id=profile.course_id).first()

        if not module:
            flash("Module not found")
            return redirect(url_for("student_dashboard"))

        lessons = db.query(Lesson).filter_by(module_id=module.id).order_by(Lesson.lesson_order.asc()).all()

        return render_template("users/module_lessons.html", module=module, lessons=lessons, profile=profile)
    finally:
        db.close()

import json

@app.route("/view_lesson/<int:lesson_id>")
def view_lesson(lesson_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        lesson = db.query(Lesson).filter_by(id=lesson_id).first()

        if not lesson:
            flash("Lesson not found")
            return redirect(url_for("dashboard"))

        lesson_data = json.loads(lesson.lesson_data) if lesson.lesson_data else {
            "introduction": {"blocks": []},
            "outline": {"blocks": []},
            "chapters": []
        }

        practical_task = json.loads(lesson.practical_task) if lesson.practical_task else {
            "blocks": []
        }

        progress = db.query(LessonProgress).filter_by(
            user_id=session["user_id"],
            lesson_id=lesson.id
        ).first()

        saved_step = progress.current_step if progress else 0

        all_lessons = (
            db.query(Lesson)
            .filter_by(module_id=lesson.module_id)
            .order_by(Lesson.lesson_order.asc())
            .all()
        )

        previous_lesson = None
        next_lesson = None

        for i, item in enumerate(all_lessons):
            if item.id == lesson.id:
                if i > 0:
                    previous_lesson = all_lessons[i - 1]
                if i < len(all_lessons) - 1:
                    next_lesson = all_lessons[i + 1]
                break

        modules = (
            db.query(Module)
            .filter_by(course_id=lesson.module.course_id)
            .order_by(Module.id.asc())
            .all()
        )

        modules_with_lessons = []
        for module in modules:
            lessons = (
                db.query(Lesson)
                .filter_by(module_id=module.id)
                .order_by(Lesson.lesson_order.asc())
                .all()
            )
            modules_with_lessons.append({
                "module": module,
                "lessons": lessons
            })

        return render_template(
            "users/view_lesson.html",
            lesson=lesson,
            lesson_data=lesson_data,
            practical_task=practical_task,
            saved_step=saved_step,
            previous_lesson=previous_lesson,
            next_lesson=next_lesson,
            modules_with_lessons=modules_with_lessons
        )

    finally:
        db.close()
    
@app.route("/teacher_lessons")
def teacher_lessons():
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Access denied")
        return redirect(url_for("login"))

    db = SessionLocal()
    try:
        lessons = (
            db.query(Lesson)
            .filter_by(teacher_id=session["user_id"])
            .order_by(Lesson.created_at.desc())
            .all()
        )

        return render_template("teacher/teacher_lessons.html", lessons=lessons)
    finally:
        db.close()

@app.route("/save_lesson_progress", methods=["POST"])
def save_lesson_progress():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    db = SessionLocal()
    try:
        data = request.get_json()
        lesson_id = data.get("lesson_id")
        current_step = int(data.get("current_step", 0))
        completed = 1 if data.get("completed", False) else 0

        progress = db.query(LessonProgress).filter_by(
            user_id=session["user_id"],
            lesson_id=lesson_id
        ).first()

        if progress:
            progress.current_step = current_step
            progress.completed = completed
            progress.updated_at = datetime.utcnow()
        else:
            progress = LessonProgress(
                user_id=session["user_id"],
                lesson_id=lesson_id,
                current_step=current_step,
                completed=completed,
                updated_at=datetime.utcnow()
            )
            db.add(progress)

        db.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        db.close()


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for("login"))




if __name__ == "__main__":
    app.run(debug=True)