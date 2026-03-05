from pypdf import PdfReader
import docx


def extract_text(file_data: dict):
    """
    Extract text from different file types.
    """

    file_path = file_data["file_path"]
    file_extension = file_data["file_extension"]

    if file_extension == ".pdf":
        return extract_pdf_text(file_path)

    elif file_extension == ".txt":
        return extract_txt_text(file_path)

    elif file_extension == ".docx":
        return extract_docx_text(file_path)

    else:
        raise ValueError(f"Unsupported file type: {file_extension}")


def extract_pdf_text(file_path):
    text = ""

    reader = PdfReader(file_path)

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text


def extract_txt_text(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_docx_text(file_path):
    doc = docx.Document(file_path)

    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)

    return "\n".join(text)