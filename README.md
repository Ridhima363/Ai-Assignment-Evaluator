# 🧠 AI-Based Assignment Evaluator System

The **AI-Based Assignment Evaluator System** is a web platform built using **Flask** and **Firebase** that helps teachers automatically manage and evaluate programming assignments.  

Teachers can create subjects, upload assignment questions and base solutions (PDF), and the system automatically checks student submissions. Students can enroll in subjects using a subject code, submit their assignments in PDF format, and instantly receive results and feedback.

This system supports **Python** and **C programming assignments**, and also includes **plagiarism detection** using JPlag.

---

## ✨ Key Features

### 🤖 Automatic Assignment Evaluation
- Extracts code from student PDF submissions
- Executes student programs safely using subprocess
- Matches student output with teacher’s base output
- Uses text similarity techniques (TF-IDF + Cosine Similarity) for better comparison

### 🕵️ Plagiarism Detection (JPlag)
- Detects similarity between student codes
- Generates plagiarism percentage
- Helps teacher identify copied submissions easily

### 👨‍🏫 Teacher Dashboard
Teachers can:
- Create subjects with a subject code
- Upload base solution PDF (correct answer PDF)
- Upload assignment PDF questions
- View all student submissions
- Automatically categorize submissions into:
  - ✅ First Accurate
  - 🕒 Accurate but Late (with plagiarism %)
  - ❌ Incorrect

### 👨‍🎓 Student Panel
Students can:
- Register/Login using Firebase Authentication
- Join subjects using a subject code
- Upload their assignment solution in PDF format
- Track submission status and results

---

## 📌 Submission Categories

The system classifies submissions automatically:

- ✅ **First Accurate**  
  Student submitted correct output on the first attempt and within time.

- 🕒 **Accurate but Late**  
  Student output is correct, but submitted after deadline.  
  Plagiarism check is applied and similarity percentage is shown.

- ❌ **Incorrect**  
  Output mismatch, compilation error, runtime error, or wrong logic.

---

## 🛠 Tech Stack

| Module / Area          | Tools / Libraries |
|------------------------|------------------|
| Backend Framework      | Flask |
| Frontend Templates     | Jinja2 |
| Styling               | Tailwind CSS |
| Authentication         | Firebase Authentication |
| Database              | Firebase Firestore |
| PDF Extraction         | PyMuPDF (`fitz`) |
| Code Execution         | subprocess (Python), GCC (C) |
| Similarity Checking    | TF-IDF, Cosine Similarity |
| Plagiarism Detection   | JPlag |
| Code Formatting        | autopep8 |

---

## ⚙️ Installation & Setup

### ✅ Requirements
Before running the project, make sure you have:

- Python 3.9+
- Java Runtime Environment (JRE) *(for JPlag)*
- GCC Compiler *(for C code execution)*
- Firebase Project (Firestore + Authentication enabled)

---

🐍 Create Virtual Environment & Install Dependencies
python -m venv venv

# For Linux / macOS
source venv/bin/activate

# For Windows
venv\Scripts\activate

pip install -r requirements.txt

🔥 Firebase Setup
1.Go to Firebase Console
2.Create a new Firebase project
3.Enable:
Firestore Database
Authentication (Email/Password)
4.Download your Firebase service account key JSON
5.Rename it to:
firebase_config.json
6.Place it in the root folder of the project.

▶️ Run the Project
python app.py
Now open your browser and go to:

⚙️ How Evaluation Works
🔹 Python Assignment Checking
Code is extracted from student PDF
Code is cleaned/normalized
Program is executed using subprocess
Output is compared with teacher’s base output
Similarity is calculated using TF-IDF + cosine similarity for better matching

🔹 C Assignment Checking
C code is extracted from PDF
Minor fixes are applied (semicolon issues, formatting, etc.)
Code is compiled using GCC
Program output is matched with base output

🔹 Plagiarism Detection
Plagiarism checking is done using JPlag
JPlag checks token-level similarity between codes
System shows similarity percentage on teacher dashboard
Mostly applied when submission is correct but late

👩‍🏫 Teacher Workflow
Signup/Login from /signup or /login
Create a subject (Python/C)
Upload assignment PDF and base solution PDF
Share subject code with students
Open evaluation dashboard to view results and plagiarism %
👨‍🎓 Student Workflow
Signup/Login
Enter subject code to enroll
Upload assignment PDF submission
View result after evluation

📌 Important Notes
Only one submission per student per subject is allowed.
Student PDFs must follow proper formatting like:
Q1) <code>
Q2) <code>
JPlag requires Java to be installed.
C code execution requires GCC compiler.

🚀 Future Improvements (Optional)
Add support for more programming languages (Java, C++, JS)
Add AI-based feedback comments on code quality
Add deadline timer and multiple submission attempts
Add downloadable result report for students

📜 License
This project is developed for educational purposes.

👨‍💻 Developed By
Ridhima Agarwal
📌 BTech CSE Student | AI/ML Enthusiast
📧 Email: agarridhima05@gmail.com
