from __future__ import annotations

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#1a1612")
STAMP = colors.HexColor("#c23b22")
PAPER = colors.HexColor("#efe4cc")
RULE = colors.HexColor("#4a4338")


def _styles():
    base = getSampleStyleSheet()
    return {
        "kicker": ParagraphStyle(
            "Kicker",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=9,
            textColor=STAMP,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "PackTitle",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "PackH",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=12,
            textColor=INK,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "PackBody",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=10,
            leading=14,
            textColor=INK,
        ),
        "small": ParagraphStyle(
            "PackSmall",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            textColor=RULE,
            spaceAfter=8,
        ),
    }


def _p(text: str, style) -> Paragraph:
    raw = escape((text or "").strip()) or "—"
    raw = raw.replace("\n", "<br/>")
    return Paragraph(raw, style)


def build_pack_pdf(session: dict) -> bytes:
    case = session.get("case") or {}
    styles = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=case.get("title") or "BriefRoom case pack",
        author="BriefRoom",
    )
    story = [
        _p("BRIEFROOM  ·  CANDIDATE COPY  ·  CONFIDENTIAL", styles["kicker"]),
        _p(case.get("title") or "Case pack", styles["title"]),
        _p(
            " · ".join(
                x
                for x in (
                    case.get("client"),
                    case.get("industry_label"),
                    case.get("timebox"),
                    session.get("user_name") and f"Candidate: {session.get('user_name')}",
                )
                if x
            ),
            styles["small"],
        ),
        _p("Objective", styles["h"]),
        _p(case.get("objective") or "", styles["body"]),
        _p("Discussion ask", styles["h"]),
        _p(case.get("discussion_ask") or "", styles["body"]),
        _p("Presentation ask", styles["h"]),
        _p(case.get("presentation_ask") or "", styles["body"]),
        _p("Brief", styles["h"]),
        _p(case.get("brief") or "", styles["body"]),
        _p("Constraints", styles["h"]),
    ]
    constraints = case.get("constraints") or []
    if constraints:
        items = [ListItem(_p(str(c), styles["body"]), leftIndent=8) for c in constraints]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    else:
        story.append(_p("None listed.", styles["body"]))
    for i, ex in enumerate(case.get("exhibits") or [], start=1):
        story.append(_p(f"Exhibit {i}: {ex.get('name') or 'Untitled'} ({ex.get('kind') or 'note'})", styles["h"]))
        story.append(_p(ex.get("body") or "", styles["body"]))
    notes = (session.get("notes") or "").strip()
    story.append(_p("Working notes", styles["h"]))
    story.append(_p(notes or "None.", styles["body"]))
    story.append(Spacer(1, 10 * mm))
    stamp = Table(
        [[Paragraph("CONFIDENTIAL — Assessment Centre rehearsal pack. Hidden rubric omitted.", styles["small"])]],
        colWidths=[doc.width],
    )
    stamp.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.2, STAMP),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(stamp)

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(STAMP)
        canvas.setLineWidth(2)
        canvas.line(16 * mm, A4[1] - 12 * mm, 16 * mm, 12 * mm)
        canvas.setFillColor(RULE)
        canvas.setFont("Times-Roman", 8)
        canvas.drawString(18 * mm, 10 * mm, "BriefRoom")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    # Background on each page: draw cream first via onFirstPage/onLaterPages before flowables.
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def pack_filename(session: dict) -> str:
    title = (session.get("case") or {}).get("title") or "case-pack"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    return f"briefroom-{slug or 'case-pack'}.pdf"
