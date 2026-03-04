#!/usr/bin/env python3
"""Analizza contenuto FOR-ORDINE"""
import PyPDF2
from pathlib import Path

pdf_path = Path("C:/Users/39334/Downloads/FOR-ORDINE_0000205_00(50359).pdf")

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        print(f"\n{'='*80}")
        print(f"PAGINA {i+1}:")
        print(f"{'='*80}")
        print(text)
        print(f"{'='*80}")
