#!/usr/bin/env python
"""Quick test of pattern matching without Docling"""

import PyPDF2
import re

filepath = 'C:/Users/39334/Documents/ORDINI/OF_260100-del-21-01-2026.pdf'

with open(filepath, 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    text = pdf.pages[0].extract_text()

# Test the pattern
pattern = r'^\s*\d+\s+([\w\s0-9\-]{3,20}?)\s*-'
matches = list(re.finditer(pattern, text, re.MULTILINE))

print(f"Pattern B matches: {len(matches)}")
for i, match in enumerate(matches[:10]):
    code = match.group(1).strip()
    print(f"  {i+1}. Code: '{code}'")

# Also show the actual lines that start with digit+space
print("\nLines starting with DIGIT+SPACE:")
for i, line in enumerate(text.split('\n')):
    if re.match(r'^\s*\d+\s+', line):
        print(f"  {i}: {line[:100]}")
