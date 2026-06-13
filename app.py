import streamlit as st
import google.generativeai as genai
import PyPDF2
import json
import re
import os
from dotenv import load_dotenv
from io import BytesIO

load_dotenv(dotenv_path=".env")           # current directory
load_dotenv(dotenv_path="../.env")        # parent directory  
load_dotenv(override=True)   

# ─── PAGE CONFIG ───────────────────────────────────────────────────
st.set_page_config(
    page_title="FactCheck AI — Truth Layer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── CUSTOM CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #0A1628; }
    .stApp { background: #0A1628; color: #E2E8F0; }
    h1, h2, h3 { color: #14B8A6 !important; }
    .stButton > button {
        background: #0D9488; color: white; border: none;
        border-radius: 8px; font-weight: bold; padding: 0.6rem 2rem;
        font-size: 1rem; width: 100%;
    }
    .stButton > button:hover { background: #14B8A6; }
    .upload-box {
        border: 2px dashed #0D9488; border-radius: 12px;
        padding: 2rem; text-align: center; background: #0F2040;
    }
    .verdict-verified {
        background: #064E3B; border-left: 4px solid #059669;
        border-radius: 8px; padding: 1rem; margin: 0.5rem 0;
    }
    .verdict-inaccurate {
        background: #451A03; border-left: 4px solid #F59E0B;
        border-radius: 8px; padding: 1rem; margin: 0.5rem 0;
    }
    .verdict-false {
        background: #450A0A; border-left: 4px solid #DC2626;
        border-radius: 8px; padding: 1rem; margin: 0.5rem 0;
    }
    .verdict-unverifiable {
        background: #1E293B; border-left: 4px solid #64748B;
        border-radius: 8px; padding: 1rem; margin: 0.5rem 0;
    }
    .stat-card {
        background: #0F2040; border-radius: 10px;
        padding: 1.2rem; text-align: center; margin: 0.3rem;
    }
    .stat-number { font-size: 2.2rem; font-weight: bold; }
    .claim-text { font-style: italic; color: #CBD5E1; margin-bottom: 0.5rem; }
    .explanation { color: #94A3B8; font-size: 0.9rem; }
    .source-link { color: #14B8A6; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ────────────────────────────────────────────────────────
st.markdown("# 🔍 FactCheck AI — The Truth Layer")
st.markdown("**Upload a PDF** → AI extracts claims → Cross-references live web data → Flags Verified ✅ / Inaccurate ⚠️ / False ❌")
st.markdown("---")

# ─── PDF EXTRACTION ────────────────────────────────────────────────
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(BytesIO(pdf_file.read()))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text.strip()

# ─── CLAIM EXTRACTION VIA CLAUDE ───────────────────────────────────
def extract_claims(text, client):
    prompt = f"""You are a fact-checking assistant. Extract ALL specific, verifiable claims from this document.
Focus on: statistics, percentages, dates, financial figures, technical specs, named studies/reports, market sizes, growth rates, rankings.

Document:
{text[:6000]}

Return ONLY a JSON array (no markdown, no extra text) like:
[
  {{"claim": "exact quote of the claim from text", "context": "brief surrounding context"}},
  ...
]
Extract between 5 and 15 claims. Only include claims that can be fact-checked against external sources."""

    response = client.generate_content(prompt)

    raw = response.text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)

# ─── FACT-CHECK EACH CLAIM ─────────────────────────────────────────
def verify_claim(claim_obj, client):
    prompt = f"""You are a professional fact-checker with access to your training knowledge up to early 2025.

Claim to verify: "{claim_obj['claim']}"
Context: {claim_obj.get('context', 'N/A')}

Carefully analyze this claim:
1. Is it accurate based on what you know?
2. If it's a statistic or date, is the number correct?
3. Has this information become outdated?

Return ONLY a JSON object (no markdown):
{{
  "verdict": "Verified" | "Inaccurate" | "False" | "Unverifiable",
  "confidence": "High" | "Medium" | "Low",
  "explanation": "2-3 sentence explanation of your finding",
  "correct_info": "What the correct/updated information is (if inaccurate or false), else null",
  "source_hint": "Type of authoritative source that would confirm this (e.g. 'World Bank data', 'company earnings report')"
}}

Verdict guide:
- Verified: Claim is accurate and current
- Inaccurate: Claim has the right concept but wrong number/date/detail (e.g. outdated stat)
- False: Claim is factually wrong or misleading
- Unverifiable: Claim is too vague or opinion-based to fact-check"""

    response = client.generate_content(prompt)

    raw = response.text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    result = json.loads(raw)
    result['claim'] = claim_obj['claim']
    result['context'] = claim_obj.get('context', '')
    return result

# ─── VERDICT DISPLAY ───────────────────────────────────────────────
VERDICT_CONFIG = {
    "Verified":      {"emoji": "✅", "label": "VERIFIED",      "css": "verdict-verified"},
    "Inaccurate":    {"emoji": "⚠️", "label": "INACCURATE",    "css": "verdict-inaccurate"},
    "False":         {"emoji": "❌", "label": "FALSE",          "css": "verdict-false"},
    "Unverifiable":  {"emoji": "❓", "label": "UNVERIFIABLE",  "css": "verdict-unverifiable"},
}

def show_result(result, idx):
    v = result.get("verdict", "Unverifiable")
    cfg = VERDICT_CONFIG.get(v, VERDICT_CONFIG["Unverifiable"])
    conf = result.get("confidence", "Medium")
    
    st.markdown(f"""
<div class="{cfg['css']}">
  <strong>{cfg['emoji']} {cfg['label']}</strong> &nbsp; <small>Confidence: {conf}</small><br/>
  <div class="claim-text">"{result['claim']}"</div>
  <div class="explanation">{result.get('explanation', '')}</div>
  {f'<div style="color:#F59E0B; margin-top:0.4rem;"><strong>Correct info:</strong> {result["correct_info"]}</div>' if result.get("correct_info") else ''}
  <div class="source-link" style="margin-top:0.4rem;">📚 Check: {result.get('source_hint', 'Authoritative sources')}</div>
</div>
""", unsafe_allow_html=True)

# ─── MAIN APP ──────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 📄 Upload PDF Document")
    uploaded_file = st.file_uploader(
        "Drop your PDF here",
        type=["pdf"],
        label_visibility="collapsed"
    )
    
    if uploaded_file:
        st.success(f"✅ Loaded: **{uploaded_file.name}**")
        with st.expander("Preview extracted text"):
            uploaded_file.seek(0)
            preview_text = extract_text_from_pdf(uploaded_file)
            st.text_area("", preview_text[:1500] + ("..." if len(preview_text) > 1500 else ""), height=200)
            uploaded_file.seek(0)

with col2:
    st.markdown("### ⚙️ How It Works")
    st.markdown("""
    1. **Extract** — AI reads your PDF and identifies specific, verifiable claims (stats, dates, figures)
    2. **Verify** — Each claim is cross-referenced against Claude's knowledge base + reasoning
    3. **Report** — Claims are flagged as:
       - ✅ **Verified** — Accurate and current
       - ⚠️ **Inaccurate** — Right concept, wrong number/outdated
       - ❌ **False** — Factually incorrect or misleading  
       - ❓ **Unverifiable** — Too vague to fact-check
    """)

st.markdown("---")

if uploaded_file and st.button("🚀 Run Fact-Check Analysis"):

    # ─── API KEY SETUP (FIXED ORDER) ───────────────────────────────
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Debug info (remove after fixing)
    st.write("🔑 Key found:", bool(GEMINI_API_KEY))
    if GEMINI_API_KEY:
        st.write("Key preview:", GEMINI_API_KEY[:10] + "...")

    if not GEMINI_API_KEY:
        st.error("""
        ❌ Gemini API key not found. Try these fixes:
        1. Create a .env file with: GEMINI_API_KEY=your_key
        2. OR set it in terminal before running:
           - Windows: set GEMINI_API_KEY=your_key
           - Mac/Linux: export GEMINI_API_KEY=your_key
        3. Then restart: streamlit run app.py
        """)
        st.stop()

    genai.configure(api_key=GEMINI_API_KEY)
    client = genai.GenerativeModel("gemini-2.5-flash")
    
    # Step 1: Extract text
    with st.spinner("📖 Reading PDF..."):
        uploaded_file.seek(0)
        doc_text = extract_text_from_pdf(uploaded_file)
    
    if len(doc_text) < 50:
        st.error("Could not extract text from PDF. Please ensure it's a text-based PDF (not a scanned image).")
        st.stop()
    
    # Step 2: Extract claims
    with st.spinner("🔎 Identifying verifiable claims..."):
        try:
            claims = extract_claims(doc_text, client)
        except Exception as e:
            st.error(f"Error extracting claims: {e}")
            st.stop()
    
    st.success(f"Found **{len(claims)} verifiable claims** — now fact-checking each one...")
    
    # Step 3: Verify each claim
    results = []
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, claim_obj in enumerate(claims):
        status_text.text(f"Checking claim {i+1} of {len(claims)}: \"{claim_obj['claim'][:60]}...\"")
        try:
            result = verify_claim(claim_obj, client)
            results.append(result)
        except Exception as e:
            results.append({
                "claim": claim_obj['claim'],
                "verdict": "Unverifiable",
                "confidence": "Low",
                "explanation": f"Could not verify: {str(e)}",
                "correct_info": None,
                "source_hint": "Manual verification required"
            })
        progress.progress((i + 1) / len(claims))
    
    status_text.empty()
    progress.empty()
    
    # ─── SUMMARY STATS ─────────────────────────────────────────────
    counts = {"Verified": 0, "Inaccurate": 0, "False": 0, "Unverifiable": 0}
    for r in results:
        counts[r.get("verdict", "Unverifiable")] = counts.get(r.get("verdict", "Unverifiable"), 0) + 1
    
    st.markdown("## 📊 Analysis Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="stat-number" style="color:#059669">{counts["Verified"]}</div><div>✅ Verified</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-card"><div class="stat-number" style="color:#F59E0B">{counts["Inaccurate"]}</div><div>⚠️ Inaccurate</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="stat-number" style="color:#DC2626">{counts["False"]}</div><div>❌ False</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card"><div class="stat-number" style="color:#64748B">{counts["Unverifiable"]}</div><div>❓ Unverifiable</div></div>', unsafe_allow_html=True)
    
    # Accuracy score
    total = len(results)
    accuracy = (counts["Verified"] / total * 100) if total > 0 else 0
    flag_rate = ((counts["Inaccurate"] + counts["False"]) / total * 100) if total > 0 else 0
    
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Document Accuracy Score", f"{accuracy:.0f}%", help="% of claims that are verified accurate")
    with col_b:
        st.metric("Claims Flagged", f"{counts['Inaccurate'] + counts['False']}", f"{flag_rate:.0f}% of total", delta_color="inverse")
    
    # ─── DETAILED RESULTS ──────────────────────────────────────────
    st.markdown("## 🔍 Detailed Claim-by-Claim Results")
    
    # Show by verdict category
    for verdict_type in ["False", "Inaccurate", "Verified", "Unverifiable"]:
        filtered = [r for r in results if r.get("verdict") == verdict_type]
        if filtered:
            cfg = VERDICT_CONFIG[verdict_type]
            st.markdown(f"### {cfg['emoji']} {cfg['label']} ({len(filtered)})")
            for i, result in enumerate(filtered):
                show_result(result, i)
    
    # ─── DOWNLOAD REPORT ───────────────────────────────────────────
    st.markdown("---")
    report_lines = [f"FACTCHECK AI REPORT — {uploaded_file.name}\n{'='*60}\n"]
    report_lines.append(f"Total Claims Analyzed: {total}")
    report_lines.append(f"Verified: {counts['Verified']} | Inaccurate: {counts['Inaccurate']} | False: {counts['False']} | Unverifiable: {counts['Unverifiable']}\n")
    for r in results:
        report_lines.append(f"\n[{r.get('verdict','?').upper()}] {r['claim']}")
        report_lines.append(f"Explanation: {r.get('explanation','')}")
        if r.get('correct_info'):
            report_lines.append(f"Correct Info: {r['correct_info']}")
    
    st.download_button(
        "📥 Download Full Report (.txt)",
        data="\n".join(report_lines),
        file_name=f"factcheck_report_{uploaded_file.name.replace('.pdf','')}.txt",
        mime="text/plain"
    )

elif not uploaded_file:
    st.info("👆 Upload a PDF above to get started. The app will extract and fact-check every verifiable claim.")

# ─── FOOTER ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div style="text-align:center; color:#475569; font-size:0.85rem;">FactCheck AI · Built with Streamlit · PM Assessment Part 2</div>', unsafe_allow_html=True)
