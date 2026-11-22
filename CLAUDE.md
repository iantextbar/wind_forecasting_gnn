# CLAUDE.md: GNN wind-power forecasting (IJCNN 2027 paper)

Research code for a paper. Results must be reproducible and defensible to reviewers. Correctness and no leakage come before speed of iteration.

## Problem
Forecast **hourly wind-power output per node** in the Brazilian grid with a spatio-temporal GNN whose **directed, sparse edges are driven by weather** (i → j when the flow at i points toward j).

- **Nodes:** wind plants or plant clusters ("conjuntos"), identified by ONS `id_ons`.
- **Target:** capacity factor = generation / installed capacity, using installed capacity at that time (it changes as turbines are added).
- **Output:** forecasts for t+1 … t+h for every node. The horizon h is undecided, so keep it configurable.
- **Edge construction must be swappable**: comparing edge sources is the paper's main experiment.
- **No leakage:** every input must be available at the forecast origin t. Observed weather after t is never an input.
- **Curtailment** (output limited by the grid operator) is not weather-driven and must be handled explicitly, never silently left in the target.

## Data
ONS open data: dados.ons.org.br, S3 bucket `ons-aws-prod-opendata` (use Parquet). ONS revises published values, so record the download date of every raw file. No download-date manifest exists yet.

All data lives under `data/` (gitignored). Raw files are in `data/raw/<folder>/`, one folder per dataset, each with the ONS data dictionary PDF (`DicionarioDados_*.pdf`).

### Core datasets
| Local folder (dataset slug) | Key fields | Resolution / period | Notes |
|---|---|---|---|
| `fator_capacidade_geracao_eolica_solar` (`fator-capacidade-2`) | `id_ons`, `nom_usina_conjunto`, `nom_tipousina` (filter to `"Eólica"`; also contains `"Solar"`), `din_instante`, `val_geracaoverificada` (MWmed), `val_capacidadeinstalada`, `val_latitudesecoletora` / `val_longitudesecoletora` | Hourly, 2009→ | Main target dataset. Only source of node coordinates; use collector, not connection-point, coordinates. Two file schemes: yearly `FATOR_CAPACIDADE_YYYY` (2009–2021) and monthly `FATOR_CAPACIDADE-2_YYYY_MM` (2022→). **Numeric `val_*` columns are decimal strings** (e.g. `"0E-8"`): cast explicitly in bronze. |
| `constrained_off_eolica_detalhamento_usina` (`restricao_coff_eolica_detail`) | `id_ons`, `id_ons_conjuntousina`, `din_instante`, `val_ventoverificado` (m/s), `flg_dadoventoinvalido`, `val_geracaoverificada`, `val_geracaoreferenciafinal`, `flg_geracaorestrita` | Semi-hourly, Oct 2021→ | Per-plant generation and measured wind **speed (no direction)**. JSON data dictionary is outdated; trust the file schema. |
| `constrained_off_eolica_usina_conjunto` (`restricao_coff_eolica_usi`) | `val_geracao`, `val_geracaoreferencia`, `val_disponibilidade`, `cod_razaorestricao` / `dsc_restricao` (curtailment reason) | Semi-hourly, Oct 2021→ | Curtailment information. |

### Other downloaded datasets (role not yet decided)
- `constrained_off_eolica_intra_semihora`: sub-semi-hourly curtailment events (`hor_inicial`, `hor_final`, `num_minutosrestricao`), Oct 2021→.
- `geracao_usina_horaria`: hourly generation for all plant types, 2000→. `val_geracao` is a string in old files and a double in new ones (schema drift).
- `disponibilidade_usina`: plant availability (`val_potenciainstalada`, `val_dispoperacional`). Has a gap: 2015_01–02, then 2023→.
- `previsao_vs_programado_eolica_solar`: ONS's own forecast vs. scheduled values, daily files from Oct 2024; a possible baseline. Keyed by `cod_usinapdp`, not `id_ons`.
- `cadastro_*`: static registries (installed capacity per generating unit, operating mode, plant ↔ conjunto membership with validity dates). Membership changes over time, so join on the validity interval.

### Weather
- **ERA5:** hourly, 0.25°, includes 100 m u/v wind.
- **INMET stations:** hourly, 10 m wind speed and direction. Missing values coded 9999/Null; timestamps in UTC. Interpolate **u/v components, never angles**.

Check every source's timezone convention before joining. ONS `din_instante` is stored as a timezone-naive timestamp; its convention is not yet verified.

## Code conventions
- **Modularity:** pipeline stages are separate modules with clear inputs and outputs. Parts that vary across experiments sit behind small interfaces (e.g. edge builders); add a variant as a new implementation, not as `if` branches. One responsibility per class or function; inject dependencies instead of constructing them deep inside. Add an abstraction only when a second implementation exists or is planned.
- **Data layers (Medallion):** `data/raw/` is immutable. `data/bronze/` = each source's raw files concatenated into a uniform typed format, with sanity checks (dtypes, schema) while concatenating, content unchanged; `data/silver/` = cleaned, validated, time-aligned, plus feature engineering; `data/gold/` = model-ready. Only code writes the layers below raw.
- **No boilerplate:** no copied scripts or duplicated helpers; experiments differ by configuration, not code. No magic numbers.
- **Comments:** explain *why* (physical reasoning, data quirks, leakage concerns), not *what*. Docstrings state **units** and **tensor shapes**. Use type hints.
- **Logging:** use a logger, never print. Log pipeline steps, dataset sizes, and how many rows each step drops and why. Each run records its config, git commit, seed, GPU model, torch/CUDA versions and data download dates.
- **Tests:** cover data transforms, always including a no-leakage test and timezone alignment. Validate data at layer boundaries (schema, ranges, no duplicate (node, time) pairs).

## Tooling
- Python 3.12, managed with `uv` (`uv add <pkg>`, `uv run <cmd>`). No dependencies are declared yet.

## Training runs on Colab
The data pipeline runs locally; model training runs in Colab, which cannot read local files.
- **Paths:** never hardcode paths. Resolve every data and output location from one configurable root, so the same code works locally and under `/content`.
- **Data in Colab:** download ONS and ERA5 directly into the runtime (both are on public cloud storage), or keep `data/gold/` on Drive and copy it to `/content` at the start of each session. Never train reading from Drive directly, because it is slow.
- **Ephemeral runtime:** write checkpoints and run records to Drive so they survive disconnects. Training must be able to resume from a checkpoint.
- **Hydra:** use the Compose API (`hydra.initialize` / `hydra.compose`), not `@hydra.main`. `@hydra.main` parses `sys.argv` and changes the working directory, which breaks in notebooks.
- **Install:** the package must install in Colab with plain `pip install` from the repo; keep anything that only works locally out of the core dependencies.
