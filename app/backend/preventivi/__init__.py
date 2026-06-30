"""Modulo preventivi — porting dei servizi del Preventivatore desktop.

Contiene i servizi puri Python di calcolo riportati dal progetto Preventivatore
(Python/Tkinter desktop) come moduli backend Flask. Niente dipendenze da Tkinter.

Sottomoduli previsti (popolati in Fase 1 e 1b del piano merge):
- xlsx_importer       — parsing XLSX Lantek (formato singolo/multi)
- dxf_scanner         — analisi DXF: pieghe, saldature, filettature, svasature, area, perimetro_taglio
- step_parser         — analisi STEP per assiemi 3D
- step_features       — estrazione tubolari/piastre da STEP
- cost_calculator     — calcolo costi/totali con margine e sconto quantità
- laser_cost_estimator — stimatore costo taglio laser da area+spessore+materiale (NUOVO, non esiste nel desktop)
- pdf_exporter        — generazione PDF preventivo (ReportLab)

Vedi `contract.md` per il contratto JSON del modello preventivo.
"""
