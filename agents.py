# agents.py
from typing import List, Dict, Any
import re
from helpers import clean_text, ats_score

# --------------------------
# Domain skill map with ~10 skills each
# --------------------------
DOMAIN_SKILL_MAP = {
    "Data Scientist": [
        ("python",5), ("pandas",5), ("numpy",5), ("scikit-learn",5),
        ("machine learning",5), ("statistics",4), ("sql",4), ("visualization",3),
        ("spark",3), ("tensorflow",4)
    ],
    "AI/ML Engineer": [
        ("python",5), ("deep learning",5), ("pytorch",5), ("tensorflow",5),
        ("computer vision",4), ("nlp",4), ("docker",3), ("mlops",3),
        ("keras",3), ("cuda",2)
    ],
    "Frontend Developer": [
        ("html",5), ("css",5), ("javascript",5), ("react",5),
        ("typescript",4), ("webpack",3), ("vue",3), ("accessibility",3),
        ("performance",3), ("testing",3)
    ],
    "Backend Developer": [
        ("python",5), ("django",5), ("flask",4), ("node.js",4),
        ("sql",4), ("rest api",4), ("docker",3), ("microservices",4),
        ("postgresql",3), ("redis",3)
    ],
    "Cloud Engineer": [
        ("aws",5), ("azure",5), ("gcp",5), ("docker",4),
        ("kubernetes",4), ("terraform",4), ("serverless",3), ("monitoring",3),
        ("ci/cd",4), ("security",3)
    ],
    "Software Engineer": [
        ("python",5), ("java",5), ("data structures",5), ("algorithms",5),
        ("git",4), ("oop",4), ("system design",4), ("microservices",3),
        ("concurrency",3), ("testing",3)
    ],
    "QA Engineer": [
        ("testing",5), ("selenium",4), ("pytest",4), ("manual testing",5),
        ("automation",4), ("performance testing",3), ("api testing",3),
        ("bug tracking",3), ("rest api",3), ("ci/cd",3)
    ]
}

def domain_required_skills(domain: str) -> List[Dict[str, Any]]:
    return [{"skill": s.title(), "importance": imp} for (s, imp) in DOMAIN_SKILL_MAP.get(domain, [])]

# --------------------------
# Extract skills simply from text
# --------------------------
def detect_skills_simple(text: str, custom_skills: List[str] = None) -> List[str]:
    if not text:
        return []
    txt = text.lower()
    pool = (custom_skills or []) + [s for domain in DOMAIN_SKILL_MAP.values() for (s, _) in domain]
    found = []
    for s in pool:
        if s.lower() in txt:
            found.append(s.title())
    # dedupe preserve order
    out = []
    for s in found:
        if s not in out:
            out.append(s)
    return out

# --------------------------
# Domain match: compute matched / missing / percent
# --------------------------
def compute_domain_match(resume_text: str, domain: str) -> Dict[str, Any]:
    req = domain_required_skills(domain)
    txt = resume_text.lower() if resume_text else ""
    matched = []
    missing = []
    total_weight = sum([k['importance'] for k in req]) or 1
    matched_weight = 0
    for k in req:
        if k['skill'].lower() in txt:
            matched.append(k.copy())
            matched_weight += k['importance']
        else:
            missing.append(k.copy())
    percent = int(round((matched_weight / total_weight) * 100))
    # provide small skill-level heuristic
    for m in matched:
        m['score'] = min(10, m['importance'] * 2)
    for mm in missing:
        mm['score'] = 0
    return {"matched": matched, "missing": missing, "match_percent": percent}

# --------------------------
# Interview Qs generator (supports difficulties)
# --------------------------
def generate_interview_questions_offline(skills: List[str], max_per_skill: int = 2, difficulty: str = "Medium") -> List[Dict[str,str]]:
    qs = []
    if not skills:
        qs = [{"q":"Tell me about yourself.","a":"Short summary focusing on relevant experience."},
              {"q":"Why this role?","a":"Explain motivation and fit."}]
        return qs

    for skill in skills:
        for i in range(max_per_skill):
            if difficulty == "Basic":
                q = f"Explain {skill} and where you'd use it."
                a = f"High-level description and basic use cases of {skill}."
            elif difficulty == "Hard":
                q = f"Design a scalable solution that heavily uses {skill}. Explain trade-offs."
                a = f"Describe architecture, bottlenecks and scaling strategies using {skill}."
            else:  # Medium
                q = f"Describe a project where you used {skill}. What challenges did you solve?"
                a = f"Talk about the project, your exact role, and results using {skill}."
            qs.append({"q": q, "a": a, "skill": skill})
    qs.append({"q":"Describe a challenge and how you solved it.","a":"Context, action, result."})
    return qs

# --------------------------
# Simple QA (keyword match)
# --------------------------
def simple_qa_offline(resume_text: str, question: str) -> str:
    if not resume_text:
        return "Please upload a resume."
    txt = resume_text.replace("\n", " ")
    sentences = [s.strip() for s in re.split(r'\.|\n', txt) if s.strip()]
    keywords = [w.lower() for w in re.findall(r'\w{4,}', question)]
    matches = []
    for s in sentences:
        low = s.lower()
        if any(k in low for k in keywords):
            matches.append(s)
    if matches:
        return "\n\n".join(matches[:6])
    return "Could not find a direct answer in the resume."

# --------------------------
# generate improvements (heuristics; optionally replace with OpenAI later)
# --------------------------
def generate_improvements(resume_text: str, selected_areas: List[str], domain: str = None) -> Dict[str, List[str]]:
    """
    Returns dictionary area -> list[str] suggestions.
    selected_areas: list of strings like "Skill Highlighting", "Experience Description", "Projects", "Overall structure"
    If selected_areas is empty, returns suggestions for all areas.
    """
    out: Dict[str, List[str]] = {}
    text = resume_text or ""
    req = domain_required_skills(domain) if domain else []
    missing = [k['skill'] for k in req if k['skill'].lower() not in text.lower()]

    sel = set([s.strip() for s in (selected_areas or [])])

    # Skill Highlighting
    if not sel or "Skill Highlighting" in sel:
        if req:
            out["Skill Highlighting"] = [f"Show a short bullet linking a project to {s} and a measurable outcome." for s in missing[:8]]
        else:
            out["Skill Highlighting"] = ["Use metrics (%, numbers, time saved) to quantify your skill impact."]

    # Experience Description
    if not sel or "Experience Description" in sel:
        out["Experience Description"] = [
            "Start bullets with action verbs (Designed, Implemented, Led).",
            "Prefer 2-3 bullets per role showing problem → action → result with numbers."
        ]

    # Projects
    if not sel or "Projects" in sel:
        out["Projects"] = [
            "Add 2–4 projects: title, tech stack, role, clear measurable result (e.g., improved X by Y%).",
            "Include links (GitHub) or short screenshots if available."
        ]

    # Overall structure
    if not sel or "Overall structure" in sel:
        out["Overall structure"] = [
            "Use reverse-chronological order, consistent date format and clear headings.",
            "Keep resume ≤ 2 pages for mid/senior roles; 1 page for entry-level where possible."
        ]

    # Extras
    if not sel or "Certifications" in sel:
        out["Certifications"] = [
            "Add relevant certifications (AWS/GCP, ML courses, Frontend certs) if you have them."
        ]

    return out

# --------------------------
# Batch analysis helper
# --------------------------
def batch_resume_analysis(resume_files: List[Dict[str, Any]], domain: str) -> List[Dict[str, Any]]:
    """
    resume_files: list of dicts {"filename": str, "file": File-like}
    returns sorted results by combined score (ats + match)
    """
    out = []
    for entry in resume_files:
        filename = entry.get("filename")
        fileobj = entry.get("file")
        # read text: if fileobj is bytes / file-like, try to read .read and pass to helper outside
        try:
            # to keep decoupled we expect caller used helpers.extract_text_from_pdf
            from helpers import extract_text_from_pdf
            text = extract_text_from_pdf(fileobj)
        except Exception:
            text = ""
        ats = ats_score(text)
        match = compute_domain_match(text, domain).get("match_percent", 0)
        score = int((ats * 0.6) + (match * 0.4))  # combine heuristically
        out.append({"filename": filename, "ats_score": ats, "match_percent": match, "combined_score": score})
    out = sorted(out, key=lambda x: x["combined_score"], reverse=True)
    return out

# --------------------------
# UI wrappers
# --------------------------
def detect_skills_for_ui(text: str, custom_skills: List[str] = None):
    return detect_skills_simple(text, custom_skills)

def domain_match_for_ui(text: str, domain: str):
    return compute_domain_match(text, domain)
