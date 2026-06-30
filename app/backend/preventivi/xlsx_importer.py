"""XLSX (Lantek) importer service.

Extracted from preventivatore 2.0.py — pure function, no UI references.
"""

import logging

import openpyxl

logger = logging.getLogger(__name__)


def importa_xlsx(path: str) -> list[dict]:
    """Importa dati da file XLSX Lantek.

    Gestisce sia il template "singolo" (un articolo per file) che il template
    "multi" (ordine di produzione con più articoli). Aggrega automaticamente
    gli articoli duplicati sommando i costi e contando le quantità.

    Args:
        path: percorso al file XLSX da importare.

    Returns:
        Lista di dizionari articolo con chiavi:
            codice (str), costo (float), area (float), quantita (int), row (int),
            costo_totale (float).

    Raises:
        ValueError: se nessun articolo trovato nel file.
        Exception: se il file non è leggibile.
    """
    wb = openpyxl.load_workbook(path, data_only=True)

    # Cerca foglio "Struttura" o usa il primo
    if "Struttura" in wb.sheetnames:
        ws = wb["Struttura"]
    else:
        ws = wb.active

    # Leggi intestazione per riconoscere template
    headers = [cell.value for cell in ws[1]]

    if headers[0] == "Codice":
        # Template singolo articolo
        idx_codice, idx_costo, idx_area, idx_quantita = 0, 12, 64, None
        template = "singolo"
    else:
        # Template multi articolo (Ordine di produzione)
        # Colonna 21 = Quantità prodotta, Colonna 22 = Costo totale
        idx_codice, idx_costo, idx_area, idx_quantita = 1, 22, None, 21
        template = "multi"

    # Leggi tutte le righe dati (dalla 2 in poi)
    articoli = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        codice = row[idx_codice] if len(row) > idx_codice and row[idx_codice] else None
        costo_totale = row[idx_costo] if len(row) > idx_costo and row[idx_costo] else 0

        # Leggi quantità se disponibile (template multi)
        if idx_quantita is not None and len(row) > idx_quantita:
            quantita = row[idx_quantita] if row[idx_quantita] else 1
        else:
            quantita = 1

        # Calcola costo unitario dividendo per quantità
        if quantita > 0:
            costo = float(costo_totale) / float(quantita)
        else:
            costo = float(costo_totale) if costo_totale else 0.0

        # Area solo per template singolo
        if idx_area is not None:
            area = row[idx_area] if len(row) > idx_area and row[idx_area] else 0
        else:
            area = 0

        # Salta righe vuote
        if codice and costo:
            articoli.append({
                "codice": str(codice),
                "costo": float(costo) if costo else 0.0,
                "area": float(area) if area else 0.0,
                "row": row_idx
            })

    wb.close()

    if not articoli:
        raise ValueError("Nessun articolo trovato nel file.")

    # Aggrega articoli con lo stesso codice (somma costi, conta quantità)
    aggregati = {}
    for art in articoli:
        codice = art['codice']
        if codice in aggregati:
            aggregati[codice]['quantita'] += 1
            aggregati[codice]['costo_totale'] += art['costo']
            aggregati[codice]['area'] += art['area']
        else:
            aggregati[codice] = {
                'codice': codice,
                'costo': art['costo'],          # costo unitario
                'costo_totale': art['costo'],   # costo totale (sommato)
                'area': art['area'],
                'quantita': 1,
                'row': art['row']
            }

    articoli = list(aggregati.values())

    return articoli
