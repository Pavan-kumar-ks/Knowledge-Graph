from PyPDF2 import PdfReader
import os

def load_pdf_text(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def load_all_pdfs(folder):
    docs = {}
    for file in os.listdir(folder):
        if file.endswith(".pdf"):
            docs[file] = load_pdf_text(os.path.join(folder, file))
    return docs

if __name__ == "__main__":
    docs = load_all_pdfs("C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph\\data\\pdfs")
    print(docs.keys())
