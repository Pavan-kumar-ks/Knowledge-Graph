# import json

# def chunk_text(text, chunk_size=1024):
#     words = text.split()
#     chunks = []

#     for i in range(0, len(words), chunk_size):
#         chunk = " ".join(words[i:i+chunk_size])
#         chunks.append(chunk)

#     return chunks

# def create_chunks(docs):
#     all_chunks = []
#     for doc_name, text in docs.items():
#         chunks = chunk_text(text)
#         for c in chunks:
#             all_chunks.append({
#                 "document": doc_name,
#                 "text": c
#             })
#     return all_chunks

# if __name__ == "__main__":
#     from pdf_loader import load_all_pdfs

#     docs = load_all_pdfs("C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph\\data\\pdfs")
#     chunks = create_chunks(docs)

#     with open("C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph\\chunks.json", "w", encoding="utf-8") as f:
#         json.dump(chunks, f, indent=2)

#     print(f"Saved {len(chunks)} chunks")
import json
import re

def is_header(line):
    line = line.strip()

    if len(line) < 3:
        return False

    # Matches: "1.", "1.1", "2.0", etc.
    if re.match(r"^\d+(\.\d+)*", line):
        return True

    # ALL CAPS headings
    if line.isupper() and len(line) < 80:
        return True

    return False


def split_into_sections(text):
    sections = []
    current_header = "Introduction"
    current_text = []

    for line in text.split("\n"):
        line = line.strip()

        if is_header(line):
            # save previous section
            if current_text:
                sections.append({
                    "header": current_header,
                    "content": " ".join(current_text)
                })
                current_text = []

            current_header = line
        else:
            if line:
                current_text.append(line)

    # last section
    if current_text:
        sections.append({
            "header": current_header,
            "content": " ".join(current_text)
        })

    return sections


def chunk_text(text, chunk_size=1024):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def create_chunks(docs):
    all_chunks = []

    for doc_name, text in docs.items():
        sections = split_into_sections(text)

        for section in sections:
            section_chunks = chunk_text(section["content"])

            for idx, chunk in enumerate(section_chunks):
                all_chunks.append({
                    "document": doc_name,
                    "section": section["header"],
                    "chunk_id": idx,
                    "text": chunk
                })

    return all_chunks


if __name__ == "__main__":
    from pdf_loader import load_all_pdfs

    docs = load_all_pdfs("C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph\\data\\pdfs")

    chunks = create_chunks(docs)

    output_path = "C:\\Users\\91779\\Desktop\\InternShip_Rooman\\policy-knowledge-graph\\chunks.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(chunks)} structured chunks to {output_path}")
