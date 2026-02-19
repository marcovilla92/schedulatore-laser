# Phase 3: Viste Reparto - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Le viste reparto (laser.html, piega.html, saldatura.html) mostrano solo gli articoli pertinenti alla fase specifica, permettono operazioni batch (avvia/completa), e la dashboard riflette il progresso per articolo. Non si aggiungono nuove fasi, nuove pagine, o nuove funzionalita — si aggiornano le viste esistenti per operare su dati per-articolo (v1.1).

</domain>

<decisions>
## Implementation Decisions

### Card articoli per ordine
- Ogni card ordine nelle viste reparto mostra solo gli articoli che hanno quella fase nelle `required_phases` — articoli senza la fase sono nascosti
- Nella card, ogni articolo mostra: nome, codice, quantita (pz), e stato nella fase corrente (in attesa / in lavorazione / completato)
- Articoli in lavorazione evidenziati con colore accent (cyan/pulse), completati con colore verde e testo barrato/sbiadito
- Card ordine non appare se tutti i suoi articoli hanno completato quella fase
- Ordinamento card: per data consegna (urgenti prima), poi per stato (in lavorazione prima di in attesa)

### Operazioni batch
- Pulsante "Avvia Tutti" avvia tutti gli articoli mostrati per quell'ordine in quella fase con un singolo click — nessuna conferma necessaria (azione reversibile)
- Pulsante "Completa" apre modale con checkbox per articoli (pattern gia esistente in laser.html) — seleziona quali articoli completare
- "Seleziona Tutti" nel modale per completamento rapido dell'intero lotto
- Feedback visivo: toast message dopo azione, card si aggiorna automaticamente con reload dati
- Se un articolo e gia in lavorazione, il pulsante "Avvia" per quell'ordine avvia solo quelli non ancora avviati

### Progresso dashboard
- Nella dashboard, ogni card ordine mostra un breakdown visivo per fase: barra segmentata orizzontale con un segmento per fase (LASER, PIEGA, SALDATURA, etc.)
- Ogni segmento colorato secondo stato: grigio (in attesa), accent (in lavorazione), verde (completato)
- Contatore testuale sotto la barra: "X/Y articoli completati" dove Y e il totale articoli dell'ordine
- Ordini con tutti gli articoli completati mostrano badge "COMPLETATO" e spostati in fondo o nascosti

### Stati e transizioni visive
- Tre stati per articolo nella vista reparto: "In attesa" (default, testo secondario), "In lavorazione" (accent cyan, dot pulsante), "Completato" (verde, opacita ridotta)
- Quando un articolo completa la fase, transizione smooth — l'articolo diventa visivamente "spento" ma resta visibile nella card fino al reload
- Quando tutti gli articoli di un ordine completano la fase, la card scompare al prossimo refresh (coerente con il pattern attuale di auto-refresh 30s)
- Empty state: "Nessun lavoro — Non ci sono articoli in attesa per questa fase" con icona check (pattern gia esistente)

### Claude's Discretion
- Esatta implementazione CSS delle transizioni e animazioni
- Struttura interna del rendering JavaScript (refactoring delle funzioni esistenti)
- Strategia di query backend per efficienza (JOIN vs query separate)
- Gestione errori di rete e retry logic
- Eventuali micro-ottimizzazioni di layout per schermi piccoli/tablet in officina

</decisions>

<specifics>
## Specific Ideas

- Le viste reparto gia esistono con il pattern card + modale completamento parziale (laser.html linee 858-1040) — estendere, non riscrivere
- Il dark glassmorphism theme e gia coerente tra tutte le pagine — mantenere lo stesso stile
- `get_orders_by_phase` gia filtra per `required_phases` e `next_phase` — la logica backend e in gran parte pronta, serve solo arricchire la risposta con stato per-articolo
- Dashboard gia ha auto-refresh 30s — il breakdown per articolo deve funzionare con questo ciclo

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-viste-reparto*
*Context gathered: 2026-02-19*
