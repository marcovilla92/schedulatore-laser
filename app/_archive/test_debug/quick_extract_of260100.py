#!/usr/bin/env python
"""Quick check: Extract text from OF_260100 to see table structure"""

import PyPDF2

filepath = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'

with open(filepath, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    text = pdf.pages[0].extract_text()
    
# Print all lines with line numbers, showing exactly what's there
lines = text.split('\n')
print(f"Total lines: {len(lines)}\n")
print("=" * 100)

for i, line in enumerate(lines):
    # Show line info - length and content
    print(f"{i:3d} ({len(line):3d}): {line[:120]}")
