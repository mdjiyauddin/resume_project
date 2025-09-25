# ui.py
import streamlit as st
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import openai
import io
import base64
from typing import List, Dict, Any

from helpers import (
    extract_text_from_pdf,
    find_emails,
    find_phones,
    parse_resume,
    create_pdf_report,
    create_report_text
)
from agents import (
    detect_skills_for_ui,
    domain_match_for_ui,
    generate_interview_questions_offline,
    simple_qa_offline,
    generate_improvements,
    domain_required_skills,
    batch_resume_analysis
)

load_dotenv()
st.set_page_config(page_title="Ace Recruitment Agent", layout="wide")
APP_NAME = "Ace Recruitment Agent"

# ------------- CSS -------------
def apply_css(accent="#d3212f"):
    st.markdown(f"""
    <style>
    body {{ background-color:#0b0b0b; color:#eaeaea; }}
    [data-testid="stSidebar"]{{ background:#111; border-right:2px solid {accent}; }}
    h1,h2,h3,h4 {{ color:{accent}; }}
    .card {{ background:#141414; padding:16px; border-radius:12px; border-left:5px solid {accent}; margin-bottom:18px; }}
    .skill-tag {{ display:inline-block; background:{accent}; color:#fff; padding:6px 12px; border-radius:20px; margin:4px; }}
    .missing-skill-tag {{ background:#333; color:#ddd; padding:6px 12px; border-radius:12px; margin:4px; }}
    .star {{ color: #f5c518; font-weight:bold; margin-right:6px; }}
    .scroll-box {{ max-height:300px; overflow-y:auto; background:#1a1a1a; padding:10px; border-radius:8px; }}
    </style>
    """, unsafe_allow_html=True)

# ------------- Sidebar -------------
def sidebar_config():
    with st.sidebar:
        st.header("⚙️ Configuration")
        use_openai = st.checkbox("Use OpenAI (optional)", value=False)
        api_key = st.text_input("OpenAI API Key", type="password")
        accent = st.color_picker("Accent Color", "#d3212f")
        st.markdown("---")
        st.write(f"**{APP_NAME}**")
    return {"use_openai": use_openai,"api_key": api_key.strip(), "accent": accent}

def create_pie(score, size=4):
    fig, ax = plt.subplots(figsize=(size, size), facecolor="#0b0b0b")
    sizes = [score, 100 - score]
    colors = ['#4CAF50', '#222']
    ax.pie(sizes, colors=colors, startangle=90, wedgeprops=dict(width=0.35))
    centre = plt.Circle((0, 0), 0.68, fc='#141414')
    fig.gca().add_artist(centre)
    ax.text(0, 0, f"{score}%", ha='center', va='center', fontsize=20, color='white', fontweight='bold')
    ax.axis('equal')
    return fig

# ------------- Main -------------
def main():
    cfg = sidebar_config()
    apply_css(cfg["accent"])
    st.title(f"🚀 {APP_NAME}")

    if cfg["use_openai"] and cfg["api_key"]:
        openai.api_key = cfg["api_key"]

    # Top controls
    col1, col2 = st.columns([3,1])
    with col1:
        domain = st.selectbox("🎯 Select domain:", [
            "Data Scientist", "AI/ML Engineer", "Frontend Developer",
            "Backend Developer", "Cloud Engineer", "Software Engineer", "QA Engineer"
        ])
        st.caption("Choose role to compare skills and get tailored suggestions.")
    with col2:
        multiple = st.checkbox("Allow multiple file upload (batch)", value=False)

    # Upload
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📄 Upload Resume(s)")
    uploaded = st.file_uploader("Upload PDF resumes", type=["pdf"], accept_multiple_files=multiple)
    st.markdown('</div>', unsafe_allow_html=True)

    # Batch mode list
    files_list = uploaded if isinstance(uploaded, list) else ([uploaded] if uploaded else [])
    file_entries = [{"filename": f.name, "file": f} for f in files_list]

    # Analysis buttons
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        if st.button("🔍 Analyze / Single"):
            if not files_list:
                st.warning("Upload at least one resume.")
            else:
                # analyze the first resume only
                file0 = files_list[0]
                text = extract_text_from_pdf(file0)
                st.session_state["last_text"] = text
                # domain match
                match = domain_match_for_ui(text, domain)
                st.session_state["match_result"] = match
                # parsed small
                parsed = parse_resume(file0)
                st.session_state["parsed"] = parsed
                st.success("Analysis done.")
    with colB:
        if st.button("📊 Batch Analyze & Generate Report"):
            if not files_list:
                st.warning("Upload resumes for batch analysis.")
            else:
                results = []
                for f in files_list:
                    parsed = parse_resume(f)
                    text = parsed.get("text","")
                    from agents import compute_domain_match
                    match = compute_domain_match(text, domain)
                    results.append({
                        "filename": f.name,
                        "text": text,
                        "name": parsed.get("name",""),
                        "score": parsed.get("ats_score",0),
                        "match_percent": match.get("match_percent",0)
                    })
                # create pdf & provide download
                pdf_path = create_pdf_report(results, output_file="batch_report.pdf")
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button("Download Batch PDF Report", data=pdf_file, file_name="batch_report.pdf")
                st.success("Batch report created.")
    with colC:
        chart_zoom = st.slider("Chart zoom", 3, 7, 4)

    # Show domain required skills always
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader(f"🔎 Required skills for {domain}")
    req_list = domain_required_skills(domain)
    if req_list:
        st.markdown(", ".join([f"**{r['skill']}**" for r in req_list]))
    else:
        st.info("No skills defined for this domain.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Show analysis if available
    if st.session_state.get("match_result"):
        res = st.session_state["match_result"]
        pct = res.get("match_percent", 0)
        matched = res.get("matched", [])
        missing = res.get("missing", [])

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📊 Domain Match Overview")
        a, b = st.columns([1,2])
        with a:
            st.pyplot(create_pie(pct, size=chart_zoom))
            if pct >= 75:
                st.success("🎉 Congratulations — Good fit for this role.")
            elif pct >= 40:
                st.info("⚠️ Partial fit — consider improving missing skills.")
            else:
                st.error("❌ Low fit — major skills missing.")
        with b:
            st.markdown("**Matched Skills:**")
            if matched:
                st.markdown(" ".join([f"<span class='skill-tag'>{m['skill']}</span>" for m in matched]), unsafe_allow_html=True)
            else:
                st.info("No matched skills found.")
            st.markdown("---")
            st.markdown("**Missing / Weak Skills (importance shown)**")
            if missing:
                for m in missing:
                    stars = '★' * m.get('importance',3) + '☆' * (5 - m.get('importance',3))
                    st.markdown(f"<div class='missing-skill-tag'><span class='star'>{stars}</span> {m['skill']}</div>", unsafe_allow_html=True)
            else:
                st.info("No missing skills.")
        st.markdown('</div>', unsafe_allow_html=True)

        # show basic parsed info
        parsed = st.session_state.get("parsed", {})
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("📇 Candidate Contact & Preview")
        txt = st.session_state.get("last_text","")
        if parsed.get("emails"):
            st.markdown("**Emails:** " + ", ".join(parsed.get("emails")))
        if parsed.get("phones"):
            st.markdown("**Phones:** " + ", ".join(parsed.get("phones")))
        st.markdown("---")
        st.subheader("Extracted Resume Text (preview)")
        st.markdown(f"<div class='scroll-box'>{txt[:5000]}</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # improvements section
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("✨ Resume Improvements")
        areas = st.multiselect("Select areas (leave empty for all):",
                                ["Skill Highlighting", "Experience Description", "Projects", "Overall structure", "Certifications"])
        if st.button("Generate Improvements (Offline)"):
            improvements = generate_improvements(txt, areas, domain)
            for area, sugg in improvements.items():
                st.markdown(f"### {area}")
                for s in sugg:
                    st.write("- " + s)

        # optional: OpenAI-enhanced improvements (if user provided API key)
        if cfg["use_openai"] and cfg["api_key"]:
            if st.button("Generate Improvements (With OpenAI)"):
                prompt = f"Act as a pro hiring manager. Resume text: '''{txt[:3000]}''' Domain: {domain}. Provide concise, actionable improvement suggestions organized by area: skill highlighting, experience description, projects, overall structure."
                try:
                    resp = openai.ChatCompletion.create(
                        model="gpt-4o-mini",  # change model to the one available to you
                        messages=[{"role":"system","content":"You are an expert hiring manager."},
                                  {"role":"user","content":prompt}],
                        max_tokens=600,
                        temperature=0.2
                    )
                    out_text = resp.choices[0].message.content.strip()
                    st.markdown("#### OpenAI Suggestions")
                    st.write(out_text)
                except Exception as e:
                    st.error(f"OpenAI call failed: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

        # Interview Qs generator
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("🎯 Interview Questions")
        per_skill = st.slider("Questions per skill", 1, 3, 2)
        difficulty = st.selectbox("Difficulty", ["Basic", "Medium", "Hard"], index=1)
        if st.button("Generate Interview Questions"):
            skills = [m['skill'] for m in res.get("matched", [])] or detect_skills_for_ui(txt)
            qs = generate_interview_questions_offline(skills, max_per_skill=per_skill, difficulty=difficulty)
            for i,q in enumerate(qs,1):
                st.markdown(f"**Q{i}. {q['q']}**")
                st.write(f"_Sample answer:_ {q.get('a','')}")
            # download
            txtdata = "\n\n".join([f"Q{i}. {q['q']}\nA: {q.get('a','')}" for i,q in enumerate(qs,1)])
            st.download_button("Download Questions (TXT)", txtdata, file_name="interview_questions.txt")
        st.markdown('</div>', unsafe_allow_html=True)

        # Quick Q&A
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("💬 Quick Resume Q&A")
        q = st.text_input("Ask a question about the resume (name / email / phone / skills / education / experience):", key="qa_input")
        if st.button("Get Answer"):
            if not q.strip():
                st.warning("Type a question.")
            else:
                ans = simple_qa_offline(txt, q)
                st.info(ans)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Upload and analyze a resume to see results or run a batch.")

if __name__ == "__main__":
    main()
