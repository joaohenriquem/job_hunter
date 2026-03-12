import pdfplumber
import io

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrai texto bruto de um PDF (funciona para PDFs do LinkedIn que tem texto embutido)."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)
