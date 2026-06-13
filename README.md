# 🔍 FactCheck AI

AI-powered fact-checking tool that analyzes PDF documents and verifies factual claims.

## Features

* Upload PDF documents
* Extract verifiable claims automatically
* AI-based claim verification
* Classify claims as:

  * ✅ Verified
  * ⚠️ Inaccurate
  * ❌ False
  * ❓ Unverifiable
* Generate downloadable report

## Tech Stack

* Python
* Streamlit
* Google Gemini API
* PyPDF2

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Add environment variable:

```env
GEMINI_API_KEY=your_api_key
```

Start app:

```bash
streamlit run app.py
```

## Live Demo

Deployed on Streamlit Cloud.

---

Built by Aditya Raj
