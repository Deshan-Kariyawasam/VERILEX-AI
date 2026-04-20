import os
import io
import base64
import logging
import threading

import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from pdf_extractor import download_and_extract_pdf
from claude_client import ValorexClient
from pdf_generator import generate_pdf_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(
    app,
    origins="*",
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

valorex = ValorexClient()


# ── helpers ──────────────────────────────────────────────────────────────────

def _require_json_body():
    """Return (data, None) or (None, error_response)."""
    data = request.get_json(silent=True)
    if not data:
        return None, (jsonify({"error": "Request body must be valid JSON"}), 400)
    return data, None


def _require_pdf_url(data, job_id="unknown"):
    pdf_url = data.get("pdf_url", "").strip()
    if not pdf_url:
        return None, (jsonify({"error": "pdf_url is required", "job_id": job_id}), 400)
    return pdf_url, None


# ── endpoints ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/extract-document", methods=["POST"])
def extract_document():
    data, err = _require_json_body()
    if err:
        return err

    job_id = data.get("job_id", "unknown")
    pdf_url, err = _require_pdf_url(data, job_id)
    if err:
        return err

    try:
        pdf_data = download_and_extract_pdf(pdf_url)
        structure = valorex.extract_document_structure(
            pdf_data["full_text"], pdf_data["page_count"]
        )
        return jsonify(structure)

    except ValueError as exc:
        logger.warning("PDF download/extract error: %s", exc)
        return jsonify({"error": str(exc), "job_id": job_id}), 400

    except Exception as exc:
        logger.exception("Unexpected error in /extract-document")
        return jsonify({"error": str(exc), "job_id": job_id}), 500


@app.route("/analyze-document", methods=["POST"])
def analyze_document():
    data, err = _require_json_body()
    if err:
        return err

    job_id = data.get("job_id", "unknown")
    pdf_url, err = _require_pdf_url(data, job_id)
    if err:
        return err

    try:
        pdf_data = download_and_extract_pdf(pdf_url)
        analysis = valorex.analyze_document(
            pdf_data["full_text"], pdf_data["page_count"], job_id
        )
        return jsonify(analysis)

    except ValueError as exc:
        logger.warning("PDF download/extract error: %s", exc)
        return jsonify({"error": str(exc), "job_id": job_id}), 400

    except Exception as exc:
        logger.exception("Unexpected error in /analyze-document")
        return jsonify({"error": str(exc), "job_id": job_id}), 500


def _process_and_callback(pdf_url: str, job_id: str, webhook_url: str):
    try:
        pdf_data = download_and_extract_pdf(pdf_url)
        analysis = valorex.analyze_document(
            pdf_data["full_text"], pdf_data["page_count"], job_id
        )
        pdf_bytes = generate_pdf_report(analysis)
        token_usage = analysis.pop("_token_usage", {})
        payload = {
            "job_id": job_id,
            "status": "success",
            "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": f"valorex-audit-{job_id}.pdf",
            "tokens": token_usage,
        }
    except Exception as exc:
        logger.exception("Background processing failed job=%s", job_id)
        payload = {"job_id": job_id, "status": "error", "error": str(exc)}

    try:
        requests.post(webhook_url, json=payload, timeout=30)
        logger.info("Webhook delivered job=%s", job_id)
    except Exception as exc:
        logger.error("Webhook delivery failed job=%s: %s", job_id, exc)


@app.route("/generate-pdf", methods=["POST"])
def generate_pdf():
    data, err = _require_json_body()
    if err:
        return err

    job_id = data.get("job_id", "unknown")
    pdf_url, err = _require_pdf_url(data, job_id)
    if err:
        return err

    webhook_url = data.get("webhook_url", "").strip()
    if not webhook_url:
        return jsonify({"error": "webhook_url is required", "job_id": job_id}), 400

    threading.Thread(
        target=_process_and_callback,
        args=(pdf_url, job_id, webhook_url),
        daemon=True,
    ).start()

    return jsonify({"status": "processing", "job_id": job_id}), 202


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
