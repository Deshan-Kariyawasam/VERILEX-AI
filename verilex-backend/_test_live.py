"""
Live end-to-end test: PDF download → text extraction → Verilex analysis → PDF report.
Run from verilex-backend/ with the venv active.
"""

import json
import os
import sys

PDF_URL = (
    "https://a0411f378c647dea10b216c374f52ec4.cdn.bubble.io"
    "/f1776531725776x816401348170337700"
    "/Woodbridge%20MS%20Site%20Lease.pdf"
)

def sep(msg):
    print(f"\n{'='*62}\n  {msg}\n{'='*62}", flush=True)

# ── 1. Extract PDF ────────────────────────────────────────────────────────────
sep("STEP 1 — Downloading & extracting PDF")
from pdf_extractor import download_and_extract_pdf

pdf_data = download_and_extract_pdf(PDF_URL)
print(f"Pages      : {pdf_data['page_count']}")
print(f"Total chars: {len(pdf_data['full_text']):,}")

# ── 2. Analyze with Claude ────────────────────────────────────────────────────
sep("STEP 2 — Running Verilex AI analysis (claude-opus-4-7)")
from claude_client import VerilexClient

client = VerilexClient()
client.max_tokens = 16000   # large output for 232-page document

analysis = client.analyze_document(
    pdf_data["full_text"], pdf_data["page_count"], "test-001"
)

# ── 3. Print JSON result ──────────────────────────────────────────────────────
sep("STEP 3 — Analysis JSON result")
out = json.dumps(analysis, ensure_ascii=False, indent=2)
sys.stdout.buffer.write(out.encode("utf-8"))
sys.stdout.buffer.write(b"\n")
sys.stdout.buffer.flush()

# ── 4. Generate PDF report ────────────────────────────────────────────────────
sep("STEP 4 — Generating PDF report")
from pdf_generator import generate_pdf_report

pdf_bytes = generate_pdf_report(analysis)
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verilex_output.pdf")
with open(out_path, "wb") as f:
    f.write(pdf_bytes)

print(f"Saved → {out_path}  ({len(pdf_bytes):,} bytes)")
sep("DONE")