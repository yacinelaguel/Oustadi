# =============================================================================
#  OSTADI — أستاذي
#  RTL Arabic PDF Export Engine
#  Architect: Yacine Laguel
#  File: backend/pdf_exporter.py
#
#  Responsibilities:
#    1. Build the official Algerian Ministry exam header on every page
#    2. Render the full exam body (text passage + sections + questions)
#    3. Build a separate correction PDF with the grading scale
#    4. Handle all Arabic RTL text shaping via arabic_reshaper + python-bidi
#    5. Embed the Amiri font (Regular + Bold) for all Arabic text
#    6. Apply professional page margins, line heights, and dotted fields
#
#  Dependencies:
#    pip install reportlab arabic-reshaper python-bidi
#
#  Both build_exam_pdf() and build_correction_pdf() are called
#  exclusively by main.py → generate_exam()
# =============================================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

# ---------------------------------------------------------------------------
# MODULE LOGGER
# ---------------------------------------------------------------------------
log = logging.getLogger("ostadi.pdf_exporter")

# ---------------------------------------------------------------------------
# PAGE GEOMETRY
# ---------------------------------------------------------------------------
PAGE_WIDTH, PAGE_HEIGHT = A4          # 210mm × 297mm
MARGIN_TOP    = 1.8 * cm
MARGIN_BOTTOM = 2.0 * cm
MARGIN_LEFT   = 2.0 * cm
MARGIN_RIGHT  = 2.0 * cm

CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

# ---------------------------------------------------------------------------
# COLOUR PALETTE
# ---------------------------------------------------------------------------
COLOR_BLACK        = colors.HexColor("#000000")
COLOR_DARK_GREY    = colors.HexColor("#1A1A1A")
COLOR_MID_GREY     = colors.HexColor("#4A4A4A")
COLOR_LIGHT_GREY   = colors.HexColor("#E8E8E8")
COLOR_HEADER_BG    = colors.HexColor("#F4F6FA")
COLOR_ACCENT_BLUE  = colors.HexColor("#1A3A6B")   # Ministry dark navy
COLOR_RULE         = colors.HexColor("#2B4C8C")   # Ministry rule line blue

# ---------------------------------------------------------------------------
# FONT REGISTRATION FLAGS
# ---------------------------------------------------------------------------
_FONTS_REGISTERED = False


# =============================================================================
#  SECTION 1: FONT REGISTRATION
# =============================================================================

def _register_fonts(fonts_dir: Path) -> None:
    """
    Registers Amiri Regular and Amiri Bold with ReportLab's font registry.
    Called once per process — subsequent calls are no-ops.
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    amiri_regular = fonts_dir / "Amiri-Regular.ttf"
    amiri_bold    = fonts_dir / "Amiri-Bold.ttf"

    for path, name in [(amiri_regular, "Amiri"), (amiri_bold, "Amiri-Bold")]:
        if not path.exists():
            raise FileNotFoundError(
                f"Font file not found: {path}\n"
                "Download Amiri from https://fonts.google.com/specimen/Amiri"
            )
        pdfmetrics.registerFont(TTFont(name, str(path)))
        log.debug(f"Registered font '{name}' from {path.name}")

    _FONTS_REGISTERED = True
    log.info("Amiri fonts registered with ReportLab")


# =============================================================================
#  SECTION 2: ARABIC TEXT SHAPER
#  Every Arabic string must pass through this function before
#  being handed to ReportLab. Skipping this produces reversed,
#  unconnected glyphs.
# =============================================================================

def _shape(text: str) -> str:
    """
    Reshapes Arabic text for correct glyph joining and applies
    the Unicode BiDi algorithm to produce left-to-right display order
    that ReportLab can render correctly in RTL context.

    Args:
        text: Raw Arabic (or mixed) string.

    Returns:
        Visually correct, display-ready string for ReportLab.
    """
    if not text or not text.strip():
        return text

    try:
        reshaped  = arabic_reshaper.reshape(text)
        displayed = get_display(reshaped)
        return displayed
    except Exception as exc:
        log.warning(f"Arabic reshaping failed for text snippet: {text[:40]!r} — {exc}")
        return text   # Return original as fallback


# =============================================================================
#  SECTION 3: PARAGRAPH STYLE FACTORY
# =============================================================================

def _build_styles() -> Dict[str, ParagraphStyle]:
    """
    Constructs and returns all named ParagraphStyle objects used
    throughout the PDF. All Arabic styles use Amiri and are right-aligned.
    """
    styles: Dict[str, ParagraphStyle] = {}

    # ---- Ministry Header Styles ----
    styles["header_republic"] = ParagraphStyle(
        name="header_republic",
        fontName="Amiri-Bold",
        fontSize=9,
        leading=13,
        alignment=TA_RIGHT,
        textColor=COLOR_ACCENT_BLUE,
        spaceAfter=0,
    )

    styles["header_ministry"] = ParagraphStyle(
        name="header_ministry",
        fontName="Amiri-Bold",
        fontSize=9,
        leading=13,
        alignment=TA_RIGHT,
        textColor=COLOR_ACCENT_BLUE,
        spaceAfter=0,
    )

    styles["header_left_label"] = ParagraphStyle(
        name="header_left_label",
        fontName="Amiri",
        fontSize=9,
        leading=14,
        alignment=TA_LEFT,
        textColor=COLOR_DARK_GREY,
        spaceAfter=0,
    )

    styles["header_center_title"] = ParagraphStyle(
        name="header_center_title",
        fontName="Amiri-Bold",
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        textColor=COLOR_ACCENT_BLUE,
        spaceBefore=4,
        spaceAfter=4,
    )

    styles["header_meta"] = ParagraphStyle(
        name="header_meta",
        fontName="Amiri",
        fontSize=9,
        leading=14,
        alignment=TA_CENTER,
        textColor=COLOR_DARK_GREY,
        spaceAfter=0,
    )

    # ---- Body Styles ----
    styles["section_title"] = ParagraphStyle(
        name="section_title",
        fontName="Amiri-Bold",
        fontSize=12,
        leading=18,
        alignment=TA_RIGHT,
        textColor=COLOR_ACCENT_BLUE,
        spaceBefore=10,
        spaceAfter=4,
        leftIndent=0,
        rightIndent=0,
    )

    styles["section_points_badge"] = ParagraphStyle(
        name="section_points_badge",
        fontName="Amiri-Bold",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        textColor=COLOR_ACCENT_BLUE,
    )

    styles["passage_text"] = ParagraphStyle(
        name="passage_text",
        fontName="Amiri",
        fontSize=11,
        leading=20,
        alignment=TA_RIGHT,
        textColor=COLOR_DARK_GREY,
        spaceBefore=6,
        spaceAfter=6,
        rightIndent=8,
        leftIndent=8,
        borderPadding=(6, 8, 6, 8),
        borderColor=COLOR_LIGHT_GREY,
        borderWidth=0.5,
        borderRadius=2,
        backColor=COLOR_HEADER_BG,
    )

    styles["question_text"] = ParagraphStyle(
        name="question_text",
        fontName="Amiri-Bold",
        fontSize=11,
        leading=17,
        alignment=TA_RIGHT,
        textColor=COLOR_DARK_GREY,
        spaceBefore=5,
        spaceAfter=2,
        rightIndent=4,
    )

    styles["sub_question_text"] = ParagraphStyle(
        name="sub_question_text",
        fontName="Amiri",
        fontSize=10.5,
        leading=16,
        alignment=TA_RIGHT,
        textColor=COLOR_DARK_GREY,
        spaceBefore=2,
        spaceAfter=2,
        rightIndent=16,
        leftIndent=0,
    )

    styles["points_inline"] = ParagraphStyle(
        name="points_inline",
        fontName="Amiri-Bold",
        fontSize=9.5,
        leading=14,
        alignment=TA_LEFT,
        textColor=COLOR_ACCENT_BLUE,
    )

    styles["correction_answer"] = ParagraphStyle(
        name="correction_answer",
        fontName="Amiri",
        fontSize=10.5,
        leading=16,
        alignment=TA_RIGHT,
        textColor=COLOR_DARK_GREY,
        spaceBefore=2,
        spaceAfter=2,
        rightIndent=14,
    )

    styles["correction_section_title"] = ParagraphStyle(
        name="correction_section_title",
        fontName="Amiri-Bold",
        fontSize=12,
        leading=18,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#8B0000"),   # Deep red for correction heading
        spaceBefore=10,
        spaceAfter=4,
    )

    styles["footer_text"] = ParagraphStyle(
        name="footer_text",
        fontName="Amiri",
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=COLOR_MID_GREY,
    )

    styles["total_points"] = ParagraphStyle(
        name="total_points",
        fontName="Amiri-Bold",
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=COLOR_ACCENT_BLUE,
        spaceBefore=10,
        spaceAfter=6,
    )

    return styles


# =============================================================================
#  SECTION 4: MINISTRY HEADER BUILDER
#  Produces the official four-zone header that appears at the top of
#  every Algerian national exam document.
# =============================================================================

def _build_ministry_header(
    styles: Dict[str, ParagraphStyle],
    academic_year: str,
    specialty_stream: str,
    subject: str,
    trimester: str,
    duration: int,
    is_correction: bool = False,
) -> List[Any]:
    """
    Constructs the official Algerian Ministry exam header as a ReportLab
    Table with four quadrants:
      Top-Right : Republic + Ministry labels
      Top-Left  : School / Wilaya fields
      Center    : Exam title block
      Bottom    : Student info bar (Lastname / Firstname / Class)

    Args:
        styles:          Pre-built style dictionary.
        academic_year:   e.g. "2AS"
        specialty_stream: e.g. "علوم تجريبية"
        subject:         e.g. "الرياضيات"
        trimester:       e.g. "الفصل الأول"
        duration:        Exam duration in minutes.
        is_correction:   If True, adds a red "التصحيح النموذجي" stamp.

    Returns:
        List of ReportLab Flowable objects.
    """
    flowables: List[Any] = []

    # ---- TOP ROW: Right side (Republic) | Left side (School info) ----
    top_right_content = [
        Paragraph(
            _shape("الجمهورية الجزائرية الديمقراطية الشعبية"),
            styles["header_republic"],
        ),
        Paragraph(
            _shape("وزارة التربية الوطنية"),
            styles["header_ministry"],
        ),
    ]

    top_left_content = [
        Paragraph(
            _shape("مديرية التربية لولاية: ................................"),
            styles["header_left_label"],
        ),
        Paragraph(
            _shape("مؤسسة: ..............................................."),
            styles["header_left_label"],
        ),
    ]

    top_table = Table(
        data=[[top_left_content, top_right_content]],
        colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5],
        hAlign="CENTER",
    )
    top_table.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    flowables.append(top_table)
    flowables.append(Spacer(1, 3 * mm))

    # ---- HORIZONTAL RULE ----
    flowables.append(
        HRFlowable(
            width=CONTENT_WIDTH,
            thickness=1.5,
            color=COLOR_RULE,
            spaceAfter=3 * mm,
        )
    )

    # ---- CENTER TITLE BLOCK ----
    doc_type = "التصحيح النموذجي وسلّم التنقيط" if is_correction else "اختبار الثلاثي"
    title_text = f"{doc_type} ({_shape(trimester)}) — السنة الدراسية: 2025–2026م"

    flowables.append(
        Paragraph(_shape(title_text), styles["header_center_title"])
    )

    # ---- EXAM DETAILS ROW ----
    details_text = (
        f"المادة: {subject}    |    "
        f"الشعبة: {specialty_stream}    |    "
        f"المدة: {duration} دقيقة"
    )
    flowables.append(
        Paragraph(_shape(details_text), styles["header_meta"])
    )

    flowables.append(Spacer(1, 3 * mm))

    # ---- SECOND HORIZONTAL RULE ----
    flowables.append(
        HRFlowable(
            width=CONTENT_WIDTH,
            thickness=1.5,
            color=COLOR_RULE,
            spaceAfter=4 * mm,
        )
    )

    # ---- STUDENT INFO BAR (exam only) ----
    if not is_correction:
        student_bar_data = [[
            Paragraph(
                _shape("القسم: ......................"),
                styles["header_meta"],
            ),
            Paragraph(
                _shape("الاسم: ......................"),
                styles["header_meta"],
            ),
            Paragraph(
                _shape("اللقب: ......................"),
                styles["header_meta"],
            ),
        ]]

        student_table = Table(
            data=student_bar_data,
            colWidths=[CONTENT_WIDTH / 3] * 3,
            hAlign="CENTER",
        )
        student_table.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.5, COLOR_LIGHT_GREY),
        ]))

        flowables.append(student_table)
        flowables.append(Spacer(1, 5 * mm))

    return flowables


# =============================================================================
#  SECTION 5: EXAM BODY RENDERER
#  Converts the Gemini JSON 'exam' object into ReportLab flowables.
# =============================================================================

def _render_exam_body(
    exam_obj: Dict[str, Any],
    styles: Dict[str, ParagraphStyle],
) -> List[Any]:
    """
    Renders the full exam body from the Gemini 'exam' JSON object.
    Handles:
      - Optional text passage (literary subjects)
      - All sections with their titles and point totals
      - All questions and sub-questions with inline point labels

    Returns:
        List of ReportLab Flowable objects.
    """
    flowables: List[Any] = []

    # ---- TEXT PASSAGE (literary subjects only) ----
    text_passage = exam_obj.get("text_passage")
    if text_passage and isinstance(text_passage, str) and text_passage.strip():
        flowables.append(Spacer(1, 3 * mm))
        flowables.append(
            Paragraph(
                _shape("النص:"),
                styles["section_title"],
            )
        )
        # Preserve paragraph breaks in the passage
        for para_line in text_passage.strip().split("\n"):
            stripped = para_line.strip()
            if stripped:
                flowables.append(
                    Paragraph(_shape(stripped), styles["passage_text"])
                )
        flowables.append(Spacer(1, 4 * mm))

    # ---- SECTIONS ----
    sections: List[Dict] = exam_obj.get("sections", [])

    for section in sections:
        section_title  = section.get("section_title", "")
        points_total   = section.get("points_total", "")
        questions      = section.get("questions", [])

        # Section header row: title on right, points badge on left
        section_points_label = f"({points_total} نقاط)" if points_total else ""

        section_header_data = [[
            Paragraph(
                _shape(section_points_label),
                styles["section_points_badge"],
            ),
            Paragraph(
                _shape(section_title),
                styles["section_title"],
            ),
        ]]

        section_header_table = Table(
            data=section_header_data,
            colWidths=[CONTENT_WIDTH * 0.22, CONTENT_WIDTH * 0.78],
            hAlign="CENTER",
        )
        section_header_table.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("LINEBELOW",     (0, 0), (-1, -1), 0.8, COLOR_RULE),
        ]))

        flowables.append(section_header_table)
        flowables.append(Spacer(1, 3 * mm))

        # ---- QUESTIONS ----
        for question in questions:
            q_number      = question.get("number", "")
            q_text        = question.get("text", "")
            q_points      = question.get("points")
            sub_questions = question.get("sub_questions", [])

            # Build question label: "السؤال 1:" or "التمرين الأول:"
            q_label = f"{q_number}—  {q_text}" if q_number else q_text

            if q_points is not None and not sub_questions:
                # Question has a direct point value (no sub-questions)
                q_row_data = [[
                    Paragraph(
                        _shape(f"({q_points} ن)"),
                        styles["points_inline"],
                    ),
                    Paragraph(
                        _shape(q_label),
                        styles["question_text"],
                    ),
                ]]
            else:
                q_row_data = [[
                    Paragraph("", styles["points_inline"]),
                    Paragraph(
                        _shape(q_label),
                        styles["question_text"],
                    ),
                ]]

            q_table = Table(
                data=q_row_data,
                colWidths=[CONTENT_WIDTH * 0.15, CONTENT_WIDTH * 0.85],
                hAlign="CENTER",
            )
            q_table.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ]))

            flowables.append(q_table)

            # ---- SUB-QUESTIONS ----
            for sub in sub_questions:
                sub_number = sub.get("number", "")
                sub_text   = sub.get("text", "")
                sub_points = sub.get("points", "")

                sub_label = f"{sub_number})  {sub_text}" if sub_number else sub_text

                sub_row_data = [[
                    Paragraph(
                        _shape(f"({sub_points} ن)" if sub_points else ""),
                        styles["points_inline"],
                    ),
                    Paragraph(
                        _shape(sub_label),
                        styles["sub_question_text"],
                    ),
                ]]

                sub_table = Table(
                    data=sub_row_data,
                    colWidths=[CONTENT_WIDTH * 0.15, CONTENT_WIDTH * 0.85],
                    hAlign="CENTER",
                )
                sub_table.setStyle(TableStyle([
                    ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ]))

                flowables.append(sub_table)

        flowables.append(Spacer(1, 5 * mm))

    return flowables


# =============================================================================
#  SECTION 6: CORRECTION BODY RENDERER
# =============================================================================

def _render_correction_body(
    correction_obj: Dict[str, Any],
    styles: Dict[str, ParagraphStyle],
) -> List[Any]:
    """
    Renders the full correction body from the Gemini 'correction' JSON object.
    Produces a two-column answer + points layout for every answer entry.

    Returns:
        List of ReportLab Flowable objects.
    """
    flowables: List[Any] = []

    sections: List[Dict] = correction_obj.get("sections", [])

    for section in sections:
        section_title = section.get("section_title", "")
        answers       = section.get("answers", [])

        # Section title
        flowables.append(
            Paragraph(
                _shape(section_title),
                styles["correction_section_title"],
            )
        )
        flowables.append(
            HRFlowable(
                width=CONTENT_WIDTH,
                thickness=0.8,
                color=colors.HexColor("#8B0000"),
                spaceAfter=3 * mm,
            )
        )

        # Answers
        for answer in answers:
            q_num     = answer.get("question_number", "")
            sub_num   = answer.get("sub_question_number", "")
            ans_text  = answer.get("answer_text", "")
            points    = answer.get("points", "")

            # Build reference label
            if sub_num:
                ref_label = f"{q_num} — {sub_num}"
            else:
                ref_label = str(q_num)

            answer_row = [[
                Paragraph(
                    _shape(f"({points} ن)" if points else ""),
                    styles["points_inline"],
                ),
                Paragraph(
                    _shape(f"{ref_label}:  {ans_text}"),
                    styles["correction_answer"],
                ),
            ]]

            answer_table = Table(
                data=answer_row,
                colWidths=[CONTENT_WIDTH * 0.15, CONTENT_WIDTH * 0.85],
                hAlign="CENTER",
            )
            answer_table.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("LINEBELOW",     (0, 0), (-1, -1), 0.3, COLOR_LIGHT_GREY),
            ]))

            flowables.append(answer_table)

        flowables.append(Spacer(1, 5 * mm))

    # ---- GRAND TOTAL ROW ----
    total_points = correction_obj.get("total_points", 20)
    flowables.append(
        HRFlowable(
            width=CONTENT_WIDTH,
            thickness=1.5,
            color=COLOR_RULE,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        )
    )
    flowables.append(
        Paragraph(
            _shape(f"المجموع الكلي: {total_points} / 20 نقطة"),
            styles["total_points"],
        )
    )

    return flowables


# =============================================================================
#  SECTION 7: PAGE TEMPLATE BUILDER
# =============================================================================

def _build_page_template(doc: BaseDocTemplate) -> PageTemplate:
    """
    Constructs the single-frame page template used for all pages
    in both the exam and correction PDFs.
    """
    frame = Frame(
        x1=MARGIN_LEFT,
        y1=MARGIN_BOTTOM,
        width=CONTENT_WIDTH,
        height=PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )

    def on_page(canvas, doc):
        """
        Called by ReportLab on every page draw.
        Adds the page number at the bottom center.
        """
        canvas.saveState()
        canvas.setFont("Amiri", 8)
        page_num_text = _shape(f"صفحة {doc.page}")
        canvas.drawCentredString(
            PAGE_WIDTH / 2,
            MARGIN_BOTTOM / 2,
            page_num_text,
        )
        canvas.restoreState()

    template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=on_page,
    )

    return template


# =============================================================================
#  SECTION 8: PUBLIC API — EXAM PDF BUILDER
# =============================================================================

def build_exam_pdf(
    output_path: Path,
    payload: Dict[str, Any],
    academic_year: str,
    specialty_stream: str,
    subject: str,
    trimester: str,
    duration: int,
    fonts_dir: Path,
) -> None:
    """
    Compiles the official exam PDF from the Gemini payload.

    Args:
        output_path:      Absolute path where the PDF file will be written.
        payload:          The validated Gemini JSON payload dict.
        academic_year:    e.g. "2AS"
        specialty_stream: e.g. "علوم تجريبية"
        subject:          e.g. "الرياضيات"
        trimester:        e.g. "الفصل الأول"
        duration:         Exam duration in minutes.
        fonts_dir:        Path to backend/fonts/ directory.
    """
    _register_fonts(fonts_dir)
    styles = _build_styles()

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=MARGIN_RIGHT,
        leftMargin=MARGIN_LEFT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )
    doc.addPageTemplates([_build_page_template(doc)])

    story: List[Any] = []

    # Ministry header
    story.extend(
        _build_ministry_header(
            styles=styles,
            academic_year=academic_year,
            specialty_stream=specialty_stream,
            subject=subject,
            trimester=trimester,
            duration=duration,
            is_correction=False,
        )
    )

    # Exam body
    exam_obj = payload.get("exam", {})
    story.extend(_render_exam_body(exam_obj, styles))

    # Build PDF
    doc.build(story)
    log.info(f"Exam PDF written → {output_path.name} ({output_path.stat().st_size / 1024:.1f} KB)")


# =============================================================================
#  SECTION 9: PUBLIC API — CORRECTION PDF BUILDER
# =============================================================================

def build_correction_pdf(
    output_path: Path,
    payload: Dict[str, Any],
    academic_year: str,
    specialty_stream: str,
    subject: str,
    trimester: str,
    fonts_dir: Path,
) -> None:
    """
    Compiles the official correction + grading scale PDF from the Gemini payload.

    Args:
        output_path:      Absolute path where the PDF file will be written.
        payload:          The validated Gemini JSON payload dict.
        academic_year:    e.g. "2AS"
        specialty_stream: e.g. "علوم تجريبية"
        subject:          e.g. "الرياضيات"
        trimester:        e.g. "الفصل الأول"
        fonts_dir:        Path to backend/fonts/ directory.
    """
    _register_fonts(fonts_dir)
    styles = _build_styles()

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=MARGIN_RIGHT,
        leftMargin=MARGIN_LEFT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )
    doc.addPageTemplates([_build_page_template(doc)])

    story: List[Any] = []

    # Ministry header — correction variant
    story.extend(
        _build_ministry_header(
            styles=styles,
            academic_year=academic_year,
            specialty_stream=specialty_stream,
            subject=subject,
            trimester=trimester,
            duration=0,       # Duration not shown on correction sheet
            is_correction=True,
        )
    )

    # Correction body
    correction_obj = payload.get("correction", {})
    story.extend(_render_correction_body(correction_obj, styles))

    # Build PDF
    doc.build(story)
    log.info(
        f"Correction PDF written → {output_path.name} "
        f"({output_path.stat().st_size / 1024:.1f} KB)"
    )