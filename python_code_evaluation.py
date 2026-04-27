import fitz
import re
import subprocess
import os
import tempfile
import textwrap

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = "".join(page.get_text("text") for page in doc)
    doc.close()
    return text

def normalize_code(code):
    """Normalize Python code by dedenting and enforcing consistent indentation."""
    lines = code.split('\n')
    lines = [line.rstrip() for line in lines if line.strip()]
    if not lines:
        return ""

    dedented_code = textwrap.dedent('\n'.join(lines))

    lines = dedented_code.split('\n')
    normalized_lines = []
    indent_level = 0
    prev_line_was_block_start = False

    for line in lines:
        stripped_line = line.lstrip()
        if not stripped_line:
            continue
        # If this line starts a new block (e.g., for, while, def) and follows a block,
        # reset indent if it’s not part of the previous block
        if (stripped_line.startswith('for ') or stripped_line.startswith('while ') or
            stripped_line.startswith('if ') or stripped_line.startswith('def ')) and not prev_line_was_block_start:
            indent_level = 0
        # Apply current indent level
        normalized_lines.append(' ' * (indent_level * 4) + stripped_line)
        # Update indent level for next line
        if stripped_line.endswith(':'):
            indent_level += 1
            prev_line_was_block_start = True
        else:
            prev_line_was_block_start = False

    return '\n'.join(normalized_lines)

def normalize_output(output):
    """Normalize output by stripping extra whitespace and standardizing newlines."""
    return '\n'.join(line.strip() for line in output.split('\n') if line.strip())

def runp(base_pdf_path, student_py_path):
    base_text = extract_text_from_pdf(base_pdf_path)
    with open(student_py_path, 'r', encoding='utf-8') as f:
        student_text = f.read()
    print(f"DEBUG: Base text:\n{base_text}")
    print(f"DEBUG: Student text:\n{student_text}")

    base_questions = dict(re.findall(r'(Q\d+\))\s*([^Q]+?(?=Q\d+\)|$))', base_text, re.DOTALL))
    student_questions = dict(re.findall(r'(Q\d+\))\s*([^Q]+?(?=Q\d+\)|$))', student_text, re.DOTALL))
    print(f"DEBUG: Base questions: {base_questions}")
    print(f"DEBUG: Student questions: {student_questions}")

    result = ""
    for q in base_questions:
        if q in student_questions:
            raw_code = student_questions[q].strip()
            raw_code = raw_code.replace('“', '"').replace('”', '"')
            normalized_code = normalize_code(raw_code)
            print(f"DEBUG: Raw code:\n{raw_code}")
            print(f"DEBUG: Normalized code:\n{normalized_code}")

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.py', dir=tempfile.gettempdir()).name
            try:
                with open(temp_file, "w", encoding='utf-8') as f:
                    f.write(normalized_code)
                # Add timeout to prevent infinite loops
                output = subprocess.check_output(["python", temp_file], stderr=subprocess.STDOUT, text=True, timeout=5)
                expected = normalize_output(base_questions[q])
                actual = normalize_output(output)
                if actual.lower() == expected.lower():
                    result += f"{q}: ✅ Student answer is correct!\n"
                else:
                    result += f"{q}: ❌ Incorrect output (Expected: {expected}, Got: {actual})\n"
            except subprocess.TimeoutExpired as e:
                result += f"{q}: ❌ Timeout: Code took too long to execute (possible infinite loop)\n"
            except subprocess.CalledProcessError as e:
                result += f"{q}: ❌ {e.output.strip()}\n"
            except Exception as e:
                result += f"{q}: ❌ {str(e)}\n"
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        else:
            result += f"{q}: ❌ Missing\n"
    print(f"DEBUG: Evaluation Result:\n{result}")
    return result