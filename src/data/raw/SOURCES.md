# Raw data sources

The ONS datasets come from ONS open data (<https://dados.ons.org.br>). The files are hosted on the public S3 bucket `ons-aws-prod-opendata`. Every ONS dataset is downloaded as **Parquet**, together with its data dictionary PDF. Non-ONS sources are listed at the end. The files themselves are gitignored; only the folder layout is tracked.

- **Download date of the local copies:** 2026-11-20 (all folders). ONS revises published values, so record a new date whenever a folder is re-downloaded.
- **Base URL:** `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/<s3_prefix>/<file>`
- **Full file listing (CKAN API):** `https://dados.ons.org.br/api/3/action/package_show?id=<slug>` lists every resource with its URL, under `result.resources[].url`.

In the file patterns below, `YYYY` is the year, `MM` the month and `DD` the day.

## Core datasets

### `fator_capacidade_geracao_eolica_solar/`: Fator de Capacidade de Geração Eólica e Solar
- Dataset page: <https://dados.ons.org.br/dataset/fator-capacidade-2>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/fator_capacidade_2_di/`
- Files:
  - `FATOR_CAPACIDADE_YYYY.parquet`: yearly, 2009–2021
  - `FATOR_CAPACIDADE-2_YYYY_MM.parquet`: monthly, 2022-01 →
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/fator_capacidade_2_di/FATOR_CAPACIDADE-2_2024_01.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/fator_capacidade_2_di/DicionarioDados_FatorCapacidade.pdf>

### `constrained_off_eolica_detalhamento_usina/`: Restrição de Operação por Constrained-off de Usinas Eólicas, Detalhamento por Usina
- Dataset page: <https://dados.ons.org.br/dataset/restricao_coff_eolica_detail>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_detail_tm/`
- Files: `RESTRICAO_COFF_EOLICA_DETAIL_YYYY_MM.parquet`, monthly, 2021-10 →
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_detail_tm/RESTRICAO_COFF_EOLICA_DETAIL_2023_01.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_detail_tm/DicionarioDados_RestricaoContrainedoff_UsiEolicas_DetalhamentoPorUsina.pdf>
- Note: some of this dataset's CSV/XLSX resources are listed under the regional host `ons-aws-prod-opendata.s3.us-west-2.amazonaws.com`. All Parquet files use the standard host.

### `constrained_off_eolica_usina_conjunto/`: Restrição de Operação por Constrained-off de Usinas Eólicas
- Dataset page: <https://dados.ons.org.br/dataset/restricao_coff_eolica_usi>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_tm/`
- Files: `RESTRICAO_COFF_EOLICA_YYYY_MM.parquet`, monthly, 2021-10 →
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_2023_10.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_tm/DicionarioDados_RestricaoContrainedoff_UsiEolicas.pdf>

## Other datasets

### `constrained_off_eolica_intra_semihora/`: Restrição de Operação por Constrained-off de Usinas Eólicas Intra Semi-hora
- Dataset page: <https://dados.ons.org.br/dataset/coff_eolica_usi_intrasemihora>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_intrasemihora/`
- Files: `COFF_USI_EOLICAS_INTRASEMIHORA_YYYY_MM.parquet`, monthly, 2021-10 →
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_intrasemihora/COFF_USI_EOLICAS_INTRASEMIHORA_2026_09.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_intrasemihora/DicionarioDados_Contrainedoff_UsiEolica_IntraSemihora.pdf>

### `geracao_usina_horaria/`: Geração por Usina em Base Horária
- Dataset page: <https://dados.ons.org.br/dataset/geracao-usina-2>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/geracao_usina_2_ho/`
- Files:
  - `GERACAO_USINA-2_YYYY.parquet`: yearly, 2000–2021
  - `GERACAO_USINA-2_YYYY_MM.parquet`: monthly, 2022-01 →
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/geracao_usina_2_ho/GERACAO_USINA-2_2000.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/geracao_usina_2_ho/DicionarioDados_GeracaoPorUsina.pdf>

### `disponibilidade_usina/`: Disponibilidade de Usinas
- Dataset page: <https://dados.ons.org.br/dataset/disponibilidade_usina>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/disponibilidade_usina_ho/`
- Files: `DISPONIBILIDADE_USINA_YYYY_MM.parquet`, monthly. Parquet is published only for 2015-01, 2015-02 and 2023-01 →; the other months are CSV/XLSX only.
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/disponibilidade_usina_ho/DISPONIBILIDADE_USINA_2023_01.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/disponibilidade_usina_ho/DicionarioDados_Disponibilidade_Usinas.pdf>

### `previsao_vs_programado_eolica_solar/`: Previsão Versus Programado, Eólicas e Solares
- Dataset page: <https://dados.ons.org.br/dataset/programacao_x_previsao>
- S3 prefix: `https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/programacao_x_previsao/`
- Files: `PROGRAMACAO_X_PREVISAO_YYYY_MM_DD.parquet`, daily, 2024-10-01 →. ONS also publishes files for future days (schedules); the local copy ends at 2026-11-20.
- Example: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/programacao_x_previsao/PROGRAMACAO_X_PREVISAO_2024_10_01.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/programacao_x_previsao/DicionarioDados_Programado_x_Previsao_EolicaSolar.pdf>

### `cadastro_capacidade_instalada/`: Capacidade Instalada de Geração
- Dataset page: <https://dados.ons.org.br/dataset/capacidade-geracao>
- File: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/CAPACIDADE_GERACAO.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/capacidade-geracao/DicionarioDados_Capacidade_Instalada_Geracao.pdf>

### `cadastro_modalidade_usina/`: Modalidade de Operação de Usinas
- Dataset page: <https://dados.ons.org.br/dataset/modalidade-usina>
- File: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/modalidade_usina/MODALIDADE_USINA.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/modalidade_usina/DicionarioDados_Modalidade_Operacao_Usina.pdf>

### `cadastro_relacionamento_usina_conjunto/`: Relacionamento entre Conjuntos e Usinas
- Dataset page: <https://dados.ons.org.br/dataset/usina_conjunto>
- File: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/usina_conjunto/RELACIONAMENTO_USINA_CONJUNTO.parquet>
- Dictionary: <https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/usina_conjunto/DicionarioDados_Usina_Conjunto.pdf>

## Non-ONS sources

### `aneel_sigel_eolicas/`: ANEEL SIGEL, wind farms and turbines
- Origin: ANEEL SIGEL's public ArcGIS service, <https://sigel.aneel.gov.br/arcgis/rest/services/PORTAL/Parques_E%C3%B3licos/MapServer>, downloaded with `baixar_sigel_aneel.ps1` (outside this repo; its SHA-256 is in each snapshot's `execucao.json`).
- **Raw layer: `20261124T183056Z/`**, downloaded 2026-11-24 18:30:56–18:31:12 UTC. The files are the unmodified HTTP responses. Copied into `raw/` on 2026-11-24 after checking every file against `manifesto.csv` (SHA-256, size, HTTP 200, record count: all 50 match).
- Snapshot contents:
  - `servico_metadata.json` and `camada_<layer>_metadata.json`: the service and layer definitions (field names and ArcGIS types).
  - `camada_<layer>_pagina_<NNN>.json`: one query response per page, `…/MapServer/<layer>/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&orderByFields=OBJECTID&resultOffset=<n>&resultRecordCount=<page size>&f=json`. Pagination is complete: `exceededTransferLimit` is true on every page except each layer's last.
  - `manifesto.csv`: URL, UTC download time, HTTP status, bytes, SHA-256 and record count per file. `execucao.json`: layer mapping, script checksum, run window.
- Layers (a snapshot of the current state, not a time series):

| Layer | Table | Geometry | Page size | Pages | Records |
|---|---|---|---|---|---|
| 0 | Aerogeradores: one row per turbine. Rated power `POT_MW` (MW), hub height `ALT_TORRE` and total height `ALT_TOTAL` (m), rotor diameter `DIAM_ROTOR` (m), UTM `X`/`Y` with zone `FUSO_AG` and datum `DATUM_EMP`, plant `CEG` | point | 1000 | 18 | 17,012 |
| 1 | Região de Interferência: `DIRECAO_PREDO` (prevailing wind direction, degrees), `NUM_PETALAS` (wind-rose sectors) | polygon (1 feature has none) | 100 | 18 | 1,737 |
| 2 | Parque Eólico (Operação): one row per farm; `INICIO_OPER` (start of commercial operation), `QTD_AEG` (turbines), power in kW | point | 500 | 3 | 1,137 |
| 3 | Parque Eólico (Construção) | point | 500 | 1 | 62 |
| 4 | Parque Eólico (Construção não iniciada) | point | 500 | 1 | 390 |
| 5 | Parque Eólico (DRO) | point | 500 | 2 | 949 |

- Response format: `{"fields": [...], "spatialReference": {"wkid": 4326}, "features": [{"attributes": {...}, "geometry": {"x": lon, "y": lat}}], ...}`. Point geometry is in WGS84 longitude/latitude because the request asks the server to reproject (`outSR=4326`). Polygons are `{"rings": [...]}`.
- **Dates** (`esriFieldTypeDate`) are milliseconds since 1970-01-01 UTC and carry a time of day (e.g. `DATA_ATUALIZACAO` 1666625847000 = 2022-10-24T15:37:27Z).
- Plant codes: `CEG` is in ANEEL format (`EOLCVRN030702-5-01`); ONS uses `EOL.CV.RN.030702-5.01`. Some CEGs have no dash before the last two digits (`EOLCVBA055451-001`). The conversion belongs in silver.
- Link to ONS nodes: through the plant ↔ conjunto registry (`cadastro_relacionamento_usina_conjunto`). With the superseded CSVs, 198 of the 204 wind nodes in `fator_capacidade` since 2021-10 had at least one member plant with SIGEL turbines (membership validity dates ignored); recompute in silver once the code conversion handles every CEG format.
- **Superseded (deleted 2026-11-24):** CSVs from an earlier version of the script, downloaded 2026-11-24 16:16:44–16:17:13 UTC, which transformed the responses (dropped geometry, dates truncated to `YYYY-MM-DD`, added `ceg_formato_ons`/`lon_wgs84`/`lat_wgs84`, with a code-conversion bug affecting 119 turbines). Replaced by the snapshot above.

### `inmet/`: INMET automatic weather stations, hourly historical data
- Origin: INMET "Dados Históricos" yearly bundles (`<YYYY>.zip`, one per year, 2009–2026). *Inferred, not verified:* the portal is <https://portal.inmet.gov.br/dadoshistoricos> and the files are `https://portal.inmet.gov.br/uploads/dadoshistoricos/<YYYY>.zip`.
- **Download date:** 2026-11-24, taken from the files' modification times on the download machine (*inferred*: no download log exists). Copied into `raw/` on 2026-11-26 unchanged, with all 18 archives passing `unzip -t`. `SHA256SUMS` holds the checksum of each zip, and copy and original match.
- Kept zipped (as published). Bronze reads the CSVs straight from the archives.
- Contents: one CSV per station and year, `INMET_<REGIAO>_<UF>_<CODIGO>_<ESTACAO>_<dd-mm-yyyy>_A_<dd-mm-yyyy>.CSV`. 2026 is partial (the sampled station ends 2026-10-31).
- **Archive layout drift:** 2009–2019 and 2025 hold the CSVs inside a `<YYYY>/` folder. 2020–2024 and 2026 hold them at the archive root.
- **File format:** Latin-1, `;`-separated, decimal comma (values like `,8` have no leading zero), and a trailing `;` on every line. 8 header lines (region, UF, station name, WMO code, latitude, longitude, altitude, foundation date), then the column header and hourly rows.
- **Schema drift across years** (first seen in the 2009 and 2026 files; dated by the survey below): the column names `DATA (YYYY-MM-DD)` / `HORA (UTC)` become `Data` / `Hora UTC`. Values `2009-01-01` / `00:00` become `2026/01/01` / `0000 UTC`. Header keys lose their accents (`REGIÃO:` → `REGIAO:`) and the foundation date goes from `YYYY-MM-DD` to `dd/mm/yy`. Missing values are `-9999` in older files and empty in newer ones (`Null` also occurs according to INMET, but not in these files). Station altitude can differ between years for the same station.
- Timestamps are UTC (per column name). Wind direction is meteorological (direction the wind blows *from*, 0 = N). Wind speed is at roughly 10 m.
- **Survey of every archive (2026-11-26)**, which confirms the drift above and fixes its dates:
  - 9,617 CSVs, 705 stations, 82,187,136 hourly rows. Every file name follows the pattern, and its station code matches the header. No station appears twice in a year, no row repeats a (date, hour) within its file, and every row falls inside its archive's year, so the yearly archives never overlap in time.
  - Exactly three spellings each of the station keys and of the column header: 2009–2018; 2019 (accented letters are a literal `?`: `REGI?O:`); 2020 onwards (`REGIAO:`, and `RADIACAO GLOBAL (Kj/m²)` instead of `(KJ/m²)`). Same 19 columns in the same order in all three.
  - Date and hour spellings switch in 2019, not later: `2009-01-01` / `00:00` until 2018, `2019/01/01` / `0000 UTC` from 2019.
  - Missing measurements: only `-9999` until 2018 (9–14% of cells), only empty from 2019 (14–46%; 27–46% in 2020–2022, when every file has a full year of rows, inactive stations apparently included). No `Null` and no other non-numeric value occurs in the measurements.
  - Station lines: altitude is `F` for 17 `S1xx` stations in 2016–2018 and `NULL` for `A772` in 2026. Latitudes without a leading zero occur (`,59944444`, `-,41444444`). `A239` has latitude `-2` (integer). `C891` (2020) is at latitude −84, in Antarctica.
  - One file's name disagrees with its data: `INMET_S_RS_B827_BAGE - CENTRO_01-08-2025_A_20-10-2025.CSV` holds rows from 2025-08-01 to 2025-12-31.
- Not copied: an incomplete browser download (`Unconfirmed 178736.crdownload`, truncated zip) and three hand-made summaries in the source folder (`dicionario_inmet.csv`, `colunas_por_ano.csv`, `estacoes_inmet.csv`). The summaries are derived notes, not INMET files. Bronze should rebuild the station list from the CSV headers.
