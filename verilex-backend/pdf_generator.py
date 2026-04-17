"""ReportLab PDF report generator for the Verilex AI audit system.

Visual design:
  - Dark navy header bar on every page (drawn on the canvas layer)
  - Clean white body with structured section headers
  - Colour-coded risk severity bands (red / orange / green)
  - Monospace Courier font for verbatim quotes / citations
  - Page numbers in a dark navy footer band
"""

import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────

NAVY        = HexColor("#0d1b2a")
NAVY_MID    = HexColor("#1a3a5c")
WHITE       = colors.white
LIGHT_GREY  = HexColor("#f5f7fa")
BORDER_GREY = HexColor("#dce1e8")
DARK_TEXT   = HexColor("#1a1a2e")
MED_TEXT    = HexColor("#4a5568")

HIGH_FG   = HexColor("#c0392b")
HIGH_BG   = HexColor("#fdf2f0")
MED_FG    = HexColor("#b7770d")
MED_BG    = HexColor("#fef9ec")
LOW_FG    = HexColor("#1e7e34")
LOW_BG    = HexColor("#edfaf1")

# ── Page geometry ─────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = A4
MARGIN        = 20 * mm
CONTENT_W     = PAGE_W - 2 * MARGIN
HEADER_H      = 18 * mm
FOOTER_H      = 12 * mm


# ── Numbered canvas (draws header + footer on every page) ─────────────────────

class _NumberedCanvas(pdf_canvas.Canvas):
    """Defers all page drawings until save() so total page count is known."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []
        self._generated_at = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_chrome(self._pageNumber, total)
            pdf_canvas.Canvas.showPage(self)
        pdf_canvas.Canvas.save(self)

    def _draw_chrome(self, page_num: int, total: int):
        self.saveState()

        # ── Header bar ───────────────────────────────────────────────────────
        self.setFillColor(NAVY)
        self.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)

        self.setFillColor(WHITE)
        self.setFont("Helvetica-Bold", 9)
        self.drawString(MARGIN, PAGE_H - 11 * mm, "CONFIDENTIAL  |  VERILEX AI AUDIT")

        self.setFont("Helvetica", 8)
        self.drawRightString(
            PAGE_W - MARGIN,
            PAGE_H - 11 * mm,
            f"Generated: {self._generated_at}",
        )

        # ── Footer bar ───────────────────────────────────────────────────────
        self.setFillColor(NAVY)
        self.rect(0, 0, PAGE_W, FOOTER_H, fill=1, stroke=0)

        self.setFillColor(WHITE)
        self.setFont("Helvetica-Bold", 8)
        self.drawCentredString(PAGE_W / 2, 4 * mm, f"Page {page_num} of {total}")

        self.setFont("Helvetica", 7)
        self.drawString(MARGIN, 4 * mm, "VERILEX AI — Confidential Legal Analysis")
        self.drawRightString(PAGE_W - MARGIN, 4 * mm, "For Authorised Use Only")

        self.restoreState()


# ── Style definitions ─────────────────────────────────────────────────────────

def _styles() -> dict:
    def ps(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    return {
        "report_title": ps(
            "report_title",
            fontName="Helvetica-Bold", fontSize=20,
            textColor=NAVY, spaceAfter=4, leading=26,
        ),
        "section_hdr": ps(
            "section_hdr",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=WHITE, leading=16,
        ),
        "sub_hdr": ps(
            "sub_hdr",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=NAVY, spaceBefore=6, spaceAfter=3, leading=15,
        ),
        "body": ps(
            "body",
            fontName="Helvetica", fontSize=10,
            textColor=DARK_TEXT, spaceAfter=3, leading=14,
            alignment=TA_JUSTIFY,
        ),
        "mono": ps(
            "mono",
            fontName="Courier", fontSize=9,
            textColor=DARK_TEXT, spaceAfter=3, leading=13,
            leftIndent=4, rightIndent=4,
        ),
        "label": ps(
            "label",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=MED_TEXT, spaceAfter=2, leading=12,
        ),
        "italic_sm": ps(
            "italic_sm",
            fontName="Helvetica-Oblique", fontSize=9,
            textColor=MED_TEXT, spaceAfter=2, leading=12,
        ),
        "bullet": ps(
            "bullet",
            fontName="Helvetica", fontSize=10,
            textColor=DARK_TEXT, spaceAfter=2, leading=14,
            leftIndent=12,
        ),
        "badge": ps(
            "badge",
            fontName="Helvetica-Bold", fontSize=9,
            alignment=TA_RIGHT,
        ),
        "item_title": ps(
            "item_title",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=WHITE, leading=14,
        ),
        "item_id": ps(
            "item_id",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=WHITE, leading=14,
        ),
        "exec_banner": ps(
            "exec_banner",
            fontName="Helvetica-Bold", fontSize=12,
            alignment=TA_CENTER, leading=16,
        ),
        "step_title": ps(
            "step_title",
            fontName="Helvetica-Bold", fontSize=11,
            textColor=NAVY, leading=15,
        ),
    }


# ── Small utilities ───────────────────────────────────────────────────────────

def _severity_colours(severity: str) -> tuple:
    """Return (fg_colour, bg_colour, label_text) for a severity string."""
    s = (severity or "").lower()
    if s == "high":
        return HIGH_FG, HIGH_BG, "HIGH"
    if s == "medium":
        return MED_FG, MED_BG, "MEDIUM"
    return LOW_FG, LOW_BG, "LOW"


def _section_header(title: str, st: dict) -> Table:
    """Full-width dark navy section header bar."""
    tbl = Table(
        [[Paragraph(title, st["section_hdr"])]],
        colWidths=[CONTENT_W],
    )
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    return tbl


def _two_col_detail(rows: list[tuple], st: dict, label_w: float = 30 * mm) -> Table:
    """Two-column table: grey label column + white content column."""
    tbl = Table(rows, colWidths=[label_w, CONTENT_W - label_w])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), LIGHT_GREY),
            ("BACKGROUND",    (1, 0), (1, -1), WHITE),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, BORDER_GREY),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ])
    )
    return tbl


def _item_header_table(id_text: str, title: str, severity: str, st: dict) -> Table:
    """Coloured header row for a contradiction or risk item."""
    fg, _, label = _severity_colours(severity)
    badge_style = ParagraphStyle(
        "badge_dyn",
        parent=st["badge"],
        textColor=fg,
    )
    tbl = Table(
        [[
            Paragraph(id_text, st["item_id"]),
            Paragraph(title,   st["item_title"]),
            Paragraph(label,   badge_style),
        ]],
        colWidths=[16 * mm, CONTENT_W - 46 * mm, 26 * mm],
    )
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), NAVY_MID),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    return tbl


def _cite(citation: dict) -> str:
    page    = citation.get("page", "?")
    section = citation.get("section", "")
    quote   = citation.get("quote", "")
    parts   = [f"[Page {page}"]
    if section:
        parts.append(f"  {section}")
    parts.append("]")
    header = "".join(parts)
    if quote:
        return f'{header}\n"{quote}"'
    return header


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_pdf_report(analysis: dict) -> bytes:
    """Generate a Verilex audit PDF from an analysis dict and return bytes."""
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=HEADER_H + 6 * mm,
        bottomMargin=FOOTER_H + 6 * mm,
        title="Verilex AI Legal Audit",
        author="Verilex AI",
        subject=analysis.get("document_title", "Legal Document"),
    )

    st = _styles()
    story = []

    # ── Cover information ─────────────────────────────────────────────────────
    doc_title   = analysis.get("document_title", "Legal Document")
    doc_type    = analysis.get("document_type", "Contract")
    jurisdiction = analysis.get("jurisdiction", "Not specified")
    pages_done  = analysis.get("pages_analysed", 0)
    risk_level  = analysis.get("overall_risk_level", "HIGH")
    job_id      = analysis.get("job_id", "")

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("VERILEX AI LEGAL AUDIT REPORT", st["report_title"]))
    story.append(
        HRFlowable(width=CONTENT_W, thickness=2.5, color=NAVY, spaceAfter=6)
    )

    # Meta table
    meta_rows = [
        [Paragraph("<b>Document</b>",       st["label"]), Paragraph(doc_title,    st["body"])],
        [Paragraph("<b>Document Type</b>",  st["label"]), Paragraph(doc_type,     st["body"])],
        [Paragraph("<b>Jurisdiction</b>",   st["label"]), Paragraph(jurisdiction, st["body"])],
        [Paragraph("<b>Pages Analysed</b>", st["label"]), Paragraph(str(pages_done), st["body"])],
        [Paragraph("<b>Job ID</b>",         st["label"]), Paragraph(job_id,       st["body"])],
        [
            Paragraph("<b>Analysis Date</b>", st["label"]),
            Paragraph(datetime.utcnow().strftime("%d %B %Y, %H:%M UTC"), st["body"]),
        ],
    ]
    meta_tbl = Table(meta_rows, colWidths=[38 * mm, CONTENT_W - 38 * mm])
    meta_tbl.setStyle(
        TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), LIGHT_GREY),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(meta_tbl)
    story.append(Spacer(1, 5 * mm))

    # Overall risk banner
    risk_fg, risk_bg, risk_lbl = _severity_colours(risk_level)
    banner_style = ParagraphStyle(
        "risk_banner", fontName="Helvetica-Bold", fontSize=13,
        textColor=risk_fg, alignment=TA_CENTER,
    )
    banner_tbl = Table(
        [[Paragraph(f"OVERALL RISK ASSESSMENT:  {risk_lbl}", banner_style)]],
        colWidths=[CONTENT_W],
    )
    banner_tbl.setStyle(
        TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), risk_bg),
            ("BOX",           (0, 0), (-1, -1), 2, risk_fg),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(banner_tbl)
    story.append(Spacer(1, 7 * mm))

    # ── Executive Summary ─────────────────────────────────────────────────────
    exec_sum = analysis.get("executive_summary") or {}
    story.append(_section_header("EXECUTIVE SUMMARY", st))
    story.append(Spacer(1, 4 * mm))

    if exec_sum.get("overview"):
        story.append(Paragraph(exec_sum["overview"], st["body"]))
        story.append(Spacer(1, 3 * mm))

    key_obs = exec_sum.get("key_observations") or []
    if key_obs:
        story.append(Paragraph("<b>Key Observations</b>", st["sub_hdr"]))
        for obs in key_obs:
            story.append(Paragraph(f"• {obs}", st["bullet"]))
        story.append(Spacer(1, 3 * mm))

    if exec_sum.get("closing_statement"):
        story.append(Paragraph(exec_sum["closing_statement"], st["body"]))
    story.append(Spacer(1, 7 * mm))

    # ── Contradictions ────────────────────────────────────────────────────────
    contradictions = analysis.get("contradictions") or []
    if contradictions:
        story.append(
            _section_header(f"CONTRADICTIONS IDENTIFIED  ({len(contradictions)})", st)
        )
        story.append(Spacer(1, 4 * mm))

        for item in contradictions:
            sev = item.get("severity", "Medium")
            ca  = item.get("clause_a") or {}
            cb  = item.get("clause_b") or {}

            detail_rows = [
                [Paragraph("<b>Clause A</b>", st["label"]),
                 Paragraph(_cite(ca), st["mono"])],
                [Paragraph("<b>Clause B</b>", st["label"]),
                 Paragraph(_cite(cb), st["mono"])],
                [Paragraph("<b>Summary</b>", st["label"]),
                 Paragraph(item.get("summary", ""), st["body"])],
                [Paragraph("<b>Impact</b>", st["label"]),
                 Paragraph(item.get("impact", ""), st["body"])],
                [Paragraph("<b>Evidence</b>", st["label"]),
                 Paragraph(item.get("source_evidence", ""), st["italic_sm"])],
            ]

            block = [
                _item_header_table(
                    item.get("id", ""),
                    item.get("title", ""),
                    sev, st,
                ),
                _two_col_detail(detail_rows, st, label_w=28 * mm),
                Spacer(1, 5 * mm),
            ]
            story.append(KeepTogether(block[:2]))
            story.append(block[2])

    # ── Hidden Risks ──────────────────────────────────────────────────────────
    hidden_risks = analysis.get("hidden_risks") or []
    if hidden_risks:
        story.append(
            _section_header(f"HIDDEN RISKS IDENTIFIED  ({len(hidden_risks)})", st)
        )
        story.append(Spacer(1, 4 * mm))

        for item in hidden_risks:
            sev = item.get("severity", "Medium")
            cit = item.get("citation") or {}

            detail_rows = [
                [Paragraph("<b>Citation</b>", st["label"]),
                 Paragraph(_cite(cit), st["mono"])],
                [Paragraph("<b>Description</b>", st["label"]),
                 Paragraph(item.get("description", ""), st["body"])],
                [Paragraph("<b>Client Exposure</b>", st["label"]),
                 Paragraph(item.get("client_exposure", ""), st["body"])],
                [Paragraph("<b>Evidence</b>", st["label"]),
                 Paragraph(item.get("source_evidence", ""), st["italic_sm"])],
            ]

            block = [
                _item_header_table(
                    item.get("id", ""),
                    item.get("title", ""),
                    sev, st,
                ),
                _two_col_detail(detail_rows, st, label_w=33 * mm),
                Spacer(1, 5 * mm),
            ]
            story.append(KeepTogether(block[:2]))
            story.append(block[2])

    # ── Actionable Steps ──────────────────────────────────────────────────────
    steps = analysis.get("actionable_steps") or []
    if steps:
        story.append(_section_header(f"ACTIONABLE STEPS  ({len(steps)})", st))
        story.append(Spacer(1, 4 * mm))

        for step in steps:
            num    = step.get("step_number", "")
            title  = step.get("title", "")
            addr   = step.get("addresses") or {}
            acts   = step.get("actions") or []
            evid   = step.get("source_evidence", "")

            addr_str = f"Page {addr.get('page', '?')}  {addr.get('section', '')}".strip()

            inner_rows: list = [
                [Paragraph(f"Step {num}:  {title}", st["step_title"])],
                [Paragraph(f"Addresses:  {addr_str}", st["label"])],
            ]
            for act in acts:
                inner_rows.append([Paragraph(f"[+]  {act}", st["bullet"])])
            if evid:
                inner_rows.append([Paragraph(evid, st["italic_sm"])])

            step_tbl = Table(
                [[row[0]] for row in inner_rows],
                colWidths=[CONTENT_W],
            )
            step_tbl.setStyle(
                TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
                    ("TOPPADDING",    (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("BOX",           (0, 0), (-1, -1), 0.5, BORDER_GREY),
                    ("LINEBELOW",     (0, 0), (-1, 0),  1.5, NAVY),
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ])
            )
            story.append(KeepTogether([step_tbl, Spacer(1, 4 * mm)]))

    # ── Final Recommendations ─────────────────────────────────────────────────
    final = analysis.get("final_recommendations") or {}
    if final:
        story.append(_section_header("FINAL RECOMMENDATIONS", st))
        story.append(Spacer(1, 4 * mm))

        exec_stmt  = final.get("execution_statement", "")
        readiness  = final.get("readiness", "")
        rec_risk   = final.get("risk_level", "High")
        rec_acts   = final.get("recommended_actions") or []

        if exec_stmt:
            r_fg, r_bg, _ = _severity_colours(rec_risk)
            stmt_style = ParagraphStyle(
                "exec_stmt",
                fontName="Helvetica-Bold", fontSize=11,
                textColor=r_fg, alignment=TA_CENTER, leading=16,
            )
            stmt_tbl = Table(
                [[Paragraph(exec_stmt, stmt_style)]],
                colWidths=[CONTENT_W],
            )
            stmt_tbl.setStyle(
                TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), r_bg),
                    ("BOX",           (0, 0), (-1, -1), 2, r_fg),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 12),
                    ("TOPPADDING",    (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ])
            )
            story.append(stmt_tbl)
            story.append(Spacer(1, 4 * mm))

        if readiness:
            story.append(
                Paragraph(f"<b>Contract Readiness:</b>  {readiness}", st["sub_hdr"])
            )
            story.append(Spacer(1, 3 * mm))

        if rec_acts:
            story.append(Paragraph("<b>Recommended Actions</b>", st["sub_hdr"]))
            for ra in rec_acts:
                act_text = ra.get("action", "")
                sect_ref = ra.get("section_reference", "")
                suffix   = f"  <i>({sect_ref})</i>" if sect_ref else ""
                story.append(Paragraph(f"• {act_text}{suffix}", st["bullet"]))

    # ── Build ─────────────────────────────────────────────────────────────────
    logger.info("Building PDF report for job_id=%s", analysis.get("job_id", ""))
    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()
