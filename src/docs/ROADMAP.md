# Roadmap

Phases from data to paper. Each phase has a target window, a status and exit criteria: the phase is done when everything in its exit criteria exists. Design choices are in [DECISIONS.md](DECISIONS.md) (`D-NNN`), tools in [TECHSTACK.md](TECHSTACK.md).

- **Goal:** IJCNN 2027 submission, deadline at the end of January 2027 (exact date to be confirmed).
- **Dates are targets, not commitments.** Move them when needed and note why in the phase.
- **Phase status:** `Not started` · `In progress` · `Done`. Update it at the end of each session.
- **Weather and other features** are prepared in every data phase (1–5) alongside the ONS data. Node features are not all decided yet.

## Current position
*Updated at the end of the 2026-11-24 session.*

Phase 1 is in progress. Bronze is built for 15 sources: the 10 ONS datasets (downloaded 2026-11-20), 3 ANEEL SIGEL tables (turbines, farms, interference regions; snapshot of 2026-11-24) and 2 INMET tables (hourly observations and station lines, 2009–2026-10; downloaded 2026-11-24). Design: D-028. Raw provenance: [`src/data/raw/SOURCES.md`](../data/raw/SOURCES.md). The ONS + SIGEL code is merged into `main` (PR #1, 2026-11-26); INMET is on branch `bronze-inmet`.

Still missing for phase 1: ERA5 (download expected to finish between 2026-11-27 and 2026-11-29) and a download-date manifest for the ONS files (the SIGEL snapshot has its own `manifesto.csv`).

**Next session:** start phase 2 for the ONS + SIGEL stream, with the timezone convention of `din_instante` and the node definition first, since everything else depends on them. Open question for the user: how the EDA is delivered (notebooks in `src/notebooks/`, scripts with a written summary, or a report page per topic).

**Plan change (2026-11-24):** the weather data arrives later than phase 1 planned. Instead of waiting, the ONS + SIGEL stream (capacity factor, curtailment, registries, turbines) goes ahead through phases 2 and 3: bronze EDA, data decisions, silver. ERA5 and INMET join each phase when they arrive, so their work is the remaining half rather than the whole.

## Overview

| # | Phase | Target | Status |
|---|---|---|---|
| 1 | Bronze layer | Nov 23 – Nov 29 | `In progress` |
| 2 | Bronze EDA and data decisions | Nov 25 – Dec 3 (ONS + SIGEL first) | `Not started` |
| 3 | Silver layer | Nov 28 – Dec 6 (ONS + SIGEL first) | `Not started` |
| 4 | Silver EDA | Dec 7 – Dec 9 | `Not started` |
| 5 | Gold layer and infrastructure | Dec 7 – Dec 13 | `Not started` |
| 6 | Baselines | Dec 14 – Dec 20 | `Not started` |
| 7 | Proposed model (iterated on validation) | Dec 21 – Jan 10 | `Not started` |
| 8 | Edge-source comparison | Jan 11 – Jan 17 | `Not started` |
| 9 | Final evaluation on test | Jan 18 – Jan 24 | `Not started` |
| 10 | Writing and submission | Jan 25 – Jan 31 | `Not started` |

Start drafting the related-work, data and method sections in December, alongside phases 4–7.

## Phases

### 1. Bronze layer
- **Work:**
  - download the weather data into `raw/` (ERA5 per-node extracts per D-003, INMET), alongside the ONS data
  - a download-date manifest for every raw file
  - bronze per source: raw files concatenated with dtype/schema checks (D-001); outputs sorted (D-011)
- **Exit criteria:** bronze exists for every source, the manifest exists, and the bronze tests pass.
- **Progress (2026-11-24):** bronze pipeline built (D-028) with Parquet and ArcGIS readers; bronze exists for all ONS and SIGEL sources; 46 tests pass. Remaining: ERA5 and INMET readers and bronze, the ONS download-date manifest.
- **Progress (2026-11-26):** INMET readers and bronze built (D-028, 2026-11-26 entry): `inmet_horario` 82,187,136 rows, `inmet_estacoes` 9,617 rows, no duplicate keys. Readers now yield chunks, and specs declare a `TextEncoding`. 67 tests pass. Remaining: ERA5 reader and bronze, the ONS download-date manifest.

### 2. Bronze EDA and data decisions
- **Exit criteria:** each of these is recorded in DECISIONS.md:
  - node definition, plants or conjuntos, and therefore N (D-007); then the edge-builder format (D-006)
  - curtailment handling
  - the timezone convention of ONS `din_instante`
  - rules for invalid data (`flg_dadoventoinvalido`, INMET 9999/Null)
  - the number of INMET stations near the farms (feeds D-019)
  - the ERA5 leakage choice (D-023)
  - evaluation protocol confirmed: folds and seeds (D-021), horizon and metrics (D-022), compute budget (D-015)
- **Inputs found while building bronze (2026-11-24)**, all kept in bronze and counted in each source's `_bronze_meta.json`:
  - `fator_capacidade`: no duplicate `(id_ons, din_instante)`; empty strings read as null in `val_capacidadeinstalada` (66,118), `val_geracaoverificada` (1,656), `val_fatorcapacidade` (1,056) and `val_geracaoprogramada` (619,836). Since 2021-10 there are 204 wind nodes, most of them conjuntos with `ceg` = `"-"`.
  - repeated keys: `detalhamento_usina` 37,058 rows on `(id_ons, din_instante)`; `geracao_usina_horaria` 565,152 (the key may be wrong for old years); `intra_semihora` 50; `cadastro_modalidade_usina` 88 on `ceg`.
  - ONS timestamps are timezone-naive; monthly files run from 00:00 on the 1st to 23:00 (hourly) or 23:30 (semi-hourly) on the last day.
  - SIGEL: 525 turbines repeat `(CEG, DEN_AEG)`; 46 farm `CEG`s repeat across phases; 131 farms have several interference regions. Some farms' `LAT_DEC`/`LONG_DEC` are wildly out of range; the server's `geometry_x`/`geometry_y` look reliable. Turbine `OPERACAO` mixes vocabularies (`Sim`/`Não`, phase names, `1`).
  - Node → turbines: through `cadastro_relacionamento_usina_conjunto` (respecting its validity dates) and the ANEEL → ONS conversion of `CEG`, which must handle codes without a dash before the last two digits (e.g. `EOLCVBA055451-001`). A first check found 198 of 204 nodes with turbines.
  - Leakage: SIGEL is a current snapshot; time-varying use (turbine counts, capacity) must follow `INICIO_OPER` and membership dates.
- **Inputs found while building INMET bronze (2026-11-26)**, details in SOURCES.md:
  - 705 stations; missing measurements 9–14% of cells until 2018 and 14–46% after, highest in 2020–2022, when every file has a full year of rows (inactive stations apparently padded).
  - Whether `hora_utc` opens or closes the hour its values cover is unverified. It decides which observations are available at a forecast origin, so it is settled before silver uses INMET.
  - Station lines change between years (coordinates, altitude), so the station table has one row per station and year; silver picks positions per period. Foundation dates are text: `dd/mm/yy` from 2019, two-digit years to resolve against the 2009–2018 spelling.
  - Oddities: altitude `F`/`NULL` (read as null), `C891` in Antarctica, one file whose name's period disagrees with its rows (`B827`, 2025), an hourly mean wind speed of up to 43.4 m/s.
- **Ideas to evaluate:**
  - **Wake-interference edges from SIGEL layer 1** (`Região de Interferência`). Each polygon is an area of about 5 × 6 km drawn around one farm from a wind rose (`NUM_PETALAS` sectors of 12 or 16), reaching furthest on the side the prevailing wind comes from (`DIRECAO_PREDO`). It marks where another farm could put this one in its wake. "Farm j has turbines inside farm i's region" defines a directed, sparse edge j → i that the wind's direction sets: a static, physically grounded edge source to compare with ERA5-driven edges (D-004), alongside a simpler variant using only each farm's `DIRECAO_PREDO`. To check: how many node pairs it connects once farms are mapped to nodes, and whether it is too sparse at the conjunto level. Data quirks: 188 regions have no direction, one has an invalid value (30545), one has no polygon.

### 3. Silver layer
- **Work:** cleaned, validated, time-aligned data and features (D-001), following the phase-2 decisions.
- **Exit criteria:** silver exists; pandera checks pass at the bronze → silver boundary; the no-leakage and timezone tests pass.

### 4. Silver EDA
- **Exit criteria:** descriptive statistics and the paper's data figures: a map of the plants, capacity-factor distributions, wind roses, how often curtailment happens.

### 5. Gold layer and infrastructure
- **Exit criteria:**
  - one shared gold layer (D-002) with the splits of D-020
  - edge builders behind one interface (D-004, D-006), self-loops included (D-005)
  - a loader that slices windows by index (D-008)
  - the shared training loop (D-017) with precision picked from the GPU (D-009)
  - evaluation code with masked metrics (D-022)
  - dev mode (D-012)
  - run logging (D-011) and skippable runs (D-013)
  - a smoke test running end to end in dev mode

### 6. Baselines
- **Work:** the simple baselines first (D-024), then the further baselines (D-025). Decide which edges the GNN baselines get.
- **Exit criteria:** validation results for every baseline, logged in W&B.

### 7. Proposed model
- **Work:** build and iterate on validation only (D-027). Every variant tried is logged in W&B.
- **Dec 31: go/no-go for the heterogeneous farm + station variant (D-019).** It goes ahead only if the farms-only model works by then.
- **Jan 10: design freeze (D-027).**
- **Exit criteria:** the frozen model and its config.

### 8. Edge-source comparison
- **Work:**
  - the proposed model with each edge source (weather, distance-based, fully connected, …) × seeds (D-021)
  - the weather-as-features control (D-026), required
  - final runs of every baseline with all seeds
- **Exit criteria:** every run is complete on validation.

### 9. Final evaluation on test
- **Work:** the test set is evaluated once (D-027).
- **Exit criteria:** tables and figures of mean ± spread across seeds (D-011), per horizon, with skill against persistence (D-022).

### 10. Writing and submission
- **Exit criteria:** the paper is submitted.

## If time runs short
Cut in this order:
1. rolling-origin folds (D-021)
2. the number of GNN baselines, down to 2 (D-025)
3. extra node features
4. the heterogeneous graph (D-019)
