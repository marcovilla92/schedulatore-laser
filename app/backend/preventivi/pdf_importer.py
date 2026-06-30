"""PDF order importer — extracts article codes from PDF documents.

Extracted from preventivatore 2.0.py — pure function, no UI references.
"""

import logging
import re

import pdfplumber

logger = logging.getLogger(__name__)


def importa_codici_da_pdf(path: str) -> list[str]:
    """Carica un ordine PDF e estrae i codici articolo in sequenza.

    Pattern per codici articolo (es: 25NDSSA0053-00, 13SA0153-00, 13PA00434-00).
    Formato: 2 cifre + 2+ lettere maiuscole + 4+ cifre + opzionale(-2cifre).
    Il suffisso -00 è opzionale perché alcuni PDF lo omettono.

    Args:
        path: percorso al file PDF dell'ordine.

    Returns:
        Lista di codici articolo (stringhe) nell'ordine in cui compaiono nel PDF.

    Raises:
        ValueError: se nessun codice articolo trovato nel PDF.
    """
    codici_trovati = []

    # Pattern per codici articolo
    # Formato: 2 cifre + 2+ lettere maiuscole + 4+ cifre + opzionale(-2cifre)
    # Il suffisso -00 è opzionale perché alcuni PDF lo omettono
    pattern = r'\b\d{2}[A-Z]{2,}[0-9]{4,}(?:-\d{2})?'

    # Apri PDF e estrai testo
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # Estrai tutto il testo dalla pagina
            text = page.extract_text()

            if text:
                # Cerca codici nel testo:
                # 1. Prima cerca codici completi con -00 (più affidabili)
                # 2. Poi cerca codici senza -00
                # Pattern permette backslash opzionali tra caratteri per gestire path Windows

                # Pattern per codici con -00 (formato completo, più affidabile)
                pattern_complete = r'(\d{2})\\?([A-Z]{2,})\\?(\d{4,})-(\d{2})'
                complete_matches = re.finditer(pattern_complete, text)

                for match in complete_matches:
                    # Ricostruisci il codice senza backslash
                    codice = f"{match.group(1)}{match.group(2)}{match.group(3)}-{match.group(4)}"
                    if codice not in codici_trovati:
                        codici_trovati.append(codice)

                # Poi cerca anche codici senza -00 nel testo pulito
                text_clean = text.replace('\\', '')
                matches = re.finditer(pattern, text_clean)

                for match in matches:
                    codice = match.group(0)

                    # Normalizza: aggiungi -00 se mancante (per matching con articoli)
                    if not re.search(r'-\d{2}$', codice):
                        codice = codice + '-00'

                    # Evita duplicati mantenendo l'ordine
                    if codice not in codici_trovati:
                        codici_trovati.append(codice)

    if not codici_trovati:
        raise ValueError(
            "Nessun codice articolo trovato nel PDF.\n\n"
            "Assicurati che il PDF contenga codici nel formato:\n"
            "es: 25NDSSA0053-00, 25NDSPA0104-00, ecc."
        )

    return codici_trovati
