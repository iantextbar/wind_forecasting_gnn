# Decisions

Design decisions about data layers, models, efficiency and experiments. Tool and library choices are in [TECHSTACK.md](TECHSTACK.md).

**Status:** `Decided` · `Proposed` (recommended, waiting for the user's confirmation) · `Open` (not decided yet).

**How to edit:**
- Add new entries at the end of their section, with the next free ID. Never renumber.
- When a status changes, edit it in place and add a dated line, e.g. `- 2026-12-01: Proposed → Decided (reason)`.

## Data layers

### D-001 Medallion layer definitions
`Decided` · 2026-11-21
- **raw:** files exactly as downloaded, possibly many files per source. Immutable. Every source, weather included (ERA5 per-node extracts, INMET, any future one), lands in `raw/<source>/` with its download date recorded.
- **bronze:** the raw files of a source concatenated, with sanity checks while concatenating (dtypes, schema, schema drift between files).
- **silver:** preprocessed data and feature engineering.
- **gold:** aggregations of silver, ready for the model. Storage format: D-002.
- **Note:** silver features may only use data available at each row's own timestamp (CLAUDE.md no-leakage rule). Anything fitted on data (scalers, fitted graphs) is fitted per training fold, not in silver.

### D-002 Gold layer as dense arrays
`Proposed` · 2026-11-21
- **Decision:** gold = arrays on a regular time grid, `[T, N, F]` (`.npy`/memmap or Zarr), plus a missing-data mask. Parquet is used up to silver only.
- **Why:** windows are contiguous zero-copy slices (`torch.from_numpy`, memmap); the CPU does no per-sample pivoting or filtering (Colab has few cores); missing values are explicit, so loss and metrics are masked consistently.
- **Trade-off:** larger on disk than Parquet. Nodes commissioned after the start date add padding, which the mask covers.
- **Revisit if:** disk or Drive space binds → Zarr with compression.

### D-003 ERA5 point extraction
`Proposed` · 2026-11-21
- **Decision:** extract the 4 grid cells around each node (the ones bilinear interpolation needs) once, store them in `raw/` (D-001) and cache them on Drive.
- **Why:** the full grid is far larger than what the nodes need.
- **Trade-off:** the CDS API queue is slow, and a Zarr store chunked by time is slow to read as point series.

### D-028 Bronze ingestion architecture
`Decided` · 2026-11-24
- **Decision:** one generic build pipeline, configured per source by a declarative spec.
  - **`SourceSpec`** (one per source, in a registry `SOURCES: dict[str, SourceSpec]`): file patterns, target schema, text encoding (null tokens, decimal separator, date/time formats), sort keys, the keys expected to be unique, the time column, and a reader.
  - **Readers**, one class per **file format** (not per source), behind a `RawReader` protocol: `ParquetReader` for all ONS sources, `ArcGisQueryReader` for SIGEL, `InmetObservationReader` and `InmetStationReader` for INMET; an ERA5 reader is added when that data lands. The spec holds a reader instance, so the pipeline never branches on file type.
  - **Pipeline:** `build_bronze(spec, paths)` and `build_all(names)`. They receive everything they use (dependency injection).
  - **Layout:** code in `src/scripts/bronze/` (`readers.py`, `raw_formats/`, `schemas.py` for column dtypes, `specs.py` for everything else per source, `casting.py`, `build.py`, `__main__.py`); reusable checks, paths and logging in `src/scripts/utils/`.
    - **Format descriptions vs reading code:** what a raw format looks like (header spellings, field-type tables, file-name patterns) is data, in `raw_formats/<format>.py`, constants only. All reading code is in `readers.py`, which refers to them as `<format>.<NAME>`. A format gets a description module only when it has something to describe (Parquet has none). Why: the likely change, a source spelling its files differently, is then a one-line edit in a file of spellings that can be checked against a raw file, and the layout states the rule. The directory is named `raw_formats`, not `formats`, because `TextEncoding.formats` already means date/time formats (2026-11-26).
- **Processing:** one raw file at a time: read → cast to the spec's schema → check → stable sort by the sort keys → write one part. Peak memory is one raw file, not the whole source.
- **Output:** a directory of sorted parts per source, `bronze/<source>/part-NNNNN.parquet`, numbered in time order, plus `_bronze_meta.json` (input files with sha256, rows, casts, null-token counts, duplicate counts, time ranges, git commit, Polars version). `pl.scan_parquet("bronze/<source>/*.parquet")` reads it as one table.
  - The raw files split each source by time period without overlap, so time-ordered parts give a globally sorted source without a global sort (D-011). The build fails if two parts' time ranges overlap.
  - A source is rebuilt into a temporary directory and swapped in only when complete. It is skipped when its spec and input hashes match the existing metadata.
- **Casting rules:** every column must be declared; a missing or unexpected column fails the build (schema drift is caught, never silently passed on). Strings become numbers, dates or times only through strict casts: an unparseable value fails the build. The exceptions are each source's declared null tokens (by default the empty string `""`, ONS's encoding of a missing number): they become null only where text becomes a typed value, and are counted in the metadata.
- **Bronze reports, silver decides:** duplicate keys, invalid-data flags, the `Eólica` filter and timezone handling are left to silver. Bronze only counts duplicates. Timestamps stay timezone-naive and unchanged.
- **Execution:** sequential; Polars multithreads within each file. The work is CPU- and memory-bound on a 2-core, 3 GB WSL machine, so running sources in parallel would compete for cores and multiply peak memory. Sources share no state, so a process pool can be added if the pipeline moves to a larger machine.
- **Not adopted: Delta Lake.** Its atomic commits, schema enforcement and upserts are already covered (single writer + directory swap, spec casts, part rebuilds). Its time travel would pin bronze versions, but training reads gold (D-002) and provenance is in the metadata. It would add a dependency, disk used by old versions, and force every reader through `scan_delta`. **Revisit if:** several writers, or the need to roll bronze back to an earlier version.
- **Revisit if:** a source needs different processing *steps* (not just different values): add an optional per-spec transform hook then, not before.
- 2026-11-24: second reader added, `ArcGisQueryReader`, for the ANEEL SIGEL snapshot (JSON query responses). Column dtypes come from each response's `fields` list, converted strictly. Point geometry becomes `geometry_x`/`geometry_y`; other geometry is kept as JSON text. Specs gained `raw_folder` (several sources share one dated snapshot folder, which the spec pins) and `companions` (expected non-data files). The unclaimed-file check moved to `build_all`, across all specs. Sources without a time column count duplicate keys across all their parts, since pages can repeat a key.
- 2026-11-26: INMET added as two sources read from the same yearly archives (`raw/inmet/<YYYY>.zip`): `inmet_horario` (hourly observations, one part per year) and `inmet_estacoes` (the station lines of each CSV, one row per station and year, since coordinates and altitude change between years). Three generic changes:
  - **Readers yield chunks** (`RawReader.scan` returns an iterator). An INMET archive yields one chunk per station CSV, and each is cast before the next is decompressed: a year of INMET as text does not fit in memory. Parquet and ArcGIS readers yield one chunk, as before.
  - **`TextEncoding`** per spec groups how a source writes values as text: null tokens (default `("",)`; INMET observations add `"-9999"`, stations `"F"` and `"NULL"`), the decimal separator, and date/time formats. Tokens are counted per column and token (`null_tokens_to_null` replaces `empty_strings_to_null`). A column may list several formats: the one that parses a chunk's first value is applied strictly to the whole chunk, so mixed or ambiguous formats fail instead of being parsed value by value. A `.` in a number under a `,` separator fails.
  - **Float32 guard:** a text value cast to Float32 must have at most 6 significant digits, which Float32 holds exactly. INMET measurements are Float32: a year as Float64 peaked at 2.5 GB during the sort against 1.5 GB (2018, measured 2026-11-26), with ~2 GB free when VS Code is open. Silver casts to Float64 before arithmetic that accumulates error.
  - The INMET readers (in `readers.py`, format description in `raw_formats/inmet.py`) only take the format apart (archive layout, the three spellings of the station keys and of the column header, columns named by position, row shape, station code against the file name); values stay text for the cast. Station foundation dates stay text: the newer `dd/mm/yy` spelling has two-digit years, resolved in silver.

## Graph and model

### D-004 Weather-driven edges computed on the fly
`Proposed` · 2026-11-21
- **Decision:** store per-node weather `[T, N, F_w]` (used only to build edges, D-018) and static pairwise geometry `[N, N]` (distance, bearing). Compute edge features, such as wind–bearing alignment, on the GPU for each batch.
- **Why:**
  - Stored time-varying edges grow with T·N² per feature.
  - Each edge-source ablation would need its own stored copy.
  - Edges with learned parameters (e.g. learned distance decay) can't be precomputed.
  - Computing them is cheap and usually faster than reading them back.
- **Exception:** store edges that are expensive to compute and fixed: correlation- or Granger-based graphs fitted on training data, and sparse top-k edges if computing them becomes a bottleneck.

### D-005 Always add self-loops
`Proposed` · 2026-11-21
- **Decision:** every node always has an edge to itself.
- **Why:** a node with no active incoming edges otherwise gets a softmax over a row that is entirely −∞, which returns NaN.
- **Requires:** a test for the case of a node with no incoming edges.

### D-006 Edge-builder output format
`Open` · 2026-11-21
- **Options:** dense mask/adjacency `[B, T, N, N]`, or top-k neighbour indices and weights `[B, T, N, k]`.
- **Constraint:** every edge source must produce the same format, so fix it early. Depends on D-007.
- **Constraint:** the format must also cover edges between two node types (D-019): one tensor per relation, of shape `[B, T, N_dst, N_src]` (or top-k per relation). A farms-only format would have to be redone.

### D-007 Number of nodes N, and dense vs. top-k attention
`Open` · 2026-11-21
- **Question:** how many nodes N (plants or conjuntos) the model will have.
- **Memory:** attention scores grow with B·T·N²·heads per layer. At fp16 with batch 32, a 168 h window and 4 heads: ~1.7 GB per layer at N = 200, ~11 GB at N = 500.
- **Mitigations:** top-k neighbours in fixed-shape tensors (memory grows with N·k), or compressing the time axis before spatial mixing (as Graph WaveNet does).

### D-016 GNN layers on dense tensors
`Proposed` · 2026-11-21
- **Decision:** GNN layers are written in plain PyTorch and operate on dense tensors, in the format fixed by D-006.
- **Why:** small graphs whose edges change at every step batch naturally as tensors. Most reference models (Graph WaveNet, AGCRN, MTGNN, StemGNN, FourierGNN) are written this way, and custom layers (masked attention, learned distance decay) are short.
- **Trade-off:** GATv2-style attention and heterogeneous graphs (e.g. station → plant) must be written by hand.

### D-018 Weather is used only to build edges
`Decided` · 2026-11-21
- **Decision:** farm nodes carry no weather features. Their features are past generation and capacity factor. Weather enters the model only through the edges it builds.
- **Why:** every model then sees the same node features, so the graph is the only difference between the proposed model and the baselines. That is the paper's claim.
- **Leakage:** edges used to forecast t+1…t+h may only use weather up to t. They are built from the input window, or fixed at the forecast origin for the whole horizon.
- **Wind direction:** ONS gives wind speed but no direction, so direction comes from ERA5 (u/v at 100 m) or INMET stations. Interpolate u/v, never angles.
- **Requires:** the weather-as-features control (D-026).

### D-019 Heterogeneous farm + weather-station graph
`Open` · 2026-11-21
- **Idea:** a variant with two node types, wind farms and INMET weather stations. Stations carry weather observations as node features, and station → farm edges follow the upwind direction. Here D-018 applies to farm nodes only.
- **Why:** INMET observations are real measurements, available at the time they're reported (no reanalysis leakage, D-023). Upwind stations see a weather change before the farm does.
- **Trade-off:** message passing between two node types is written by hand (D-016). INMET has gaps, 9999 codes and station outages, so station features need a mask. Gold gains station features `[T, S, F_s]` with a mask, and farm–station geometry `[N, S]`.
- **Requires:** its own control: a farms-only graph whose nodes get the same station data as inputs.
- **Go/no-go:** build the farms-only model first; add this variant only if that model works by the date in ROADMAP.md. The number of INMET stations near the farms (bronze EDA) decides whether it's worth it.

## Training and efficiency

### D-008 Windows sliced by index
`Proposed` · 2026-11-21
- **Decision:** store each series once and slice windows by start index; never materialise windows in advance. If the gold tensors fit in GPU memory, keep them there and slice on the GPU.
- **Why:** removes duplicate storage and the CPU data loader as a bottleneck.

### D-009 Precision picked from the detected GPU
`Proposed` · 2026-11-21
- **Decision:** bf16 autocast on L4/A100; fp16 autocast with a gradient scaler on T4. Select it from the detected GPU, never hard-code it.
- **Why:** sessions may fall back to a T4, which has no bf16 support.

### D-010 `torch.compile` deferred
`Proposed` · 2026-11-21
- **Decision:** try `torch.compile` only once the model is stable.
- **Why:** recompiles and compile errors slow down iteration. Fixed shapes (e.g. top-k) avoid recompiles.

### D-011 Statistical reproducibility
`Decided` · 2026-11-21
- **Decision:** training results are reproducible statistically, not bit for bit.
  - Fix every seed: Python, NumPy, torch and the DataLoader workers.
  - Don't force deterministic GPU algorithms.
  - Run every configuration with several seeds (how many: D-015) and report mean ± spread.
  - Compare edge sources on the same set of seeds. Don't claim a difference smaller than the seed spread.
- **Why:** bit-exact reruns hold only on the same GPU model, driver and torch/CUDA versions. Colab guarantees none of these: L4, A100 or T4 depending on the day, a preinstalled torch that changes over time, and bf16 vs. fp16 by GPU (D-009). Forcing determinism would also slow training, and operations without a deterministic implementation raise errors.
- **Scope:** training only. The data pipeline must be exactly reproducible: sort outputs before writing each layer, because Polars `group_by` doesn't keep row order unless given `maintain_order=True`.
- **Requires:** each run logs the GPU model, torch/CUDA versions, seed, git commit and config.
- **Debug flag:** a config option turns on deterministic algorithms (`torch.use_deterministic_algorithms(True)`, `cudnn.deterministic=True`, `cudnn.benchmark=False`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`) on one machine. It is for checking that a refactor didn't change results or for chasing a NaN, never for reported results.
- 2026-11-21: Proposed → Decided (the user wants statistical reproducibility).

### D-017 Training loop and models written in-house
`Decided` · 2026-11-21
- **Decision:** one shared plain-PyTorch training loop for all models, and every model written in-house. Baselines (Graph WaveNet, AGCRN, DCRNN, …) are adapted from their official implementations.
- **Why:** every model runs under the same loop, so a comparison differs only by the model.
- **Requires:** check each baseline's licence and credit the source in the code.

## Experiments and infrastructure

### D-012 Dev mode and tuning budget
`Proposed` · 2026-11-21
- **Decision:** a dev-mode config with a small subset (~20 nodes × 1 year) for fast iteration and smoke tests. Tune hyperparameters on one fold with early stopping (ASHA/Hyperband). Run all folds × seeds only for final results.

### D-013 Running experiments on Colab
`Proposed` · 2026-11-21
- **Decision:**
  - Hydra multirun for small fixed grids (e.g. edge source × seed).
  - W&B sweeps for hyperparameter search: the sweep state lives on W&B's servers and survives disconnects.
  - Notebooks stay thin and run `!python -m <pkg>.train -m …` as a subprocess.
- **Why:** Colab sessions time out, and Hydra doesn't resume an interrupted multirun.
- **Requires:** every run is skippable. A run exits early if it already completed (a completion marker on Drive, or a finished W&B run with the same config).

### D-014 Where things run
`Proposed` · 2026-11-21
- **Decision:** run the data pipeline where RAM is largest and the disk persists (probably the local machine). Train on Colab, reading the gold layer from Drive.
- **Requires:** a compact gold layer (fp16, only the variables used) because of the 15 GB Drive limit.

### D-015 Experiment compute budget
`Open` · 2026-11-21
- **Question:** the number of ablations × seeds × folds the compute allows.
- **Where:** to be set in ROADMAP.md (phase 2). D-012, D-013 and D-021 depend on it.

### D-029 Optional run logs by step
`Decided` · 2026-11-24
- **Decision:** every entry point logs to the terminal. With `--save-log`, it also writes the full log, DEBUG included, to `src/logs/<step>/<UTC timestamp>.log`, where the step is a relative path such as `data/bronze`, `data/silver` or `model/DCRNN`. Timestamps are UTC in file names and log lines. Outputs name the log of the run that built them (`run_log` in `_bronze_meta.json`).
- **Why:** costly steps (full rebuilds, training) need a record that outlives the terminal; quick runs don't. Grouping by step keeps data and model logs apart.
- **Colab:** set `$WIND_GNN_LOG_ROOT` to a Drive folder, since the runtime's disk is wiped when a session ends.
- **Code:** `scripts.utils.log` (`setup_logging`, `new_log_file`) and `scripts.utils.paths.resolve_log_root`. `src/logs/` is gitignored.

## Evaluation and baselines

### D-020 Study period and splits
`Decided` · 2026-11-21
- **Decision:** the study period starts in 2021-10. Splits are chronological, one full year for each evaluation split:
  - train: 2021-10 → 2024-10
  - validation: 2024-11 → 2025-10
  - test: 2025-11 → 2026-10
- **Why:** curtailment information (`flg_geracaorestrita`, curtailment reasons) exists only from 2021-10, and curtailment must be handled explicitly. Full years cover the whole seasonal cycle, including the northeast's strong wind season (roughly Jul–Nov).
- **Requires:** everything fitted on data (scalers, correlation graphs) is fitted on train only.

### D-021 Folds and seeds
`Proposed` · 2026-11-21
- **Decision:** one chronological split (D-020) with 5 seeds. Add rolling-origin folds only if the compute budget (D-015) allows.
- **Why:** the deadline; seed spread is what D-011 reports.

### D-022 Horizon and metrics
`Proposed` · 2026-11-21
- **Horizon:** h = 1…6 h is the main result, reported per horizon; h stays configurable. Without observed weather after t as an input, skill over persistence shrinks after a few hours.
- **Metrics:** MAE and RMSE on capacity factor, which is comparable across nodes, per horizon; plus a skill score against persistence.
- **Masking:** curtailed and missing time steps are masked out of both the loss and the metrics.

### D-023 ERA5 reanalysis leakage
`Open` · 2026-11-21
- **Problem:** ERA5 is a reanalysis. Its value at time t comes from data assimilation over a window that can include observations made after t, and its public release lags by days. Using ERA5 at t as "available at t" can leak a little future information, through the edges (D-018) as much as through inputs.
- **Options:** state it as an assumption in the paper; lag the ERA5 inputs; use INMET observations as the live weather source (see D-019).
- **Decide before:** the silver layer.

### D-024 Simple baselines
`Decided` · 2026-11-21
- **Decision:** persistence, diurnal persistence (the same hour yesterday), and per-node linear AR(p) on lagged values.
- **Why:** at short horizons persistence is hard to beat, and reviewers check it first. These baselines also catch pipeline bugs.

### D-025 Further baselines
`Proposed` · 2026-11-21
- **Decision:**
  - Climatology: the average for that hour and month at that node.
  - A deep model with no graph: a per-node MLP or LSTM on the same node features. It shows whether the graph adds anything at all.
  - 2–3 GNN baselines from D-017.
  - Optional: ONS's own forecast (`previsao_vs_programado`) as an operational reference. It's keyed by `cod_usinapdp` and made day-ahead, so it may only be comparable for aggregates.
- **Open within it:** which edges the GNN baselines get (fully connected, distance-based, or their own learned adjacency).
- **Optional:** variants of AR and the no-graph model with weather inputs (ARX).

### D-026 Weather-as-features control
`Decided` · 2026-11-21
- **Decision:** a required experiment: the proposed model with weather as node features and non-weather edges (distance-based or fully connected).
- **Why:** it answers the obvious reviewer question: does weather help because it shapes the graph, or would it help just as much as a plain input? If weather edges beat this control, the paper's claim stands.

### D-027 Design freeze and a single test evaluation
`Decided` · 2026-11-21
- **Decision:** model development iterates on validation only, up to a design freeze (date in ROADMAP.md). After the freeze: no architecture changes, only the final runs. The test set is evaluated once, after the freeze. A poor test result is reported; it doesn't reopen development.
- **Requires:** every variant tried is logged in W&B, so the paper can say honestly what was explored.
