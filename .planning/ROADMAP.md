# Roadmap: Schedulatore Laser — v1.1 Fasi per Articolo

**Created:** 2026-02-19
**Milestone:** v1.1
**Total phases:** 3
**Total requirements:** 10

## Overview

Milestone v1.1 transforms the scheduling system from order-level phase tracking to per-article phase tracking. Each article gets its own set of assigned phases, independent status, and appears only in the department views where it belongs. The work clusters into three natural delivery boundaries: backend data model changes (foundation), phase assignment UI (office workflow), and department view updates (shop floor workflow).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Modello Dati per Articolo** - Backend model, API, and logic for per-article phase tracking
- [ ] **Phase 2: Assegnazione Fasi** - UI for office staff to assign/modify phases per article
- [ ] **Phase 3: Viste Reparto** - Department views show and operate on per-article phase data

## Phase Details

### Phase 1: Modello Dati per Articolo
**Goal**: Every article in an order carries its own assigned phases, tracks its own completion status, and the system correctly derives order-level status from article-level data
**Depends on**: Nothing (first phase)
**Requirements**: DATI-01, DATI-02, DATI-03, DATI-04
**Success Criteria** (what must be TRUE):
  1. When an order is created via API, each article stores a `required_phases` list specifying which phases (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) that article must go through
  2. When a phase is started/completed for an article, a per-article ProcessingStep is created and tracked independently from other articles in the same order
  3. Querying an article's status returns its next pending phase, list of completed phases, and list of remaining phases — derived from its assigned phases and completed steps
  4. An order's status changes to "completato" only when every article in that order has completed all of its individually assigned phases
  5. Existing orders without per-article phase data continue to work (backward compatibility with pre-v1.1 data)
**Plans**: TBD
**Estimated complexity:** High

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Assegnazione Fasi
**Goal**: Office staff can assign and modify the set of required phases for each article in an order before production begins
**Depends on**: Phase 1
**Requirements**: FASE-01, FASE-02, FASE-03
**Success Criteria** (what must be TRUE):
  1. On the ordini estratti page, each article displays a row of 5 checkboxes (LASER, PIEGA, SALDATURA, PULIZIA, SPEDIZIONE) and the user can check/uncheck any combination
  2. When a new order is created, all 5 phase checkboxes default to checked for every article — the user removes phases that do not apply
  3. The user can change an article's assigned phases at any time before that article has started processing in the phase being removed
  4. Saving phase assignments persists them to the backend and they survive page reload
**Plans**: TBD
**Estimated complexity:** Medium

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD

### Phase 3: Viste Reparto
**Goal**: Department operators see only the articles relevant to their phase, can batch-process them, and the dashboard reflects per-article progress
**Depends on**: Phase 1, Phase 2
**Requirements**: VISTA-01, VISTA-02, VISTA-03
**Success Criteria** (what must be TRUE):
  1. In laser.html, piega.html, and saldatura.html, each order card shows only the articles that have that specific phase in their `required_phases` — articles without the phase are not displayed
  2. The operator can start all displayed articles for an order in that phase with a single click, and complete all of them with a single click (batch operations)
  3. The dashboard shows per-article progress for each order: how many articles are in each phase, how many have completed all their assigned phases, displayed as a visual breakdown
  4. When an article completes its last assigned phase, it no longer appears in any department view — only fully-incomplete articles are shown
**Plans**: TBD
**Estimated complexity:** Medium

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Modello Dati per Articolo | 0/0 | Not started | - |
| 2. Assegnazione Fasi | 0/0 | Not started | - |
| 3. Viste Reparto | 0/0 | Not started | - |
