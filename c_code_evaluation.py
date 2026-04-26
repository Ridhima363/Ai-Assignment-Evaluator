# c_code_evaluation.py
import os
import tempfile
import subprocess
import fitz  # PyMuPDF for PDF text extraction
import re
import shutil

def runc(base_pdf_path, student_pdf_path):
    def fix_encoding_issues(code):
        code = re.sub(r"\(cid:\d+\)", "", code)
        code = code.replace("ƞ", "f").replace("ﬀ", "ff")
        code = code.replace("‘", "'").replace("’", "'")
        code = code.replace("“", "\"").replace("”", "\"")
        code = re.sub(r"prin[a-zA-Z]*\(", "printf(", code)
        return code

    def extract_text_from_pdf(pdf_path):
        if not os.path.isfile(pdf_path):
            return ""
        text = ""
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text")
        return text.strip() if text else ""

    def extract_questions(text):
        pattern = r'(Q\d+\))\s*(.*?)(?=Q\d+\)|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        return {q_num: content.strip() for q_num, content in matches}

    def clean_c_code(code):
        code = re.sub(r'^Q\d+\)\s*', '', code, 1)  # Remove Q#) at the start
        return fix_encoding_issues(code.strip())

    def normalize_output(text):
        # Normalize newlines to \n and strip trailing/leading whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def run_c_code(code, timeout=5):
        try:
            if not code:
                return "", "Error: No valid code to execute"

            code = clean_c_code(code)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False, encoding="utf-8") as temp_file:
                temp_file.write(code)
                temp_c_file = temp_file.name

            exe_file = temp_c_file.replace(".c", ".exe")

            gcc_path = shutil.which("gcc")
            if not gcc_path:
                return "", "Error: GCC compiler not found"

            compile_result = subprocess.run([gcc_path, temp_c_file, "-o", exe_file],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if compile_result.returncode != 0:
                return "", f"Compilation Error:\n{compile_result.stderr}"

            result = subprocess.run([exe_file], capture_output=True, text=True, timeout=timeout)

            try:
                os.remove(exe_file)
            except OSError:
                pass
            finally:
                os.remove(temp_c_file)

            return normalize_output(result.stdout), normalize_output(result.stderr)

        except subprocess.TimeoutExpired:
            return "", "Error: Code execution timed out"
        except Exception as e:
            return "", f"Unexpected Error: {str(e)}"

    def evaluate_c_answers(base_questions, student_questions):
        results = []
        for q_num in base_questions:
            if q_num not in student_questions:
                results.append(f"{q_num}: ❌ Missing")
                continue

            expected_output = normalize_output(base_questions[q_num])
            student_code = student_questions[q_num]
            student_output, error = run_c_code(student_code)

            if error:
                results.append(f"{q_num}: ❌ Student code execution error: {error}")
            elif student_output == expected_output:
                results.append(f"{q_num}: ✅ Student answer is correct!")
            else:
                results.append(f"{q_num}: ❌ Incorrect answer!\nExpected:\n{expected_output}\nGot:\n{student_output}")

        for q_num in student_questions:
            if q_num not in base_questions:
                results.append(f"{q_num}: ❌ Extra (Not in base PDF)")

        return "\n".join(results) if results else "❌ No questions detected"

    base_text = extract_text_from_pdf(base_pdf_path)
    student_text = extract_text_from_pdf(student_pdf_path)

    if not base_text or not student_text:
        return "❌ Error: Missing content for comparison."

    base_questions = extract_questions(base_text)
    student_questions = extract_questions(student_text)

    return evaluate_c_answers(base_questions, student_questions)