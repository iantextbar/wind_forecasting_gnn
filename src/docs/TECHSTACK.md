# Tech stack

The libraries and compute this project uses. Design rules are in [DECISIONS.md](DECISIONS.md); `D-NNN` refers to an entry there.

**Status:** `Decided` · `Proposed` (recommended, waiting for the user's confirmation) · `Open` (not decided yet).

## Libraries

| Purpose | Library | Status | Why | Trade-off |
|---|---|---|---|---|
| Deep learning | PyTorch | `Decided` | The training loop, models and GNN layers are written on it (D-016, D-017). | — |
| Tensor reshaping | `einops` | `Proposed` | Readable switching between temporal and spatial axes, with runtime shape checks. | A notation to learn. Use it only for multi-axis operations. |
| Configs | Hydra, structured (dataclass) configs | `Proposed` | Config groups map onto ablations (`edge_builder=…`); each run gets a folder with its resolved config and log. Usage on Colab: D-013. | Built for command-line scripts: the notebook API has no multirun, and an interrupted multirun doesn't resume. |
| Tabular data | Polars, lazy API scanning Parquet | `Proposed` | Fast on one machine; filtering and column selection happen before loading, which matters with little RAM. | API differs from pandas. Libraries that expect pandas need a conversion through Arrow, which is cheap. |
| Gridded data | xarray + Zarr/NetCDF | `Proposed` | Reads ERA5 from the ARCO-ERA5 Zarr store or the CDS API. Per-node series are extracted once, then handled in Polars (D-003). | A Zarr store chunked by time is slow to read as long point series. |
| Data validation | `pandera`, Polars backend | `Proposed` | Validates whole columns at layer boundaries, LazyFrames included (Polars support since v0.19, checked 2026-11-21). | — |
| Logging | Standard-library `logging`, set up by `scripts.utils.log` | `Decided` | Third-party libraries log through it too. Saving a run's log is optional, in `src/logs/<step>/` (D-029). Hydra's own log files come only with `@hydra.main`, which D-013 rules out. | — |
| Experiment tracking | Weights & Biases: runs, sweeps, Artifacts for checkpoints (optionally data snapshots) | `Proposed` | Works from Colab with no server to run; its storage outlives the runtime. | A cloud account and some lock-in. |
| Environment | `uv` + `pyproject.toml` + lockfile. On Colab: `git clone` + `pip install -e .` | `Proposed` | The same environment locally and on Colab. | Setup at the start of each session. Colab's preinstalled torch changes over time, so each run logs its torch/CUDA versions (D-011). |
| Code quality | `ruff` (lint and format; PEP 8, line length 88, config in `pyproject.toml`), `pytest` | `Decided` | Standard and fast. In use since 2026-11-24. | — |
| Code quality | pre-commit hooks running `ruff` | `Proposed` | Keeps new code formatted without remembering to run it. | One more tool to install. |

## Compute

### Hardware
- **Colab Pro through the Colab extension in VS Code** (`Decided`): L4/A100 GPUs when available, T4 as fallback. Precision follows the detected GPU (D-009).

### Colab limits and how the design answers them
| Limit | Consequence |
|---|---|
| The runtime can't read local files (checked 2026-11-21). | Upload with the "Upload to Colab" command, or fetch data inside the runtime. Training reads the gold layer from Drive (D-014). |
| The disk is wiped when the session ends, and sessions time out. | Runs are skippable and resumable from Drive/W&B (D-013). |
| Few CPU cores, limited RAM. | Lazy scans before loading; no per-sample pivoting on the CPU (D-002, D-008). The data pipeline runs where RAM is largest (D-014). |
| Free Drive storage is 15 GB, and reading from it is slow. | A compact gold layer: fp16, only the variables used (D-014). |

### Scale
- **Data:** ONS tables have up to ~100M rows. ERA5 is gridded, ~17 years, hourly, so only the cells around each node are extracted (D-003).
- **Graph:** tens to a few hundred nodes, with edges that change at every time step. Attention memory grows with N² (D-007).
