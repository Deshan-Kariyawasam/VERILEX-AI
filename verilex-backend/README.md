# Verilex AI Backend — PythonAnywhere Deployment Guide

A Flask REST API that downloads a PDF, analyses it with Claude AI using the Verilex legal-audit prompt, and returns results via three endpoints.

---

## Endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/health` | `{"status": "ok"}` |
| POST | `/extract-document` | JSON array of ordered document elements |
| POST | `/analyze-document` | Full structured JSON analysis |
| POST | `/generate-pdf` | Binary PDF download (Verilex audit report) |

---

## Prerequisites

- PythonAnywhere account (free tier works for low traffic; paid for longer timeouts)
- Anthropic API key with access to `claude-opus-4-7`

---

## Step-by-step deployment

### 1. Upload the files

Open a PythonAnywhere **Bash console** and run:

```bash
mkdir -p ~/verilex-backend
```

Then use the **Files** tab to upload all files inside `verilex-backend/` into `/home/YOURUSERNAME/verilex-backend/`.

Alternatively, if the repo is on GitHub:

```bash
git clone https://github.com/YOUR_GITHUB/VERILEX-AI.git ~/VERILEX-AI
cp -r ~/VERILEX-AI/verilex-backend ~/verilex-backend
```

### 2. Create a virtual environment and install dependencies

In a Bash console:

```bash
cd ~/verilex-backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** PythonAnywhere free tier uses Python 3.10 by default. All packages are compatible.

### 3. Create the Web App

1. Go to the **Web** tab in your PythonAnywhere dashboard.
2. Click **Add a new web app**.
3. Choose **Manual configuration** (not Flask quick-start).
4. Select **Python 3.10**.

### 4. Configure the WSGI file

1. In the Web tab, click the link next to **WSGI configuration file** (e.g. `/var/www/YOURUSERNAME_pythonanywhere_com_wsgi.py`).
2. Delete all existing content.
3. Paste the following (replace `YOURUSERNAME`):

```python
import sys
import os

project_home = "/home/YOURUSERNAME/verilex-backend"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application
```

4. Save the file.

### 5. Set the virtualenv path

In the Web tab, under **Virtualenv**, enter:

```
/home/YOURUSERNAME/verilex-backend/venv
```

### 6. Set the ANTHROPIC_API_KEY environment variable

The safest way on PythonAnywhere:

1. Go to the **Web** tab.
2. Scroll down to **Environment variables** (only available on paid plans).
3. Add:
   - Key: `ANTHROPIC_API_KEY`
   - Value: `sk-ant-api03-...` (your real key)

**Free plan alternative** — edit the WSGI file and add before the import line:

```python
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api03-..."
```

> Keep the WSGI file private; never commit it with a real API key.

Optional variable to override the Claude model:

```
CLAUDE_MODEL=claude-opus-4-7
```

### 7. Reload and test

1. Click **Reload** in the Web tab.
2. Open a new Bash console and test:

```bash
curl https://YOURUSERNAME.pythonanywhere.com/health
# Expected: {"status":"ok"}

curl -X POST https://YOURUSERNAME.pythonanywhere.com/analyze-document \
  -H "Content-Type: application/json" \
  -d '{"pdf_url":"https://example.com/sample.pdf","job_id":"test-001"}'
```

---

## Bubble.io integration

In your Bubble.io API connector:

- **Base URL:** `https://YOURUSERNAME.pythonanywhere.com`
- **Authentication:** None (or add a shared secret header if desired)
- **CORS:** Handled automatically by the backend (all origins allowed)

### Endpoint configuration in Bubble

**analyze-document**
- Method: POST
- Body type: JSON
- Body: `{ "pdf_url": "<dynamic>", "job_id": "<dynamic>" }`

**generate-pdf**
- Method: POST
- Body type: JSON
- Body: `{ "pdf_url": "<dynamic>", "job_id": "<dynamic>" }`
- Return type: File (set "Response type" to `file` in the API connector)

---

## Environment variables reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-opus-4-7` | Claude model ID |
| `CLAUDE_MAX_TOKENS` | No | `8192` | Max tokens per response |

---

## File structure

```
verilex-backend/
├── app.py            # Flask routes
├── claude_client.py  # Anthropic SDK + Verilex system prompt
├── pdf_extractor.py  # PyMuPDF download + text extraction
├── pdf_generator.py  # ReportLab PDF report generation
├── requirements.txt  # pip dependencies
├── app.wsgi          # PythonAnywhere WSGI entry point
└── README.md         # This file
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: anthropic` | Virtualenv not activated or packages not installed in it |
| `EnvironmentError: ANTHROPIC_API_KEY not set` | Add the env var via the Web tab or WSGI file |
| PDF download returns 400 | Confirm the PDF URL is publicly accessible and returns a valid PDF |
| 502 Bad Gateway | Check the **Error log** in the Web tab; usually a Python import error |
| Timeout on large PDFs | Upgrade to a paid PythonAnywhere plan (longer request timeout) |
| `Cannot parse JSON from Claude response` | Claude returned unexpected output; check the **Server log** for the raw response |

---

## Local development

```bash
cd verilex-backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
# Server running at http://localhost:5000
```
