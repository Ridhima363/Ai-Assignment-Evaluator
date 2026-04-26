import json
import os
import re
import subprocess
import zipfile
import autopep8
from flask import Flask, render_template, redirect, url_for, request, flash, Response
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import firebase_admin
from firebase_admin import credentials, firestore, auth
import random
import string
import base64
from google.cloud import storage
import tempfile
import time
import fitz
from werkzeug.utils import secure_filename
from python_code_evaluation import runp
from c_code_evaluation import runc
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Initialize Flask App
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'your_secret_key'
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize Firestore
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, name, email, role):
        self.id = user_id
        self.name = name
        self.email = email
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    student_ref = db.collection("students").document(user_id).get()
    teacher_ref = db.collection("teachers").document(user_id).get()

    if student_ref.exists:
        user_data = student_ref.to_dict()
        return User(user_id, user_data['name'], user_data['email'], "student")
    elif teacher_ref.exists:
        user_data = teacher_ref.to_dict()
        return User(user_id, user_data['name'], user_data['email'], "teacher")
    return None

@app.before_request
def ensure_role():
    if current_user.is_authenticated and not hasattr(current_user, "role"):
        user = load_user(current_user.id)
        if user:
            current_user.role = user.role

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        if len(password) < 6:
            flash("Error: Password must be at least 6 characters long.", "danger")
            return redirect(url_for("signup"))

        try:
            auth.get_user_by_email(email)
            flash("Error: Email already in use. Please login instead.", "danger")
            return redirect(url_for("login"))
        except firebase_admin.auth.UserNotFoundError:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            user = auth.create_user(email=email, password=password)
            collection_name = "students" if role == "student" else "teachers"
            db.collection(collection_name).document(user.uid).set({
                "name": name,
                "email": email,
                "role": role,
                "password": hashed_password
            })
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            return redirect(url_for("signup"))
    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        student_docs = db.collection('students').where("email", "==", email).stream()
        teacher_docs = db.collection('teachers').where("email", "==", email).stream()

        user_data = None
        user_id = None
        user_role = None

        for doc in student_docs:
            user_data = doc.to_dict()
            user_id = doc.id
            user_role = "student"
            break

        for doc in teacher_docs:
            if not user_data:
                user_data = doc.to_dict()
                user_id = doc.id
                user_role = "teacher"
                break

        if user_data:
            try:
                user_record = auth.get_user_by_email(email)
                if bcrypt.check_password_hash(user_data["password"], password):
                    user = User(user_id, user_data['name'], email, user_role)
                    login_user(user)
                    return redirect(url_for('student_dashboard') if user_role == "student" else url_for('teacher_dashboard'))
                else:
                    flash('Invalid password. Please try again.', 'danger')
            except firebase_admin.auth.UserNotFoundError:
                flash('User not found. Please sign up first.', 'danger')
            except Exception as e:
                flash(f'Error: {e}', 'danger')
        else:
            flash('Login unsuccessful. Check email and password.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('student_dashboard') if current_user.role == "student" else url_for('teacher_dashboard'))

def generate_subject_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))




@app.route('/teacher_dashboard', methods=['GET', 'POST'])
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        return redirect(url_for('dashboard'))

    subjects = list(
        db.collection('subjects').where(filter=firestore.FieldFilter("teacher_id", "==", current_user.id)).stream())
    subject_list = [{**doc.to_dict(), 'id': doc.id} for doc in subjects]

    selected_subject = None
    first_accurate = None
    accurate_but_late = []
    incorrect = []
    show_evaluation = False

    if request.method == 'POST':
        if 'subject_code' in request.form:
            selected_subject_code = request.form.get('subject_code')
            selected_subject = next((s for s in subject_list if s['subject_code'] == selected_subject_code), None)
            if selected_subject:
                show_evaluation = True
                teacher_doc = db.collection("teachers").document(current_user.id).get()
                teacher_data = teacher_doc.to_dict()
                base_pdf_base64 = teacher_data.get("base_pdfs", {}).get(selected_subject_code, {}).get("pdf_base64")

                if not base_pdf_base64:
                    flash("Error: Base PDF not found for this subject.", "danger")
                    return redirect(url_for('teacher_dashboard'))

                base_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                base_temp.write(base64.b64decode(base_pdf_base64))
                base_temp.close()

                subject_language = selected_subject.get('language', 'python')

                all_students = db.collection('students').stream()
                submissions = []
                temp_dir = tempfile.mkdtemp()

                base_doc = fitz.open(base_temp.name)
                base_text = "".join(page.get_text("text") for page in base_doc)
                base_doc.close()

                for student in all_students:
                    student_data = student.to_dict()
                    student_id = student.id
                    enrolled_subjects = student_data.get("enrolled_subjects", [])
                    if selected_subject_code in enrolled_subjects:
                        submission = student_data.get("submitted_assignments", {}).get(selected_subject_code, {})
                        if submission:
                            student_pdf_base64 = submission.get("pdf_base64")
                            if student_pdf_base64:
                                student_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                                student_temp.write(base64.b64decode(student_pdf_base64))
                                student_temp.close()

                                student_doc = fitz.open(student_temp.name)
                                student_text = "".join(page.get_text("text") for page in student_doc)
                                student_doc.close()

                                if subject_language == 'python':
                                    student_text = student_text.replace('“', '"').replace('”', '"')
                                    student_text = re.sub(r'^\s*|\s*$', '', student_text)
                                    file_extension = '.py'
                                else:  # C
                                    student_text = student_text.replace('prinƞ', 'printf').replace('print',
                                                                                                   'printf')  # Fix print to printf
                                    student_text = student_text.replace('“', '"').replace('”', '"')
                                    student_text = re.sub(r'^\s*|\s*$', '', student_text)
                                    # Remove Q1), Q2), etc., labels
                                    student_text = re.sub(r'Q\d+\)\s*', '', student_text)
                                    lines = student_text.split('\n')
                                    for i, line in enumerate(lines):
                                        line = line.strip()
                                        if line and not line.endswith(';') and not line.endswith(
                                                '{') and not line.endswith('}') and not line.startswith('#'):
                                            lines[i] = line + ';'
                                    student_text = '\n'.join(lines)
                                    file_extension = '.c'


                                student_file = os.path.join(temp_dir, f"{student_id}{file_extension}")
                                with open(student_file, 'w', encoding='utf-8') as f:
                                    f.write(student_text)

                                evaluation_result = runp(base_temp.name,
                                                         student_file) if subject_language == 'python' else runc(
                                    base_temp.name, student_temp.name)
                                submission_time = submission.get('timestamp')
                                submission_time_str = submission_time.strftime(
                                    '%B %d, %Y, %I:%M %p') if submission_time else "N/A"
                                is_100_accurate = "❌" not in evaluation_result
                                student_submission = {
                                    'student_name': student_data.get('name', 'Unknown'),
                                    'student_id': student_id,
                                    'submission_time': submission_time,
                                    'submission_time_str': submission_time_str,
                                    'evaluation_result': evaluation_result,
                                    'is_100_accurate': is_100_accurate,
                                    'code_file': student_file
                                }
                                submissions.append(student_submission)
                                os.remove(student_temp.name)

                os.remove(base_temp.name)

                # Sort submissions by time and categorize
                submissions.sort(key=lambda x: x['submission_time'] or firestore.SERVER_TIMESTAMP)

                # Categorize all submissions
                for sub in submissions:
                    if sub['is_100_accurate'] and not first_accurate:
                        first_accurate = sub
                    elif sub['is_100_accurate']:
                        accurate_but_late.append(sub)
                    else:
                        incorrect.append(sub)


                # Run JPlag if there’s at least one accurate submission to compare
                if first_accurate and accurate_but_late:
                    jplag_result_dir = tempfile.mkdtemp()
                    jplag_path = os.path.join(os.path.dirname(__file__), "jplag.jar")
                    if not os.path.exists(jplag_path):
                        flash("Error: JPlag JAR file not found.", "danger")
                    else:
                        jplag_language = 'python3' if subject_language == 'python' else 'cpp'
                        cmd = [
                            "java", "-jar", jplag_path,
                            "-l", jplag_language,
                            temp_dir,
                            "-r", os.path.join(jplag_result_dir, "results.zip"),
                            "-m", "0.50",
                            "-t", "2",
                            "--mode=RUN"
                        ]
                        try:
                            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                    text=True)
                            if result.returncode != 0:  # Only check return code
                                raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout,
                                                                    stderr=result.stderr)

                            # Extract overview.json from ZIP
                            zip_path = os.path.join(jplag_result_dir, "results.zip")
                            if os.path.exists(zip_path):
                                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                    zip_ref.extract("overview.json", jplag_result_dir)
                                result_json_path = os.path.join(jplag_result_dir, "overview.json")
                                if os.path.exists(result_json_path):
                                    with open(result_json_path, 'r', encoding='utf-8') as f:
                                        jplag_results = json.load(f)
                                    for sub in accurate_but_late:
                                        first_file_name = os.path.basename(first_accurate['code_file'])
                                        sub_file_name = os.path.basename(sub['code_file'])
                                        plagiarism_percentage = 0.0
                                        for match in jplag_results.get('top_comparisons', []):
                                            if (match.get('first_submission') == first_file_name and match.get(
                                                    'second_submission') == sub_file_name) or \
                                                    (match.get('first_submission') == sub_file_name and match.get(
                                                        'second_submission') == first_file_name):
                                                plagiarism_percentage = float(match['similarities']['AVG']) * 100
                                                break
                                        sub['plagiarism_percentage'] = round(plagiarism_percentage, 2)
                                else:
                                    flash(
                                        "Warning: Plagiarism results not generated, displaying evaluation without plagiarism.",
                                        "warning")
                            else:
                                flash(
                                    "Warning: Plagiarism results not generated, displaying evaluation without plagiarism.",
                                    "warning")

                        except subprocess.CalledProcessError as e:

                            flash(
                                f"Warning: Plagiarism check failed. Details: {e.stderr}. Displaying evaluation without plagiarism.",
                                "warning")
                        except FileNotFoundError as e:
                            flash(
                                "Warning: Java not found or JPlag execution failed. Displaying evaluation without plagiarism.",
                                "warning")

                    # Cleanup
                    for sub in submissions:
                        if os.path.exists(sub['code_file']):
                            os.remove(sub['code_file'])
                    if os.path.exists(temp_dir):
                        os.rmdir(temp_dir)
                    for root, dirs, files in os.walk(jplag_result_dir, topdown=False):
                        for file in files:
                            os.remove(os.path.join(root, file))
                        for dir in dirs:
                            os.rmdir(os.path.join(root, dir))
                    if os.path.exists(jplag_result_dir):
                        os.rmdir(jplag_result_dir)

        elif 'subject_name' in request.form:
            subject_name = request.form['subject_name']
            language = request.form.get('language', 'python')
            subject_code = generate_subject_code()
            file = request.files.get('file')
            if not file:
                flash("Please upload a base PDF for the course.", "danger")
                return redirect(url_for('teacher_dashboard'))
            file_base64 = base64.b64encode(file.read()).decode('utf-8')
            db.collection('subjects').document(subject_code).set({
                "subject_name": subject_name,
                "subject_code": subject_code,
                "teacher_id": current_user.id,
                "language": language
            })
            teacher_ref = db.collection("teachers").document(current_user.id)
            teacher_ref.set({
                "base_pdfs": {
                    subject_code: {
                        "pdf_base64": file_base64,
                        "subject_name": subject_name
                    }
                }
            }, merge=True)
            flash(f'Subject "{subject_name}" created successfully with code: {subject_code}', 'success')
            return redirect(url_for('teacher_dashboard'))

    return render_template('teacher_dashboard.html', name=current_user.name, subjects=subject_list,
                           selected_subject=selected_subject, first_accurate=first_accurate,
                           accurate_but_late=accurate_but_late, incorrect=incorrect, show_evaluation=show_evaluation)

@app.route('/student_dashboard', methods=['GET', 'POST'])
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('dashboard'))

    enrolled_subjects = []
    submitted_assignments = {}
    student_ref = db.collection("students").document(current_user.id)
    student_data = student_ref.get().to_dict()

    if student_data:
        enrolled_subjects = student_data.get("enrolled_subjects", [])
        submitted_assignments = student_data.get("submitted_assignments", {})

    if request.method == 'POST':
        subject_code = request.form.get('subject_code').strip()
        subject_ref = db.collection('subjects').document(subject_code).get()
        if subject_ref.exists:
            subject_data = subject_ref.to_dict()
            if subject_code not in enrolled_subjects:
                enrolled_subjects.append(subject_code)
                student_ref.update({"enrolled_subjects": firestore.ArrayUnion([subject_code])})
            return redirect(url_for('submit_assignment', subject_code=subject_code))
        else:
            flash('Invalid subject code. Please try again.', 'danger')

    return render_template('student_dashboard.html', name=current_user.name, enrolled_subjects=enrolled_subjects, submitted_assignments=submitted_assignments)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/submit_assignment', methods=['GET', 'POST'])
@login_required
def submit_assignment():
    if request.method == 'GET':
        subject_code = request.args.get('subject_code', '')
        return render_template('submit_assignment.html', subject_code=subject_code)

    if current_user.role != 'student':
        flash("Error: Only students can submit assignments.", "danger")
        return redirect(url_for('dashboard'))

    student_id = current_user.id
    subject_code = request.form.get('subject_code')
    name = request.form.get('name')
    file = request.files.get('file')

    if not student_id or not subject_code or not file:
        flash("Error: Missing required fields.", "danger")
        return redirect(url_for('submit_assignment', subject_code=subject_code))

    student_ref = db.collection("students").document(student_id)
    student_doc = student_ref.get()
    if student_doc.exists:
        student_data = student_doc.to_dict()
        submitted_assignments = student_data.get("submitted_assignments", {})
        if subject_code in submitted_assignments:
            flash("Error: You have already submitted an assignment for this subject.", "danger")
            return redirect(url_for('student_dashboard'))

    file_base64 = base64.b64encode(file.read()).decode('utf-8')

    try:
        if student_doc.exists:
            student_ref.update({
                f"submitted_assignments.{subject_code}": {
                    "name": name,
                    "pdf_base64": file_base64,
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
            })
        else:
            student_ref.set({
                "submitted_assignments": {
                    subject_code: {
                        "name": name,
                        "pdf_base64": file_base64,
                        "timestamp": firestore.SERVER_TIMESTAMP
                    }
                }
            }, merge=True)
        flash("Assignment submitted successfully!", "success")
    except Exception as e:
        flash("Error: Failed to submit assignment.", "danger")

    return redirect(url_for('student_dashboard'))

@app.route('/get_pdf/<student_id>/<subject_code>')
@login_required
def get_pdf(student_id, subject_code):
    student_ref = db.collection("students").document(student_id).get()
    if not student_ref.exists:
        return "No file found", 404
    student_data = student_ref.to_dict()
    pdf_base64 = student_data.get("submitted_assignments", {}).get(subject_code, {}).get("pdf_base64")
    if not pdf_base64:
        return "No file found", 404
    pdf_data = base64.b64decode(pdf_base64)
    return Response(pdf_data, mimetype='application/pdf')

@app.route('/get_base_pdf/<subject_code>')
@login_required
def get_base_pdf(subject_code):
    teacher_ref = db.collection("teachers").document(current_user.id).get()
    if not teacher_ref.exists:
        return "No base PDF found", 404
    teacher_data = teacher_ref.to_dict()
    base_pdfs = teacher_data.get("base_pdfs", {})
    if subject_code not in base_pdfs:
        return "No base PDF found for this subject", 404
    pdf_base64 = base_pdfs[subject_code]["pdf_base64"]
    pdf_data = base64.b64decode(pdf_base64)
    return Response(pdf_data, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)