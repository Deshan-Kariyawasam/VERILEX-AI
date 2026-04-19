"""Verilex AI branded PDF report generator.

Matches the Verilex UI mockup:
  - White background, logo in page header
  - Numbered section headings (no dark bars)
  - Left-bordered risk cards with light tinted backgrounds
  - Green-badge step indicators for actionable steps
  - Compliance-badge footer on every page
"""

import io
import os
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    HRFlowable, KeepTogether, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY        = HexColor("#1c2b4a")
BLUE        = HexColor("#2563eb")
GREY_DARK   = HexColor("#374151")
GREY_MID    = HexColor("#6b7280")
BORDER_GREY = HexColor("#e5e7eb")
WHITE       = colors.white

HIGH_FG = HexColor("#dc2626");  HIGH_BG = HexColor("#fef2f2")
MED_FG  = HexColor("#d97706");  MED_BG  = HexColor("#fffbeb")
LOW_FG  = HexColor("#16a34a");  LOW_BG  = HexColor("#f0fdf4")

# ── Geometry ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN    = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN
HEADER_H  = 20 * mm
FOOTER_H  = 16 * mm


# ── Severity helper ───────────────────────────────────────────────────────────
def _sev(s: str):
    k = (s or "").lower()
    if k == "high":   return HIGH_FG, HIGH_BG, "HIGH"
    if k == "medium": return MED_FG,  MED_BG,  "MEDIUM"
    return LOW_FG, LOW_BG, "LOW"


# ── Per-page chrome canvas ────────────────────────────────────────────────────
class _Canvas(pdf_canvas.Canvas):
    def __init__(self, *args, logo_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: list[dict] = []
        self._logo = logo_path
        self._date = datetime.now().strftime("%Y-%m-%d")

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._chrome(self._pageNumber, n)
            pdf_canvas.Canvas.showPage(self)
        pdf_canvas.Canvas.save(self)

    # ── header ────────────────────────────────────────────────────────────────
    def _draw_logo(self):
        drawn = False
        if self._logo and os.path.isfile(self._logo):
            try:
                ir = ImageReader(self._logo)
                iw, ih = ir.getSize()
                target_h = HEADER_H - 5 * mm
                scale    = target_h / ih
                self.drawImage(
                    self._logo,
                    MARGIN, PAGE_H - HEADER_H + 2.5 * mm,
                    width=iw * scale, height=target_h,
                    mask="auto",
                )
                drawn = True
            except Exception:
                pass
        if not drawn:
            # text fallback
            self.setFillColor(BLUE)
            self.setFont("Helvetica-Bold", 14)
            self.drawString(MARGIN, PAGE_H - 10 * mm, "V")
            self.setFillColor(NAVY)
            self.setFont("Helvetica-Bold", 12)
            self.drawString(MARGIN + 8 * mm, PAGE_H - 10 * mm, "VERILEX")
            self.setFillColor(GREY_MID)
            self.setFont("Helvetica", 6.5)
            self.drawString(MARGIN + 8 * mm, PAGE_H - 15 * mm, "ADVANCED LEGAL INTELLIGENCE")

    def _header(self):
        self._draw_logo()
        # right-side badge
        self.setFont("Helvetica", 7.5)
        self.setFillColor(GREY_MID)
        self.drawRightString(PAGE_W - MARGIN, PAGE_H - 10 * mm,
                             "CONFIDENTIAL  |  VERILEX AI AUDIT")
        self.drawRightString(PAGE_W - MARGIN, PAGE_H - 15 * mm, self._date)
        # bottom rule
        self.setStrokeColor(BORDER_GREY)
        self.setLineWidth(0.5)
        self.line(MARGIN, PAGE_H - HEADER_H, PAGE_W - MARGIN, PAGE_H - HEADER_H)

    # ── footer ────────────────────────────────────────────────────────────────
    def _footer(self, page: int, total: int):
        self.setStrokeColor(BORDER_GREY)
        self.setLineWidth(0.5)
        self.line(MARGIN, FOOTER_H, PAGE_W - MARGIN, FOOTER_H)

        badges = [
            "AI Clause Analysis",
            "Verbatim Citations",
            "Live Claude Analysis",
            "Data Privacy Compliant",
        ]
        bw = CONTENT_W / len(badges)
        self.setFont("Helvetica", 6.5)
        self.setFillColor(GREY_MID)
        for i, b in enumerate(badges):
            self.drawCentredString(MARGIN + i * bw + bw / 2, FOOTER_H - 5 * mm, b)

        self.setFont("Helvetica", 7)
        self.drawCentredString(PAGE_W / 2, FOOTER_H - 10 * mm, f"Page {page} of {total}")

    def _chrome(self, page: int, total: int):
        self.saveState()
        self._header()
        self._footer(page, total)
        self.restoreState()


# ── Styles ────────────────────────────────────────────────────────────────────
def _styles() -> dict:
    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "doc_title": ps("doc_title", fontName="Helvetica-Bold", fontSize=18,
                        textColor=NAVY, leading=24, spaceAfter=4),
        "doc_meta":  ps("doc_meta",  fontName="Helvetica", fontSize=9,
                        textColor=GREY_MID, spaceAfter=2),
        "sec_head":  ps("sec_head",  fontName="Helvetica-Bold", fontSize=15,
                        textColor=NAVY, leading=20, spaceBefore=8, spaceAfter=2),
        "body":      ps("body",      fontName="Helvetica", fontSize=10,
                        textColor=GREY_DARK, leading=14, spaceAfter=3,
                        alignment=TA_JUSTIFY),
        "bullet":    ps("bullet",    fontName="Helvetica", fontSize=9.5,
                        textColor=GREY_DARK, leading=13, spaceAfter=1, leftIndent=12),
        "card_lbl":  ps("card_lbl",  fontName="Helvetica-Bold", fontSize=9,
                        textColor=GREY_DARK, spaceAfter=1, leading=12),
        "card_val":  ps("card_val",  fontName="Helvetica", fontSize=9.5,
                        textColor=GREY_DARK, leading=13, spaceAfter=5,
                        alignment=TA_JUSTIFY),
        "step_head": ps("step_head", fontName="Helvetica-Bold", fontSize=11,
                        textColor=NAVY, leading=15, spaceAfter=3),
        "badge_txt": ps("badge_txt", fontName="Helvetica-Bold", fontSize=9,
                        textColor=WHITE, alignment=TA_CENTER),
        "rec_box":   ps("rec_box",   fontName="Helvetica-Bold", fontSize=11,
                        textColor=HIGH_FG, leading=16, alignment=TA_CENTER),
        "rec_lbl":   ps("rec_lbl",   fontName="Helvetica-Bold", fontSize=10,
                        textColor=NAVY, spaceAfter=3),
    }


# ── Section heading ───────────────────────────────────────────────────────────
def _section(n: int, title: str, st: dict) -> list:
    return [
        Paragraph(f"{n}. {title}", st["sec_head"]),
        HRFlowable(width=CONTENT_W, thickness=0.75, color=BORDER_GREY, spaceAfter=4),
        Spacer(1, 2 * mm),
    ]


# ── Risk card ─────────────────────────────────────────────────────────────────
def _card(title: str, severity: str, fields: list, st: dict) -> Table:
    """Left-bordered card.  fields = list of (label, value) tuples."""
    fg, bg, label = _sev(severity)

    title_style = ParagraphStyle(
        "ct", fontName="Helvetica-Bold", fontSize=10,
        textColor=fg, leading=14, spaceAfter=6,
    )

    paras = [Paragraph(f"{label}  —  {title}", title_style)]
    for lbl, val in fields:
        if not val:
            continue
        if lbl:
            paras.append(Paragraph(lbl, st["card_lbl"]))
        paras.append(Paragraph(val, st["card_val"]))

    inner_w = CONTENT_W - 6
    inner = Table([[p] for p in paras], colWidths=[inner_w])
    inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1,  0), 10),
        ("TOPPADDING",    (0, 1), (-1, -1),  2),
        ("BOTTOMPADDING", (0, 0), (-1, -2),  2),
        ("BOTTOMPADDING", (0,-1), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    # 2-col wrapper: thin colored left strip | content
    card = Table([[Spacer(6, 1), inner]], colWidths=[6, inner_w])
    card.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), fg),
        ("BACKGROUND",    (1, 0), (1, -1), bg),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return card


# ── Citation text ─────────────────────────────────────────────────────────────
def _cite(cit: dict) -> str:
    page    = cit.get("page", "?")
    section = cit.get("section", "")
    quote   = cit.get("quote", "")
    ref = f"Page {page}" + (f",  {section}" if section else "")
    return ref + (f'  —  "{quote}"' if quote else "")


# ── Step row ──────────────────────────────────────────────────────────────────
def _step_header(n, title: str, st: dict) -> Table:
    """Green badge + bold step title in a single table row."""
    tbl = Table(
        [[Paragraph(">", st["badge_txt"]),
          Paragraph(f"Step {n}  —  {title}", st["step_head"])]],
        colWidths=[8 * mm, CONTENT_W - 8 * mm],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), LOW_FG),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Main ──────────────────────────────────────────────────────────────────────
def generate_pdf_report(analysis: dict, logo_path: str | None = None) -> bytes:
    """Return Verilex-branded PDF bytes for *analysis*."""

    # auto-discover logo next to this script
    if logo_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        for name in ("verilex_logo.png", "verilex_logo.jpg",
                     "verilex_logo.jpeg", "logo.png", "logo.jpg"):
            candidate = os.path.join(here, name)
            if os.path.isfile(candidate):
                logo_path = candidate
                break

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=HEADER_H + 6 * mm, bottomMargin=FOOTER_H + 6 * mm,
        title="Verilex AI Legal Audit",
        author="Verilex AI",
        subject=analysis.get("document_title", "Legal Document"),
    )

    st    = _styles()
    story = []

    # ── Document header block ─────────────────────────────────────────────────
    doc_title    = analysis.get("document_title", "Legal Document")
    doc_type     = analysis.get("document_type", "")
    jurisdiction = analysis.get("jurisdiction", "")
    pages_done   = analysis.get("pages_analysed", 0)
    overall_risk = analysis.get("overall_risk_level", "HIGH")
    risk_fg, _, risk_lbl = _sev(overall_risk)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(doc_title, st["doc_title"]))

    meta_parts = [p for p in [doc_type, jurisdiction,
                               f"{pages_done} pages analysed" if pages_done else ""]
                  if p]
    if meta_parts:
        story.append(Paragraph("  |  ".join(meta_parts), st["doc_meta"]))

    story.append(Paragraph(
        f"Overall Risk:  "
        f'<font color="{risk_fg.hexval()}"><b>{risk_lbl}</b></font>',
        st["doc_meta"],
    ))
    story.append(HRFlowable(width=CONTENT_W, thickness=1,
                             color=BORDER_GREY, spaceAfter=6))
    story.append(Spacer(1, 4 * mm))

    # ── 1. Executive Summary ──────────────────────────────────────────────────
    es = analysis.get("executive_summary") or {}
    story += _section(1, "Executive Summary", st)

    if es.get("overview"):
        story.append(Paragraph(es["overview"], st["body"]))
        story.append(Spacer(1, 3 * mm))

    obs = es.get("key_observations") or []
    if obs:
        story.append(Paragraph("Key observations include:", st["body"]))
        for o in obs:
            story.append(Paragraph(f"•  {o}", st["bullet"]))
        story.append(Spacer(1, 3 * mm))

    if es.get("closing_statement"):
        story.append(Paragraph(es["closing_statement"], st["body"]))
    story.append(Spacer(1, 6 * mm))

    # ── 2. Contradictions ─────────────────────────────────────────────────────
    contras = analysis.get("contradictions") or []
    story += _section(2, "Contradictions", st)
    if not contras:
        story.append(Paragraph("No contradictions identified.", st["body"]))

    for c in contras:
        ca = c.get("clause_a") or {}
        cb = c.get("clause_b") or {}
        fields = [
            ("Summary:",  c.get("summary", "")),
            ("Impact:",   c.get("impact", "")),
            ("Clause A:", _cite(ca) if ca else ""),
            ("Clause B:", _cite(cb) if cb else ""),
            ("Citation:", c.get("source_evidence", "")),
        ]
        story.append(KeepTogether([
            _card(c.get("title", ""), c.get("severity", "Medium"), fields, st),
            Spacer(1, 4 * mm),
        ]))
    story.append(Spacer(1, 4 * mm))

    # ── 3. Hidden Risks ───────────────────────────────────────────────────────
    risks = analysis.get("hidden_risks") or []
    story += _section(3, "Hidden Risks", st)
    if not risks:
        story.append(Paragraph("No hidden risks identified.", st["body"]))

    for r in risks:
        cit = r.get("citation") or {}
        fields = [
            ("Description:", r.get("description", "")),
            ("Risk:",         r.get("client_exposure", "")),
            ("Citation:",     _cite(cit) if cit else r.get("source_evidence", "")),
        ]
        story.append(KeepTogether([
            _card(r.get("title", ""), r.get("severity", "Medium"), fields, st),
            Spacer(1, 4 * mm),
        ]))
    story.append(Spacer(1, 4 * mm))

    # ── 4. Actionable Steps ───────────────────────────────────────────────────
    steps = analysis.get("actionable_steps") or []
    story += _section(4, "Actionable Steps", st)

    for step in steps:
        n     = step.get("step_number", "")
        title = step.get("title", "")
        acts  = step.get("actions") or []
        addr  = step.get("addresses") or {}

        block = [_step_header(n, title, st)]
        for a in acts:
            block.append(Paragraph(f"•  {a}", st["bullet"]))
        if addr:
            addr_str = f"Page {addr.get('page','?')}  {addr.get('section','')}".strip()
            block.append(Paragraph(addr_str, st["doc_meta"]))
        block.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(block))

    story.append(Spacer(1, 4 * mm))

    # ── 5. Final Recommendations ──────────────────────────────────────────────
    final = analysis.get("final_recommendations") or {}
    story += _section(5, "Final Recommendations", st)

    exec_stmt = final.get("execution_statement", "")
    if exec_stmt:
        box = Table([[Paragraph(exec_stmt, st["rec_box"])]], colWidths=[CONTENT_W])
        box.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), HIGH_BG),
            ("BOX",           (0, 0), (-1, -1), 1.5, HIGH_FG),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("TOPPADDING",    (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(box)
        story.append(Spacer(1, 5 * mm))

    rec_acts = final.get("recommended_actions") or []
    if rec_acts:
        story.append(Paragraph("Recommended Actions:", st["rec_lbl"]))
        for ra in rec_acts:
            act = ra.get("action", "")
            ref = ra.get("section_reference", "")
            story.append(Paragraph(
                f"•  {act}" + (f"  ({ref})" if ref else ""),
                st["bullet"],
            ))
        story.append(Spacer(1, 4 * mm))

    readiness  = final.get("readiness", "")
    risk_level = final.get("risk_level", "")
    if readiness or risk_level:
        story.append(Paragraph("Final Assessment:", st["rec_lbl"]))
        if risk_level:
            story.append(Paragraph(f"Risk Level:  {risk_level}", st["body"]))
        if readiness:
            story.append(Paragraph(f"Readiness:  {readiness}", st["body"]))

    # ── Build ─────────────────────────────────────────────────────────────────
    def _make_canvas(*args, **kwargs):
        return _Canvas(*args, logo_path=logo_path, **kwargs)

    logger.info("Building Verilex PDF  job=%s", analysis.get("job_id"))
    doc.build(story, canvasmaker=_make_canvas)
    return buf.getvalue()