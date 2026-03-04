#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test Pattern 3 matching on N°217 text"""

import re

text = '''Codice Articolo Cod.Interno Revisione Quantità Prezzo Totale
SR5-05530-004 Band. PR.600=300 PS5530 F 2  +25%02/04/2026
Bandelle - 7'''

print("Text:", repr(text[:200]))
print()

# Current Pattern 3
pattern3 = r'(SR[A-Z0-9\-]+)\s+([^\d]+?)\s+[A-Z0-9]{4,}\s+[A-Z0-9]\s+(\d+)'
print("Pattern 3 (current):", pattern3)
matches = list(re.finditer(pattern3, text))
print(f"Matches: {len(matches)}")
for m in matches:
    print(f"  - Code={m.group(1)}, Desc={m.group(2)}, Qty={m.group(3)}")
print()

# Better Pattern 3 - allow digits after SR
pattern3_new = r'(SR5[A-Z0-9\-]+|SR[A-Z0-9\-]+)\s+([^\d]+?)\s+[A-Z0-9]{4,}\s+[A-Z]\s+(\d+)'
print("Pattern 3 (new):", pattern3_new)
matches = list(re.finditer(pattern3_new, text))
print(f"Matches: {len(matches)}")
for m in matches:
    print(f"  - Code={m.group(1)}, Desc={m.group(2)}, Qty={m.group(3)}")
print()

# Even simpler - just look for CODES that are word-dash pattern followed by description and qty
pattern_simple = r'([A-Z0-9]{2,}(?:\-[A-Z0-9]+)+)\s+([^0-9\n]+?)(?:\s+[A-Z0-9]{3,})+\s+([A-Z])\s+(\d+)'
print("Pattern simple:", pattern_simple)
matches = list(re.finditer(pattern_simple, text))
print(f"Matches: {len(matches)}")
for m in matches:
    print(f"  - Code={m.group(1)}, Desc={m.group(2)}, Rev={m.group(3)}, Qty={m.group(4)}")
