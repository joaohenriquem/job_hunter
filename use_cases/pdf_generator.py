from fpdf import FPDF
from core.entities.resume import Resume
import os


def _sanitize(text: str) -> str:
    """Substitui caracteres Unicode que a fonte Helvetica (Latin-1) nao suporta."""
    if not text:
        return ""
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2012": "-", "\u2010": "-",
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2026": "...", "\u00b7": "*", "\u2022": "-", "\u25cf": "-",
        "\u200b": "", "\ufeff": "",
    }
    for ch, repl in replacements.items():
        text = text.replace(ch, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ResumePDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def generate_resume_pdf(resume: Resume, primary_color: tuple = (41, 128, 185)) -> str:
    """Gera um PDF com margens corretas e quebra de texto adequada.
    primary_color: tupla RGB para a cor dos titulos das secoes.
    """
    pdf = ResumePDF()
    # Margem de 15mm em todos os lados
    pdf.set_margins(left=15, top=15, right=15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    text_color = (50, 50, 50)
    page_width = pdf.w - 30  # largura util descontando margens

    # ----- HEADER: NOME -----
    pdf.set_font("helvetica", "B", 22)
    pdf.set_text_color(*primary_color)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(page_width, 12, _sanitize(resume.full_name).upper(), align="C")

    # ----- HEADER: CONTATOS -----
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*text_color)

    contacts = []
    if resume.email:     contacts.append(_sanitize(resume.email))
    if resume.phone:     contacts.append(_sanitize(resume.phone))
    if resume.linkedin:  contacts.append(_sanitize(resume.linkedin))
    if resume.portfolio: contacts.append(_sanitize(resume.portfolio))

    if contacts:
        # Linha 1: email + telefone | Linha 2: linkedin + portfolio
        line1 = "  |  ".join(contacts[:2])
        line2 = "  |  ".join(contacts[2:]) if len(contacts) > 2 else ""
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 6, line1, align="C")
        if line2:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(page_width, 6, line2, align="C")

    pdf.ln(4)

    # ----- DIVISOR -----
    pdf.set_draw_color(*primary_color)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    def add_section(title, content):
        if not content or not str(content).strip():
            return

        pdf.set_font("helvetica", "B", 12)
        pdf.set_text_color(*primary_color)
        pdf.set_x(pdf.l_margin)
        pdf.cell(page_width, 8, _sanitize(title).upper(), ln=True, align="L")

        pdf.set_draw_color(*primary_color)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(2)

        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(*text_color)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(page_width, 5.5, _sanitize(str(content)), align="L")
        pdf.ln(5)

    # ----- CORPO -----
    add_section("Resumo Profissional", resume.professional_summary)
    add_section("Experiencia Profissional", resume.experience)
    add_section("Formacao Academica", resume.education)
    add_section("Conhecimentos e Competencias", resume.skills)
    add_section("Idiomas", resume.languages)

    # ----- GRAVACAO -----
    filename = f"curriculo_{resume.user_id}.pdf"
    export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "exports")
    os.makedirs(export_dir, exist_ok=True)

    filepath = os.path.join(export_dir, filename)
    pdf.output(filepath)
    return filepath
