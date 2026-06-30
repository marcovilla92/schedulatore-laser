"""DXF BOM (Bill of Materials) reader for SolidWorks assembly drawings.

Extracted from preventivatore 2.0.py — pure function, no UI references.
"""

import logging

import ezdxf

logger = logging.getLogger(__name__)


def leggi_bom_da_dxf(dxf_path: str) -> dict:
    """Legge la tabella BOM dal disegno assieme DXF (formato SolidWorks).

    Cerca il blocco SW_TABLEANNOTATION_0 che contiene la BOM come
    entità MTEXT posizionate in griglia. Estrae codice componente e quantità.

    Args:
        dxf_path: percorso al file DXF dell'assieme.

    Returns:
        dict {codice_componente: quantita} oppure {} se non trovato.
    """
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception:
        return {}

    # Cerca blocco BOM (SolidWorks usa SW_TABLEANNOTATION_0, _1, etc.)
    bom_block = None
    for block_name in doc.blocks:
        if hasattr(block_name, 'name'):
            name = block_name.name
        else:
            name = str(block_name)
        if name.upper().startswith('SW_TABLEANNOTATION'):
            bom_block = doc.blocks.get(name)
            break

    if bom_block is None:
        return {}

    # Raccogli tutte le MTEXT dal blocco
    testi = []
    for entity in bom_block:
        if entity.dxftype() == 'MTEXT':
            try:
                text = entity.text.strip() if hasattr(entity, 'text') else entity.dxf.text.strip()
                x = float(entity.dxf.insert.x)
                y = float(entity.dxf.insert.y)
                testi.append({'text': text, 'x': x, 'y': y})
            except Exception:
                continue

    if not testi:
        return {}

    # Raggruppa per Y (tolleranza 3mm) → righe
    testi.sort(key=lambda t: -t['y'])  # Y decrescente (dall'alto al basso)
    righe = []
    riga_corrente = [testi[0]]
    for t in testi[1:]:
        if abs(t['y'] - riga_corrente[0]['y']) < 3.0:
            riga_corrente.append(t)
        else:
            righe.append(sorted(riga_corrente, key=lambda t: t['x']))
            riga_corrente = [t]
    righe.append(sorted(riga_corrente, key=lambda t: t['x']))

    if len(righe) < 2:
        return {}

    # Trova header (prima riga) e identifica posizioni X delle colonne
    header = righe[0]
    x_codice = None
    x_qty = None
    for cell in header:
        txt = cell['text'].upper().strip()
        if 'CODICE' in txt:
            x_codice = cell['x']
        elif txt.startswith('QT'):
            x_qty = cell['x']

    if x_codice is None or x_qty is None:
        return {}

    def _trova_cella_per_x(riga, x_target, tolleranza=80.0):
        """Trova la cella nella riga la cui X è più vicina a x_target."""
        best = None
        best_dist = tolleranza
        for cell in riga:
            dist = abs(cell['x'] - x_target)
            if dist < best_dist:
                best_dist = dist
                best = cell
        return best

    # Estrai dati dalle righe successive
    bom = {}
    for riga in righe[1:]:
        cell_codice = _trova_cella_per_x(riga, x_codice)
        cell_qty = _trova_cella_per_x(riga, x_qty)

        if not cell_codice:
            continue

        codice = cell_codice['text'].strip()
        if not codice:
            continue

        qty = 1
        if cell_qty:
            try:
                qty = int(float(cell_qty['text'].strip()))
            except (ValueError, TypeError):
                qty = 1

        bom[codice] = qty

    return bom
