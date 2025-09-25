# helpers.py
import re
from typing import List, Dict, Any, Union
import pdfplumber
from fpdf import FPDF

# --------------------------
# Regex for phones & emails
# --------------------------
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# --------------------------
# Clean / extract / parse
# --------------------------
def clean_text(text: str) -> str:
    """Normalize whitespace and remove weird characters."""
    if not text:
        return ""
    txt = text.replace('\r', '\n')
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    txt = txt.replace('\xa0', ' ')
    return txt.strip()

def find_emails(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(EMAIL_RE.findall(text)))

def find_phones(text: str) -> List[str]:
    if not text:
        return []
    phones = PHONE_RE.findall(text)
    phones = [re.sub(r"[^0-9+]", "", p) for p in phones]
    return list(dict.fromkeys(phones))

def extract_text_from_pdf(file_obj: Union[str, Any]) -> str:
    """
    Accepts either a path (str) or a file-like object (Streamlit's uploaded file).
    Uses pdfplumber to extract text from all pages.
    """
    text = ""
    try:
        # pdfplumber can handle file-like objects; on some environments you might pass bytes
        pdf = pdfplumber.open(file_obj)
        for p in pdf.pages:
            page_text = p.extract_text() or ""
            text += page_text + "\n"
        pdf.close()
        return clean_text(text)
    except Exception:
        # fallback: try to read bytes and open via pdfplumber.open(io.BytesIO(...))
        try:
            data = file_obj.read() if hasattr(file_obj, "read") else None
            if data:
                import io
                pdf = pdfplumber.open(io.BytesIO(data))
                for p in pdf.pages:
                    page_text = p.extract_text() or ""
                    text += page_text + "\n"
                pdf.close()
                return clean_text(text)
        except Exception:
            return ""

# --------------------------
# Simple ATS scoring system
# --------------------------
def ats_score(text: str) -> int:
    """
    Very simple, keyword-based ATS score (0-100).
    Extend keywords to taste.
    """
    if not text:
        return 0
    keywords = [
        "python", "java", "machine learning", "ai", "sql", "data science",
        "flask", "react", "node.js", "cloud", "aws", "docker",
        "communication", "leadership", "tensorflow", "pytorch", "sql",
        "django", "kubernetes", "terraform"
    ]
    score = 0
    tl = text.lower()
    for word in keywords:
        if word.lower() in tl:
            score += 7  # ~7 per match to reach near 100 on many matches
    return min(100, score)

# --------------------------
# PDF report generator
# --------------------------
def create_pdf_report(results: List[Dict[str, Any]], output_file: str = "ATS_Report.pdf") -> str:
    """
    results: list of dicts: {"filename": str, "score": int, "match_percent": int, "name": str}
    Returns path to saved PDF.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(0, 10, "ATS Resume Analysis Report", ln=True, align="C")
    pdf.ln(6)

    pdf.set_font("Arial", size=11)
    for res in results:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(0, 8, f"Resume: {res.get('filename','-')}", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f"Name: {res.get('name','-')}", ln=True)
        pdf.cell(0, 7, f"ATS Score: {res.get('score',0)}%", ln=True)
        pdf.cell(0, 7, f"Domain Match: {res.get('match_percent',0)}%", ln=True)

        if res.get('score', 0) >= 75:
            pdf.set_text_color(0, 128, 0)
            pdf.cell(0, 7, "✅ Shortlisted", ln=True)
        else:
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 7, "❌ Not selected", ln=True)

        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

    pdf.output(output_file)
    return output_file

# --------------------------
# small parse helper (returns minimal parsed info)
# --------------------------
def parse_resume(file_obj: Union[str, Any]) -> Dict[str, Any]:
    """
    Return a small parsed dict: text, emails, phones, ats_score
    """
    txt = extract_text_from_pdf(file_obj)
    return {
        "text": txt,
        "emails": find_emails(txt),
        "phones": find_phones(txt),
        "ats_score": ats_score(txt),
        "name": (find_emails(txt)[0] if find_emails(txt) else "")
    }

# --------------------------
# Create a readable report text (optional)
# --------------------------
def create_report_text(parsed: Dict[str, Any]) -> str:
    name = parsed.get("name") or "Candidate"
    lines = [
        f"Resume report for: {name}",
        f"Emails: {', '.join(parsed.get('emails', []))}",
        f"Phones: {', '.join(parsed.get('phones', []))}",
        f"ATS Score: {parsed.get('ats_score', 0)}%",
        "",
        "Extracted text preview:",
        parsed.get("text", "")[:1000]
    ]
    return "\n".join(lines)
