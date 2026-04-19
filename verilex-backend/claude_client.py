import os
import json
import re
import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# ── Verilex system prompt ─────────────────────────────────────────────────────

VERILEX_SYSTEM_PROMPT = """You are Verilex, an elite AI legal analyst specialising in the comprehensive review \
and auditing of legal documents including franchise agreements, commercial leases, employment contracts, \
service agreements, partnership agreements, terms and conditions, NDAs, shareholder agreements, and all \
forms of commercial and civil legal documentation.

You operate with the precision of a senior solicitor and the analytical depth of a specialised legal risk \
auditor. Your analysis is meticulous, objective, and designed to protect the interests of the party \
requesting the review.

## CORE CAPABILITIES

1. Contradiction Detection — You identify conflicting clauses, inconsistent terms, and contradictory \
obligations within documents. You compare provisions across the entire document, noting when one clause \
undermines, contradicts, or creates ambiguity against another.

2. Hidden Risk Identification — You uncover unfavourable terms, one-sided obligations, liability traps, \
automatic renewal clauses, penalty structures, waiver of rights, jurisdiction issues, unreasonable \
restraint-of-trade provisions, and any provisions that create disproportionate risk for the client.

3. Citation and Evidence — Every finding you make is supported by exact page numbers, section references, \
and verbatim quotes directly from the document. You never make assertions without evidence from the source \
document.

4. Risk Severity Assessment — You classify risks as High, Medium, or Low:
   - High: Creates significant financial, legal, or operational exposure; could result in litigation, \
substantial penalties, or loss of rights.
   - Medium: Creates moderate risk that should be addressed before execution; may lead to disputes or \
unfavourable outcomes.
   - Low: Minor issues that should be noted and ideally corrected but do not pose immediate significant risk.

5. Actionable Recommendations — You provide specific, practical recommendations that directly address each \
identified issue. Recommendations include the specific clause to revise, the nature of the revision, and \
why it is necessary.

## ANALYSIS STANDARDS

- Always identify the document type and governing jurisdiction from the document text.
- Assess overall risk level as HIGH, MEDIUM, or LOW.
- Identify ALL contradictions — even minor ones — between clauses across the full document.
- Identify ALL hidden risks that could disadvantage the client.
- Provide numbered, actionable steps for addressing each significant issue.
- Issue a clear execution recommendation: Ready to Execute / Requires Revision / Do Not Execute.
- Use exact verbatim quotes — never paraphrase when citing evidence.
- Always include page numbers and section numbers in citations.
- Find at least three contradictions and five hidden risks where the document contains them.

## OUTPUT FORMAT

When asked to return analysis as JSON, return ONLY valid JSON with no other text, no markdown fences, \
no explanation before or after. The JSON must conform exactly to the schema provided in the user message.

When asked to return document structure as a JSON array, return ONLY the JSON array with no surrounding \
text or markdown.

Your analysis should be thorough enough for a legal professional to use as a first-pass review document. \
Be direct, be specific, and do not minimise risks."""


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> Any:
    """Robustly extract JSON from a Claude response."""
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip ```json … ``` or ``` … ``` code fences
    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Grab the outermost JSON array or object
    for opener, closer in [("[", "]"), ("{", "}")]:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(
        f"Could not extract valid JSON from Claude response. "
        f"First 300 chars: {text[:300]}"
    )


# ── client ────────────────────────────────────────────────────────────────────

class VerilexClient:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY environment variable is not set.")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
        self.max_tokens = int(os.environ.get("CLAUDE_MAX_TOKENS", "8192"))

    def _call_claude(self, user_message: str, max_tokens: int | None = None) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": VERILEX_SYSTEM_PROMPT,
                    # Cache the large system prompt to reduce latency and cost on
                    # repeated calls (5-minute TTL per Anthropic's prompt caching).
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    # ── public methods ────────────────────────────────────────────────────────

    def extract_document_structure(self, text: str, page_count: int) -> list:
        """Return an ordered JSON array of typed document elements."""
        prompt = f"""The following is the full text of a legal document ({page_count} pages).

Analyse its structure and return ONLY a JSON array of document elements in reading order.

Each element must have exactly these three fields:
- "type": one of the following labels —
    header_title  (report/audit header line)
    main_title    (document name / overall title)
    sub_title     (numbered major section heading, e.g. "1. Definitions")
    section_label (sub-heading within a section)
    paragraph     (body text)
    risk_item     (identified risk — prefix text with: "High — ", "Medium — ", or "Low — ")
    citation      (page/section reference, e.g. "[Page 12, §4.2]")
    quote         (verbatim quoted text from the document)
    bullet_point  (list item)
    recommendation (suggested action)
    divider       (visual separator — use empty string for text)
- "text": the content string for this element
- "order": sequential integer starting from 1

Rules:
- The first element should be type "header_title" with text "CONFIDENTIAL | VERILEX AI AUDIT".
- The second element should be type "main_title" with the document title.
- Major numbered headings → sub_title.
- Sub-headings → section_label.
- Body paragraphs → paragraph.
- Any clause that poses a risk → also emit a risk_item element immediately after its paragraph.
- Verbatim extracts → quote.
- Return ONLY the JSON array. No other text whatsoever.

DOCUMENT TEXT:
{text[:60000]}"""

        logger.info("Calling Claude for document structure extraction (%d chars)", len(text))
        raw = self._call_claude(prompt)
        return _parse_json_response(raw)

    def analyze_document(self, text: str, page_count: int, job_id: str) -> dict:
        """Return a full Verilex analysis as a structured dict."""
        schema = """{
  "job_id": "<string>",
  "document_title": "<string>",
  "document_type": "<string>",
  "jurisdiction": "<string>",
  "pages_analysed": <integer>,
  "overall_risk_level": "HIGH" | "MEDIUM" | "LOW",
  "executive_summary": {
    "overview": "<string>",
    "key_observations": ["<string>", "..."],
    "closing_statement": "<string>"
  },
  "contradictions": [
    {
      "id": "C1",
      "severity": "High" | "Medium" | "Low",
      "title": "<string>",
      "clause_a": { "page": <int>, "section": "<string>", "quote": "<verbatim quote>" },
      "clause_b": { "page": <int>, "section": "<string>", "quote": "<verbatim quote>" },
      "summary": "<string>",
      "impact": "<string>",
      "source_evidence": "<string>"
    }
  ],
  "hidden_risks": [
    {
      "id": "R1",
      "severity": "High" | "Medium" | "Low",
      "title": "<string>",
      "citation": { "page": <int>, "section": "<string>", "quote": "<verbatim quote>" },
      "description": "<string>",
      "client_exposure": "<string>",
      "source_evidence": "<string>"
    }
  ],
  "actionable_steps": [
    {
      "step_number": <int>,
      "title": "<string>",
      "addresses": { "page": <int>, "section": "<string>" },
      "actions": ["<string>", "..."],
      "source_evidence": "<string>"
    }
  ],
  "final_recommendations": {
    "execution_statement": "<string>",
    "recommended_actions": [
      { "action": "<string>", "section_reference": "<string>" }
    ],
    "risk_level": "High" | "Medium" | "Low",
    "readiness": "Ready to Execute" | "Requires Revision" | "Do Not Execute"
  }
}"""

        prompt = f"""Perform a complete Verilex AI legal audit of the document below ({page_count} pages).

Return ONLY valid JSON that exactly matches this schema (replace angle-bracket placeholders with real values):

{schema}

Requirements:
- job_id must be exactly: {job_id}
- pages_analysed must be exactly: {page_count}
- Find ALL contradictions (aim for 3+ if present).
- Find ALL hidden risks (aim for 5+ if present).
- Every contradiction and risk MUST include exact page numbers and verbatim quotes.
- source_evidence fields must name the specific pages and sections.
- final_recommendations.execution_statement must be a clear, direct statement.
- Return ONLY the JSON object. No text before or after.

DOCUMENT TEXT:
{text[:90000]}"""

        logger.info(
            "Calling Claude for full document analysis (%d chars, job_id=%s)",
            len(text),
            job_id,
        )
        raw = self._call_claude(prompt)
        return _parse_json_response(raw)
