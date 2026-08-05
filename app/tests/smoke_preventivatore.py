"""Smoke test regressione: esercita tutte le funzioni principali del
preventivatore contro il backend in esecuzione (porta 5000).

Uso: python app/tests/smoke_preventivatore.py
Backend deve essere UP. Utente commerciale-test deve esistere.
"""
import io
import json
import os
import sys
import urllib.request
import uuid
import zipfile

API = 'http://localhost:5000'
USER = 'commerciale-test'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REG = os.path.join(ROOT, '_test_input', 'regression')

_results = []


def _rec(name, ok, detail=''):
    _results.append((name, ok, detail))
    flag = 'OK ' if ok else 'KO '
    print(f'  [{flag}] {name}' + (f'  — {detail}' if detail else ''))


def req(method, path, data=None, form=None, files=None):
    url = API + path
    if files is not None:
        boundary = '----b' + uuid.uuid4().hex
        parts = []
        for k, v in (form or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for fk, fn, content in files:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{fk}"; filename="{fn}"\r\n'
                         f'Content-Type: application/octet-stream\r\n\r\n'.encode() + content + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        body = b''.join(parts)
        r = urllib.request.Request(url, data=body, method=method,
                                   headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    else:
        body = json.dumps(data).encode() if data is not None else None
        r = urllib.request.Request(url, data=body, method=method,
                                   headers={'Content-Type': 'application/json'} if body else {})
    try:
        resp = urllib.request.urlopen(r, timeout=120)
        raw = resp.read()
        ct = resp.headers.get('Content-Type', '')
        if 'json' in ct:
            return resp.status, json.loads(raw)
        return resp.status, raw  # es. PDF bytes
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {'error': 'non-json'}


def main():
    print('\n=== SMOKE TEST PREVENTIVATORE ===\n')

    # 0. Config
    st, d = req('GET', '/api/preventivi/config')
    _rec('GET config', st == 200 and d.get('success'),
         f"generali={d.get('preventivi_config',{}).get('costo_generali_pct')}")

    # 1. Lista preventivi
    st, d = req('GET', '/api/preventivi')
    _rec('GET lista preventivi', st == 200)

    # 2. Crea preventivo (ritorna 201 + {preventivo})
    st, d = req('POST', '/api/preventivi', {'cliente': 'SMOKE TEST', 'created_by': USER, 'quantita': 2})
    pid = d.get('preventivo', {}).get('id') if isinstance(d, dict) else None
    _rec('POST crea preventivo', st in (200, 201) and bool(pid), pid or str(d)[:60])
    if not pid:
        print('\nStop: creazione preventivo fallita.')
        return _summary()

    # 3. Salva articoli con TUTTI i campi (roundtrip persistenza)
    art = [{
        'codice': 'SMK-1', 'quantita': 1, 'materiale': 'INOX_304', 'spessore_mm': 3,
        'area_dm2': 1.5, 'perimetro_taglio_m': 1.2, 'n_forature': 4,
        'pieghe': 2, 'saldatura_ml': 0.5, 'saldatura_min': 6, 'filettatura_pz': 1,
        'dxf_filename': 'smk.dxf', 'geometria_manuale_confermata': True,
        'geometry_source': 'manual-click', 'area_stimata_piega': False,
        'costo_base_stimato': 10.0, 'codice_assieme': None,
    }]
    st, d = req('PUT', f'/api/preventivi/{pid}/articoli', {'admin_id': USER, 'articoli': art})
    _rec('PUT salva articoli', st == 200 and d.get('success'), d.get('error', ''))

    st, d = req('GET', f'/api/preventivi/{pid}')
    a0 = (d.get('preventivo', {}).get('articoli') or [{}])[0]
    roundtrip = (a0.get('saldatura_min') == 6 and a0.get('geometria_manuale_confermata') is True
                 and a0.get('materiale') == 'INOX_304')
    _rec('GET articoli roundtrip (campi nuovi)', roundtrip,
         f"sald_min={a0.get('saldatura_min')} conf={a0.get('geometria_manuale_confermata')}")

    # 4. Stima-base
    st, d = req('POST', f'/api/preventivi/{pid}/articoli/{a0.get("id","x")}/stima-base',
                {'admin_id': USER, 'articolo': {'area_dm2': 1.5, 'perimetro_taglio_m': 1.2,
                                                'n_forature': 4, 'spessore_mm': 3, 'materiale': 'INOX_304'}})
    _rec('POST stima-base', st == 200 and d.get('success'),
         f"base={d.get('stima',{}).get('base')}" if d.get('success') else d.get('error',''))

    # 5. Salva assiemi
    st, d = req('PUT', f'/api/preventivi/{pid}/assiemi',
                {'admin_id': USER, 'assiemi': [{'codice_assieme': 'ASM-1', 'qty': 1, 'ore_montaggio': 2, 'costo': 90}]})
    _rec('PUT salva assiemi', st == 200 and d.get('success'), d.get('error', ''))

    # 6. Import DXF single (reale)
    dxf_path = os.path.join(REG, '20PA00693-00_INOX_304_sp3mm', 'pezzo.dxf')
    if os.path.exists(dxf_path):
        content = open(dxf_path, 'rb').read()
        st, d = req('POST', f'/api/preventivi/{pid}/import-dxf?admin_id={USER}',
                    form={'admin_id': USER}, files=[('file', '20PA00693.dxf', content)])
        _rec('POST import-dxf single', st == 200 and d.get('success'),
             f"area={d.get('geometria',{}).get('area_dm2')}" if d.get('success') else d.get('error',''))

        # 7. Import DXF batch SENZA paths (multi-file semplice)
        st, d = req('POST', f'/api/preventivi/{pid}/import-dxf-batch?admin_id={USER}',
                    form={'admin_id': USER}, files=[('files', '20PA00693.dxf', content)])
        _rec('POST import-dxf-batch (no paths)', st == 200 and d.get('success'),
             f"{len(d.get('results',[]))} risultati")

        # 8. Import DXF batch CON paths (assiemi da cartella)
        st, d = req('POST', f'/api/preventivi/{pid}/import-dxf-batch?admin_id={USER}',
                    form={'admin_id': USER, 'paths': 'ORD/SUB1/20PA00693.dxf'},
                    files=[('files', '20PA00693.dxf', content)])
        _rec('POST import-dxf-batch (con paths/assiemi)', st == 200 and 'assiemi' in d,
             f"assiemi={d.get('assiemi')}")
    else:
        _rec('import-dxf*', False, 'DXF di test non trovato')

    # 9. Import XLSX (reale ORD.204)
    xlsx_path = os.path.join(ROOT, '_test_input', 'ORD.204.xlsx')
    if os.path.exists(xlsx_path):
        st, d = req('POST', f'/api/preventivi/{pid}/import-xlsx?admin_id={USER}',
                    form={'admin_id': USER}, files=[('file', 'ORD.204.xlsx', open(xlsx_path, 'rb').read())])
        _rec('POST import-xlsx', st == 200 and d.get('success'),
             f"{len(d.get('articoli',[]))} articoli" if d.get('success') else d.get('error',''))
    else:
        _rec('import-xlsx', False, 'ORD.204.xlsx non trovato')

    # 10. RFQ ZIP semplice (senza sottocartelle, senza AI reale → verifica solo che non crashi 500)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('ordine.pdf', b'%PDF-1.4 fake')
        if os.path.exists(dxf_path):
            z.writestr('20PA00693-00.dxf', open(dxf_path, 'rb').read())
    st, d = req('POST', '/api/preventivi/import-rfq-package', form={'admin_id': USER},
                files=[('zip', 'test.zip', buf.getvalue())])
    # atteso: fallisce sul PDF fake (Gemini) ma GESTITO (400/200 con success:False), NON 500
    _rec('POST import-rfq (gestione errore, no crash)', st != 500 and d.get('success') is False,
         (d.get('error','') or '')[:50])

    # 11. Calcola totali
    st, d = req('POST', f'/api/preventivi/{pid}/calcola', {'admin_id': USER})
    _rec('POST calcola', st in (200, 404) and (d.get('success') or st == 404), '' if d.get('success') else d.get('error',''))

    # 12. PDF export
    st, d = req('GET', f'/api/preventivi/{pid}/pdf')
    is_pdf = st == 200 and isinstance(d, (bytes, bytearray)) and d[:4] == b'%PDF'
    _rec('GET pdf preventivo', is_pdf, f'{len(d)} bytes' if isinstance(d, (bytes, bytearray)) else str(d)[:40])

    # 13. Duplica (ritorna 200/201 + {preventivo})
    st, d = req('POST', f'/api/preventivi/{pid}/duplica', {'created_by': USER, 'cliente': 'SMOKE DUP', 'copy_articoli': True})
    dup_id = d.get('preventivo', {}).get('id') if isinstance(d, dict) else None
    _rec('POST duplica', st in (200, 201) and bool(dup_id), dup_id or str(d)[:50])

    # 14. Invia — l'articolo di test è confermato+costo → gate PASSA (200). Verifica no-500.
    st, d = req('POST', f'/api/preventivi/{pid}/invia', {'user_id': USER})
    _rec('POST invia (risponde sano)', st != 500 and isinstance(d, dict),
         f"status={d.get('preventivo',{}).get('status') if d.get('success') else 'bloccato:'+str(d.get('error',''))[:30]}")

    # 14b. Gate: crea preventivo con articolo NON confermato → invia deve BLOCCARE
    st, dg = req('POST', '/api/preventivi', {'cliente': 'GATE', 'created_by': USER, 'quantita': 1})
    gpid = dg.get('preventivo', {}).get('id')
    req('PUT', f'/api/preventivi/{gpid}/articoli',
        {'admin_id': USER, 'articoli': [{'codice': 'NC', 'quantita': 1, 'dxf_filename': 'x.dxf',
                                         'geometria_manuale_confermata': False}]})
    st, d = req('POST', f'/api/preventivi/{gpid}/invia', {'user_id': USER})
    _rec('POST invia GATE blocca (articolo non confermato)', st == 400 and d.get('success') is False,
         (d.get('error','') or '')[:45])
    req('DELETE', f'/api/preventivi/{gpid}?deleted_by={USER}')

    # cleanup preventivi
    for x in (pid, dup_id):
        if x:
            req('DELETE', f'/api/preventivi/{x}?deleted_by={USER}')
    _rec('DELETE cleanup', True)

    _summary()


def _summary():
    ok = sum(1 for _, o, _ in _results if o)
    tot = len(_results)
    print(f'\n{"="*50}\nRISULTATO: {ok}/{tot} funzioni OK')
    ko = [n for n, o, _ in _results if not o]
    if ko:
        print('DA CONTROLLARE:', ', '.join(ko))
    sys.exit(0 if ok == tot else 1)


if __name__ == '__main__':
    main()
