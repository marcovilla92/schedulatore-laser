#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test Pattern 3 matching on N°217 text - FIXED"""

import re

text = '''Codice Articolo Cod.Interno Revisione Quantità Prezzo Totale
SR5-05530-004 Band. PR.600=300 PS5530 F 2  +25%02/04/2026
Bandelle - 7'''

print("Text:", repr(text[:200]))
print()

# The actual format is:
# SR5-05530-004 Band. PR.600=300 PS5530 F 2
# Codice Descrizione CodInterno Rev Quantità

# FIX: Description can have dots, digits, = etc. Just stop at the next WORD that's uppercase+digits (4+chars)
pattern = r'([A-Z0-9\-]{8,})\s+(.+?)\s+([A-Z0-9]{3,})\s+([A-Z])\s+(\d+)'
print("New Pattern:", pattern)
matches = list(re.finditer(pattern, text))
print(f"Matches: {len(matches)}")
for m in matches:
    code = m.group(1)
    desc = m.group(2).strip()
    code_interno = m.group(3)
    rev = m.group(4)
    qty = m.group(5)
    print(f"  - Code={code}, Desc={desc}, CodInterno={code_interno}, Rev={rev}, Qty={qty}")
