# reports/base/TradeFriendPdfBase.py

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


class TradeFriendPdfBase:
    """
    Base PDF builder for all TradeFriend reports.
    """

    # -----------------------------
    # INIT
    # -----------------------------
    def __init__(self, output_path: str):
        self.output_path = self._resolve_path(output_path)
        self.story = []

        # ✅ Ensure directory exists BEFORE document creation
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # Printable A4 margins
        self.doc = SimpleDocTemplate(
            self.output_path,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=48,
            bottomMargin=36
        )

        self.styles = getSampleStyleSheet()

        self.title_style = ParagraphStyle(
            "TF_Title",
            parent=self.styles["Heading1"],
            alignment=TA_CENTER,
            fontSize=16,
            spaceAfter=14
        )

        self.meta_style = ParagraphStyle(
            "TF_Meta",
            parent=self.styles["Normal"],
            fontSize=9,
            textColor=colors.grey,
            spaceAfter=8
        )

        self.normal = ParagraphStyle(
            "TF_Normal",
            parent=self.styles["Normal"],
            fontSize=9,
            spaceAfter=6
        )

    # -----------------------------
    # PATH RESOLUTION (EXE SAFE)
    # -----------------------------
    def _resolve_path(self, relative_path: str) -> str:
        """
        Makes path safe for:
        - Normal python run
        - Scheduler
        - PyInstaller EXE
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # Go 2 levels up from reports/base/
        project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))

        return os.path.join(project_root, relative_path)

    # -----------------------------
    # HEADER / FOOTER
    # -----------------------------
    def _draw_header_footer(self, canvas, doc):
        canvas.saveState()

        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(
            36,
            A4[1] - 28,
            "TradeFriend — Intelligent Trading Assistant"
        )

        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            36,
            24,
            f"Generated: {datetime.now():%Y-%m-%d %H:%M}"
        )
        canvas.drawRightString(
            A4[0] - 36,
            24,
            f"Page {doc.page}"
        )

        canvas.restoreState()

    # -----------------------------
    # CONTENT HELPERS
    # -----------------------------
    def add_title(self, text: str):
        self.story.append(Paragraph(text, self.title_style))
        self.story.append(Spacer(1, 8))

    def add_meta(self, html_text: str):
        self.story.append(Paragraph(html_text, self.meta_style))
        self.story.append(Spacer(1, 6))

    def add_timestamp(self):
        self.add_meta(
            f"<b>Report Time:</b> {datetime.now():%Y-%m-%d %H:%M}"
        )

    def add_table(self, *, headers, rows, col_widths=None):
        data = [headers] + rows

        table = Table(
            data,
            colWidths=col_widths,
            repeatRows=1
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONT", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 10))

    # -----------------------------
    # BUILD
    # -----------------------------
    def build(self) -> str:
        self.doc.build(
            self.story,
            onFirstPage=self._draw_header_footer,
            onLaterPages=self._draw_header_footer
        )
        return self.output_path
