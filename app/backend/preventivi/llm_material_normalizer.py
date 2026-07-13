"""Normalizzazione materiale via LLM Gemini quando la tabella rule-based fallisce.

Approccio ibrido raccomandato dalla ricerca deep (report w13qt3qzy):
1. Prova prima `_normalize_materiale_cartiglio` (tabella regex esplicita)
2. Se fallisce E il valore raw non è vuoto → chiama LLM
3. LLM riceve prompt strutturato con JSON Schema forced (output validato)
4. Sanity check finale: output ∈ {S235, ZINCATO, INOX_304, ALU, OTTONE}

Costo Gemini flash: ~0.001 € per chiamata. Latenza: 500ms-2s.
Se GEMINI_API_KEY non configurata → funzione ritorna None (no-op).

Cache in-memory dei risultati LLM per stringa raw: se un cartiglio "C75 S"
viene visto 100 volte, chiamiamo Gemini 1 volta.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

VALID_MATERIALI = {'S235', 'ZINCATO', 'INOX_304', 'ALU', 'OTTONE'}


def _get_api_key() -> str | None:
    """Legge GEMINI_API_KEY dall'env, fallback su GOOGLE_API_KEY."""
    return os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY') or None


def is_available() -> bool:
    """True se LLM normalization è attivabile (API key configurata)."""
    return bool(_get_api_key())


@lru_cache(maxsize=512)
def normalize_via_llm(raw_material: str) -> str | None:
    """Chiama Gemini per classificare `raw_material` in uno dei 5 codici standard.

    Returns:
        Codice materiale ∈ {S235, ZINCATO, INOX_304, ALU, OTTONE} oppure None
        se: (a) API key non configurata, (b) chiamata fallisce, (c) LLM
        risponde con codice non-standard.

    Cached per stringa raw (fino a 512 diverse) — chiamate ripetute nella
    stessa sessione sono istantanee.
    """
    raw = (raw_material or '').strip()
    if not raw:
        return None
    api_key = _get_api_key()
    if not api_key:
        return None

    prompt = _build_prompt(raw)
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            'gemini-flash-latest',
            generation_config={
                'response_mime_type': 'application/json',
                'response_schema': {
                    'type': 'object',
                    'properties': {
                        'materiale': {
                            'type': 'string',
                            'enum': ['S235', 'ZINCATO', 'INOX_304', 'ALU', 'OTTONE', 'UNKNOWN'],
                        },
                        'confidence': {'type': 'number'},
                        'reasoning': {'type': 'string'},
                    },
                    'required': ['materiale', 'confidence'],
                },
                'temperature': 0.0,  # deterministico
                'max_output_tokens': 200,
            },
        )
        resp = model.generate_content(prompt)
        import json as _json
        result = _json.loads(resp.text)
    except ImportError:
        logger.warning('google-generativeai non installato — fallback no-op. '
                       'Installa: pip install google-generativeai')
        return None
    except Exception as e:
        logger.warning('LLM normalization fallita per %r: %s', raw, e)
        return None

    mat = str(result.get('materiale', '')).upper()
    confidence = float(result.get('confidence', 0))

    # Guardrail: accetta solo se materiale è nella whitelist E confidence ≥ 0.7
    if mat not in VALID_MATERIALI:
        return None
    if confidence < 0.7:
        logger.info('LLM basso confidence per %r: %s (%.2f) — scartato', raw, mat, confidence)
        return None

    logger.info('LLM normalizzato %r → %s (conf=%.2f)', raw, mat, confidence)
    return mat


def _build_prompt(raw: str) -> str:
    return f"""Sei un esperto di metallurgia italiana per lavorazione laser. Devi classificare
la seguente designazione di materiale letta da un cartiglio DXF in UNA delle 5
categorie standard usate dalla nostra tabella ricette Lantek:

Designazione da classificare: "{raw}"

Categorie ammesse:
- S235 → acciai al carbonio strutturali (S235, S275, S355, C-steels, Fe37, ST37, 1.0037, 1.0044, DC01-06)
- ZINCATO → lamiere/acciai galvanizzati (DX51D+Z, S250GD, S355 + zincatura, Sendzimir)
- INOX_304 → acciai inossidabili austenitici (AISI 304, 316, 1.4301, 1.4401, X5CrNi, X2CrNiMo)
- ALU → alluminio e leghe (5052, 5083, 5754, 6060, 6061, 6082, ENAW, tutti Al)
- OTTONE → leghe rame-zinco (Brass, CuZn, MS58, MS63, CW508L)
- UNKNOWN → se davvero non riesci a mappare (rame puro, titanio, plastica, ecc.)

Rispondi con JSON: {{
  "materiale": "<CATEGORIA>",
  "confidence": 0.0-1.0,
  "reasoning": "<breve motivo, max 20 parole>"
}}

Se non sei sicuro (confidence < 0.7), rispondi UNKNOWN. Non hallucinare."""
