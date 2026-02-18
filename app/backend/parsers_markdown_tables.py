"""
Universal Markdown Table Parser
Extracts articles from Markdown tables (Docling output format)
Works for any PDF format: OAFA, FOR_ORDINE, DIVISIONE, etc.
"""

import re
from typing import List, Dict, Optional


def extract_articles_from_markdown_table(markdown_text: str) -> List[Dict[str, str]]:
    """
    Extract articles from Markdown table format produced by Docling.
    
    Handles tables in format:
    | CODICE | DESCRIZIONE | QUANTITA | etc |
    |--------|-------------|----------|-----|
    | code1  | desc1       | qty1     | ... |
    
    Args:
        markdown_text: Full text output from Docling (contains markdown table)
    
    Returns:
        List of dicts with keys: code, name, qty
    """
    articles = []
    
    # Find all markdown tables in text
    tables = _extract_tables(markdown_text)
    
    if not tables:
        return articles
    
    # Process each table found
    for table_markdown in tables:
        rows = _parse_markdown_table(table_markdown)
        
        if not rows:
            continue
            
        # Find headers and column indices
        headers = rows[0]
        col_indices = _find_column_indices(headers)
        
        if not col_indices:
            continue
        
        # Extract articles from data rows (skip header and separator)
        for row in rows[2:]:  # Skip header row (0) and separator (1)
            article = _parse_article_row(row, col_indices)
            
            if article:
                articles.append(article)
    
    return articles


def _extract_tables(text: str) -> List[str]:
    """Extract markdown table blocks from text."""
    tables = []
    
    # Split by lines
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if line starts a table (contains | pipes)
        if line.startswith('|') and '|' in line:
            table_lines = [line]
            i += 1
            
            # Collect separator and data rows
            while i < len(lines):
                next_line = lines[i].strip()
                
                # Stop if we hit non-table content
                if not next_line.startswith('|'):
                    break
                
                table_lines.append(next_line)
                i += 1
            
            if len(table_lines) >= 3:  # Need header, separator, at least 1 data row
                tables.append('\n'.join(table_lines))
            
            continue
        
        i += 1
    
    return tables


def _parse_markdown_table(table_text: str) -> Optional[List[List[str]]]:
    """Parse markdown table into rows of cells."""
    lines = table_text.split('\n')
    
    if len(lines) < 3:
        return None
    
    rows = []
    
    for line in lines:
        # Remove leading/trailing pipes and split
        line = line.strip()
        
        if not line.startswith('|') or not line.endswith('|'):
            continue
        
        # Remove outer pipes and split by pipe
        cells = line[1:-1].split('|')
        
        # Clean cells: strip whitespace
        cells = [cell.strip() for cell in cells]
        
        rows.append(cells)
    
    return rows if rows else None


def _find_column_indices(headers: List[str]) -> Dict[str, int]:
    """
    Find column indices for common article fields.
    
    Looks for variations of:
    - Code: CODICE, CODE, ARTICOLO, PRODUCT CODE, etc.
    - Description: DESCRIZIONE, DESC, DESCRIPTION, ARTICOLO, etc.
    - Quantity: QUANTITA, QTY, QTA, CANTIDAD, MENGE, QUANTITÉ, etc.
    
    Returns:
        Dict with keys 'code', 'name', 'qty' mapping to column indices
    """
    indices = {}
    
    # Define patterns for each column type
    code_patterns = [
        r'^(?:CODICE|CODE|ARTICOLO|PRODUCT\s*CODE|ART\.?)$',
        r'^(?:REF|REFERENCE|SKU|PART\s*NUMBER)$'
    ]
    
    desc_patterns = [
        r'^(?:DESCRIZIONE|DESCRIPTION|DESC|DESCRIPTION)$',
        r'^(?:ARTICOLO|ARTICLE|PRODUCT|DENOMINAZIONE)$'
    ]
    
    qty_patterns = [
        r'^(?:QUANTITA|QTY|QTA|CANTIDAD|QUANTITY|MENGE|QUANTITÉ|QTESS?)$',
        r'^(?:AMOUNT|NUMERO|NR|NUM)$'
    ]
    
    # Search through headers
    for idx, header in enumerate(headers):
        header_upper = header.upper().strip()
        
        # Skip empty headers
        if not header_upper:
            continue
        
        # Check code column
        if 'code' not in indices:
            for pattern in code_patterns:
                if re.match(pattern, header_upper):
                    indices['code'] = idx
                    break
        
        # Check description column
        if 'name' not in indices:
            for pattern in desc_patterns:
                if re.match(pattern, header_upper):
                    indices['name'] = idx
                    break
        
        # Check quantity column
        if 'qty' not in indices:
            for pattern in qty_patterns:
                if re.match(pattern, header_upper):
                    indices['qty'] = idx
                    break
    
    # Validate we found at least code + qty (description is optional)
    if 'code' not in indices or 'qty' not in indices:
        return {}
    
    return indices


def _parse_article_row(cells: List[str], col_indices: Dict[str, int]) -> Optional[Dict[str, str]]:
    """
    Parse a single data row into article dict.
    
    Returns None if row is invalid (e.g., header row, empty row, non-data).
    """
    # Check bounds
    max_idx = max(col_indices.values())
    if max_idx >= len(cells):
        return None
    
    # Extract fields
    code = cells[col_indices['code']].strip()
    qty = cells[col_indices['qty']].strip()
    name = cells[col_indices['name']].strip() if 'name' in col_indices else ''
    
    # Validate: code should have content, qty should be numeric-like
    if not code or not qty:
        return None
    
    # Skip separator rows (contain only dashes)
    if re.match(r'^[\s\-|]+$', code):
        return None
    
    # Skip header rows (lines that contain header keywords)
    header_keywords = ['CODICE', 'CODE', 'DESCRIZIONE', 'QUANTITA', 'QTY', 'ARTICOLO']
    if any(kw.lower() in code.lower() for kw in header_keywords):
        return None
    
    # Skip footer/nota rows (contain keywords like "Note", "Trasporto", "Spese", "Totale", "Sconto")
    footer_keywords = ['NOTE', 'TRASPORTO', 'SPESE', 'TOTALE', 'SCONTO', 'ASSICUR', 'BANCARIE', 'EVENTUALI']
    if any(kw.lower() in name.lower() for kw in footer_keywords):
        return None
    
    # Validate quantity is numeric (may contain . or , as decimal)
    qty_str = qty.replace(',', '.').replace(' ', '')
    if not re.match(r'^\d+(\.\d+)?$', qty_str):
        return None

    qty_num = float(qty_str)
    if qty_num == int(qty_num):
        qty_num = int(qty_num)

    # Validate code format (alphanumeric, hyphens, special chars allowed)
    # Must have at least some content that looks like a code
    if not re.search(r'[A-Z0-9]', code):
        return None

    return {
        'code': code,
        'name': name,
        'qty': qty_num
    }


if __name__ == '__main__':
    # Test example
    test_markdown = """
| CODICE | DESCRIZIONE | QUANTITA |
|--------|-------------|----------|
| 25AA01 | Test Part 1 | 2,50 |
| 25BB02 | Test Part 2 | 1,00 |
"""
    
    articles = extract_articles_from_markdown_table(test_markdown)
    for art in articles:
        print(f"Code: {art['code']}, Name: {art['name']}, Qty: {art['qty']}")
