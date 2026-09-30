"""Editable Word resume exports from saved data; no AI or browser required."""
from html.parser import HTMLParser
from io import BytesIO
import re

from docx import Document
from docx.shared import Inches, Mm, Pt, RGBColor

from app.schemas.models import ResumeData, SectionMeta

DEFAULT_SECTIONS = [
    ("personalInfo", "Personal Info", "personalInfo"),
    ("summary", "Summary", "text"),
    ("workExperience", "Experience", "itemList"),
    ("education", "Education", "itemList"),
    ("personalProjects", "Projects", "itemList"),
    ("additional", "Skills & Awards", "stringList"),
]


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.suppressed += 1
        elif not self.suppressed and tag in {"br", "p", "li", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif not self.suppressed and tag in {"p", "li", "div"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def plain_text(value: str | None) -> str:
    """Strip editor markup and XML-invalid controls without executing content."""
    value = value or ""
    if re.search(r"</?(?:p|div|br|strong|em|b|i|u|a|ul|ol|li|span|script|style)\b", value, re.I):
        parser = _Text()
        parser.feed(value)
        value = "".join(parser.parts)
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", value)
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def render_resume_docx(data: ResumeData, *, page_size: str = "LETTER", margins: tuple[int, int, int, int] = (20, 20, 20, 20)) -> bytes:
    """Use editable paragraphs in a single-column layout, preserving section order."""
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5) if page_size == "LETTER" else Mm(210)
    section.page_height = Inches(11) if page_size == "LETTER" else Mm(297)
    section.top_margin, section.bottom_margin, section.left_margin, section.right_margin = map(Mm, margins)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "List Bullet"):
        style = doc.styles[name]
        for border in style.element.xpath("./w:pPr/w:pBdr"):
            border.getparent().remove(border)
        style.font.name = "Calibri"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(10.5 if name in {"Normal", "List Bullet"} else 12)
        style.paragraph_format.space_after = Pt(4)
    doc.styles["Title"].font.size = Pt(22)
    doc.styles["Heading 1"].font.bold = True
    doc.styles["Heading 1"].paragraph_format.space_before = Pt(10)
    doc.styles["Heading 1"].paragraph_format.keep_with_next = True
    doc.styles["Normal"].paragraph_format.line_spacing = 1.05
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.title = ""

    def paragraph(text, *, bold=None, style=None):
        cleaned = plain_text(text)
        if not cleaned:
            return
        p = doc.add_paragraph(style=style)
        p.add_run(cleaned).bold = bold
        return p

    def items(entries):
        for item in entries:
            title = getattr(item, "title", None) or getattr(item, "degree", None) or getattr(item, "name", "")
            subtitle = getattr(item, "company", None) or getattr(item, "institution", None) or getattr(item, "role", None) or getattr(item, "subtitle", None)
            heading = paragraph(" — ".join(filter(None, [title, subtitle])), bold=True)
            if heading is not None:
                heading.paragraph_format.keep_with_next = True
            paragraph(" | ".join(filter(None, [item.years, getattr(item, "location", None)])))
            for key in ("github", "website"):
                paragraph(getattr(item, key, None))
            description = item.description
            if isinstance(description, str):
                paragraph(description)
            else:
                styles = getattr(item, "descriptionStyles", [])
                for index, text in enumerate(description or []):
                    plain = index < len(styles) and styles[index] == "plain"
                    paragraph(text, style=None if plain else "List Bullet")

    metadata = data.sectionMeta or [SectionMeta(id=key, key=key, displayName=label, sectionType=kind, order=index) for index, (key, label, kind) in enumerate(DEFAULT_SECTIONS)]
    visible = sorted((s for s in metadata if s.isVisible), key=lambda s: s.order)
    if any(s.key == "personalInfo" for s in visible):
        info = data.personalInfo
        paragraph(info.name, style="Title")
        paragraph(info.title)
        paragraph(" | ".join(filter(None, [info.email, info.phone, info.location])))
        paragraph(" | ".join(filter(None, [info.website, info.linkedin, info.github])))
    for meta in visible:
        if meta.key == "personalInfo":
            continue
        if meta.isDefault:
            value = getattr(data, meta.key, None)
            if meta.key == "additional":
                if not any(data.additional.model_dump().values()):
                    continue
                paragraph(meta.displayName, style="Heading 1")
                labels = {"technicalSkills": "Skills", "languages": "Languages", "certificationsTraining": "Certifications and Training", "awards": "Awards"}
                for key, label in labels.items():
                    values = getattr(data.additional, key)
                    if values:
                        paragraph(label + ": " + ", ".join(values))
            elif value:
                paragraph(meta.displayName, style="Heading 1")
                if isinstance(value, str):
                    paragraph(value)
                elif isinstance(value, list):
                    items(value)
        else:
            custom = data.customSections.get(meta.key)
            if custom is None or not (custom.text or custom.items or custom.strings):
                continue
            paragraph(meta.displayName, style="Heading 1")
            if custom.text:
                paragraph(custom.text)
            if custom.items:
                items(custom.items)
            for text in custom.strings or []:
                paragraph(text, style="List Bullet")
    output = BytesIO()
    doc.save(output)
    return output.getvalue()
