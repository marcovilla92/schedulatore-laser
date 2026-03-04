#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rimuovi TUTTI gli emoji dai parser files"""
import os
import re

EMOJI_MAP = {
    '✅': '[OK]',
    '⚠️': '[WARNING]',
    '❌': '[ERROR]',
    '📄': '[PDF]',
    '📊': '[TABLE]',
    '🤖': '[PARSER]',
    '📋': '[DATA]',
    '1️⃣': '[1]',
    '2️⃣': '[2]',
    '3️⃣': '[3]',
    '4️⃣': '[4]',
}

PARSER_FILES = [
    'backend/parsers_generic.py',
    'backend/parsers_po_bebitalia.py',
    'backend/parsers_markdown_tables.py',
]

cwd = os.getcwd()

for file_rel in PARSER_FILES:
    filepath = os.path.join(cwd, file_rel)
    
    if not os.path.exists(filepath):
        print(f"File non trovato: {filepath}")
        continue
    
    print(f"\nProcessando: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Sostituisci ogni emoji
    for emoji, replacement in EMOJI_MAP.items():
        if emoji in content:
            count = content.count(emoji)
            content = content.replace(emoji, replacement)
            print(f"  {emoji} → {replacement}: {count} occorrenze")
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Salvato")
    else:
        print(f"  (nessun emoji trovato)")

print("\nDone!")
