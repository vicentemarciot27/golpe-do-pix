# Source - https://stackoverflow.com/a/71207797
# Posted by gerda die gandalfziege
# Retrieved 2026-01-31, License - CC BY-SA 4.0

import os

from PyPDF2 import PdfReader, PdfWriter

for file in os.listdir("data/relacao_vencedores_leiloes"):
    if not file.lower().endswith(".pdf"):
        continue

    file_base_name = file

    pdf = PdfReader(f"data/relacao_vencedores_leiloes/{file}")

    pages = [0, 1, 2]  # page 1,2,3
    pdfWriter = PdfWriter()

    for page_num in pages:
        pdfWriter.add_page(pdf.pages[page_num])

    with open(f"{file_base_name}_subset.pdf", "wb") as f:
        pdfWriter.write(f)
