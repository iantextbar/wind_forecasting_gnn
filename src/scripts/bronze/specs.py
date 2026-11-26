"""Declarative description of every raw source: what bronze expects and produces.

Each spec declares where its raw files are, how to read them and how rows are keyed.
Column dtypes, units and drift notes live in ``schemas.py``.

Keys:
- ``sort_keys`` give each part a deterministic order (D-011). They start with the
  time column, so time-ordered parts form a globally sorted source.
- ``unique_keys`` are the expected identity of a row. Bronze only counts
  violations; silver decides what to do about them. For time-ordered sources they
  include the time column: parts never share an instant, so per-part counts add up
  to the source's count.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

import polars as pl

from scripts.bronze.casting import TextEncoding
from scripts.bronze.readers import (
    ArcGisQueryReader,
    InmetObservationReader,
    InmetStationReader,
    ParquetReader,
    RawReader,
)
from scripts.bronze.schemas import (
    CADASTRO_CAPACIDADE_INSTALADA_SCHEMA,
    CADASTRO_MODALIDADE_USINA_SCHEMA,
    CADASTRO_RELACIONAMENTO_USINA_CONJUNTO_SCHEMA,
    COFF_DETALHAMENTO_USINA_SCHEMA,
    COFF_INTRA_SEMIHORA_SCHEMA,
    COFF_USINA_CONJUNTO_SCHEMA,
    DISPONIBILIDADE_USINA_SCHEMA,
    FATOR_CAPACIDADE_SCHEMA,
    GERACAO_USINA_HORARIA_SCHEMA,
    INMET_ESTACOES_SCHEMA,
    INMET_HORARIO_SCHEMA,
    PREVISAO_VS_PROGRAMADO_SCHEMA,
    SIGEL_AEROGERADORES_SCHEMA,
    SIGEL_PARQUES_SCHEMA,
    SIGEL_REGIAO_INTERFERENCIA_SCHEMA,
)

ISO_DATE = "%Y-%m-%d"
COMPACT_DATE = "%Y%m%d"
CLOCK_TIME = "%H:%M:%S"

# Documentation shipped next to the data files.
ONS_COMPANIONS = ("DicionarioDados_*.pdf",)
SIGEL_SNAPSHOT = "aneel_sigel_eolicas/20261124T183056Z"
SIGEL_COMPANIONS = (
    "servico_metadata.json",
    "camada_*_metadata.json",
    "manifesto.csv",
    "execucao.json",
)


@dataclass(frozen=True)
class SourceSpec:
    """Everything bronze needs to know about one raw source.

    Attributes:
        name: folder under ``bronze/``; also the folder under ``raw/`` unless
            ``raw_folder`` is given.
        patterns: glob patterns selecting the raw files inside the raw folder.
        schema: every column with its bronze dtype, in output order.
        sort_keys: columns for a stable sort within each part.
        unique_keys: columns expected to identify a row; violations are counted.
        time_column: column whose range orders the parts and must not overlap
            between them; None for static registries.
        encoding: how the raw files write values as text (null tokens, decimal
            separator, date/time formats); see ``casting.TextEncoding``.
        reader: how to read one raw file.
        raw_folder: path under ``raw/`` when it differs from ``name``: several
            sources share one folder, or the source pins a dated snapshot.
        companions: glob patterns of non-data files expected in the raw folder
            (dictionaries, manifests), so they aren't reported as unclaimed.
    """

    name: str
    patterns: tuple[str, ...]
    schema: Mapping[str, pl.DataType]
    sort_keys: tuple[str, ...]
    unique_keys: tuple[str, ...]
    time_column: str | None
    encoding: TextEncoding = TextEncoding()
    reader: RawReader = ParquetReader()
    raw_folder: str | None = None
    companions: tuple[str, ...] = ()

    @property
    def raw_path(self) -> str:
        """Folder of this source's raw files, relative to ``raw/``."""
        return self.raw_folder or self.name

    def __post_init__(self) -> None:
        declared = set(self.schema)
        referenced = {*self.sort_keys, *self.unique_keys, *self.encoding.formats}

        if self.time_column is not None:
            referenced.add(self.time_column)
            if self.sort_keys[:1] != (self.time_column,):
                raise ValueError(
                    f"{self.name}: sort_keys must start with the time column "
                    "so that time-ordered parts are globally sorted"
                )
            if self.time_column not in self.unique_keys:
                raise ValueError(
                    f"{self.name}: unique_keys must include the time column, "
                    "otherwise duplicates spanning two parts would go uncounted"
                )

        if unknown := referenced - declared:
            raise ValueError(
                f"{self.name}: keys/formats name undeclared columns {sorted(unknown)}"
            )

    def describe(self) -> dict[str, object]:
        """JSON-serialisable description, stored in the bronze metadata."""
        return {
            "name": self.name,
            "raw_path": self.raw_path,
            "patterns": list(self.patterns),
            "schema": {name: str(dtype) for name, dtype in self.schema.items()},
            "sort_keys": list(self.sort_keys),
            "unique_keys": list(self.unique_keys),
            "time_column": self.time_column,
            "encoding": self.encoding.describe(),
            "reader": repr(self.reader),
        }

    def fingerprint(self) -> str:
        """Stable text identifying the spec; a change forces a rebuild."""
        return json.dumps(self.describe(), sort_keys=True)


FATOR_CAPACIDADE = SourceSpec(
    name="fator_capacidade_geracao_eolica_solar",
    companions=ONS_COMPANIONS,
    # Yearly files 2009-2021, monthly files 2022 onwards.
    patterns=("FATOR_CAPACIDADE_*.parquet", "FATOR_CAPACIDADE-2_*.parquet"),
    schema=FATOR_CAPACIDADE_SCHEMA,
    sort_keys=("din_instante", "id_ons"),
    unique_keys=("id_ons", "din_instante"),
    time_column="din_instante",
)

COFF_DETALHAMENTO_USINA = SourceSpec(
    name="constrained_off_eolica_detalhamento_usina",
    companions=ONS_COMPANIONS,
    patterns=("RESTRICAO_COFF_EOLICA_DETAIL_*.parquet",),
    schema=COFF_DETALHAMENTO_USINA_SCHEMA,
    sort_keys=("din_instante", "id_ons"),
    unique_keys=("id_ons", "din_instante"),
    time_column="din_instante",
)

COFF_USINA_CONJUNTO = SourceSpec(
    name="constrained_off_eolica_usina_conjunto",
    companions=ONS_COMPANIONS,
    patterns=("RESTRICAO_COFF_EOLICA_*.parquet",),
    schema=COFF_USINA_CONJUNTO_SCHEMA,
    sort_keys=("din_instante", "id_ons"),
    unique_keys=("id_ons", "din_instante"),
    time_column="din_instante",
)

COFF_INTRA_SEMIHORA = SourceSpec(
    name="constrained_off_eolica_intra_semihora",
    companions=ONS_COMPANIONS,
    patterns=("COFF_USI_EOLICAS_INTRASEMIHORA_*.parquet",),
    schema=COFF_INTRA_SEMIHORA_SCHEMA,
    sort_keys=("din_instante", "id_ons", "hor_inicial"),
    unique_keys=("id_ons", "din_instante", "hor_inicial"),
    time_column="din_instante",
    encoding=TextEncoding(
        formats={"hor_inicial": (CLOCK_TIME,), "hor_final": (CLOCK_TIME,)}
    ),
)

DISPONIBILIDADE_USINA = SourceSpec(
    name="disponibilidade_usina",
    companions=ONS_COMPANIONS,
    patterns=("DISPONIBILIDADE_USINA_*.parquet",),
    schema=DISPONIBILIDADE_USINA_SCHEMA,
    sort_keys=("din_instante", "id_ons"),
    unique_keys=("id_ons", "din_instante"),
    time_column="din_instante",
)

GERACAO_USINA_HORARIA = SourceSpec(
    name="geracao_usina_horaria",
    companions=ONS_COMPANIONS,
    # Yearly files 2000-2021, monthly files 2022 onwards.
    patterns=("GERACAO_USINA-2_*.parquet",),
    schema=GERACAO_USINA_HORARIA_SCHEMA,
    sort_keys=("din_instante", "id_ons"),
    unique_keys=("id_ons", "din_instante"),
    time_column="din_instante",
)

PREVISAO_VS_PROGRAMADO = SourceSpec(
    name="previsao_vs_programado_eolica_solar",
    companions=ONS_COMPANIONS,
    patterns=("PROGRAMACAO_X_PREVISAO_*.parquet",),
    schema=PREVISAO_VS_PROGRAMADO_SCHEMA,
    sort_keys=("dat_programacao", "num_patamar", "cod_usinapdp"),
    unique_keys=("cod_usinapdp", "dat_programacao", "num_patamar"),
    time_column="dat_programacao",
    encoding=TextEncoding(formats={"dat_programacao": (COMPACT_DATE,)}),
)

CADASTRO_CAPACIDADE_INSTALADA = SourceSpec(
    name="cadastro_capacidade_instalada",
    companions=ONS_COMPANIONS,
    patterns=("CAPACIDADE_GERACAO.parquet",),
    schema=CADASTRO_CAPACIDADE_INSTALADA_SCHEMA,
    sort_keys=("ceg", "cod_equipamento"),
    unique_keys=("cod_equipamento",),
    time_column=None,
    encoding=TextEncoding(
        formats={
            "dat_entradateste": (ISO_DATE,),
            "dat_entradaoperacao": (ISO_DATE,),
            "dat_desativacao": (ISO_DATE,),
        }
    ),
)

CADASTRO_MODALIDADE_USINA = SourceSpec(
    name="cadastro_modalidade_usina",
    companions=ONS_COMPANIONS,
    patterns=("MODALIDADE_USINA.parquet",),
    schema=CADASTRO_MODALIDADE_USINA_SCHEMA,
    sort_keys=("ceg", "id_ons"),
    unique_keys=("ceg",),
    time_column=None,
)

CADASTRO_RELACIONAMENTO_USINA_CONJUNTO = SourceSpec(
    name="cadastro_relacionamento_usina_conjunto",
    companions=ONS_COMPANIONS,
    patterns=("RELACIONAMENTO_USINA_CONJUNTO.parquet",),
    schema=CADASTRO_RELACIONAMENTO_USINA_CONJUNTO_SCHEMA,
    sort_keys=("id_ons_conjunto", "id_ons_usina", "dat_iniciorelacionamento"),
    unique_keys=("id_ons_conjunto", "id_ons_usina", "dat_iniciorelacionamento"),
    time_column=None,
    encoding=TextEncoding(
        formats={
            "dat_iniciorelacionamento": (ISO_DATE,),
            "dat_fimrelacionamento": (ISO_DATE,),
        }
    ),
)

# SIGEL layers are a snapshot of the current registry, not a time series.
SIGEL_AEROGERADORES = SourceSpec(
    name="sigel_aerogeradores",
    raw_folder=SIGEL_SNAPSHOT,
    patterns=("camada_0_pagina_*.json",),
    companions=SIGEL_COMPANIONS,
    reader=ArcGisQueryReader(),
    schema=SIGEL_AEROGERADORES_SCHEMA,
    sort_keys=("OBJECTID",),
    unique_keys=("CEG", "DEN_AEG"),
    time_column=None,
)

SIGEL_REGIAO_INTERFERENCIA = SourceSpec(
    name="sigel_regiao_interferencia",
    raw_folder=SIGEL_SNAPSHOT,
    patterns=("camada_1_pagina_*.json",),
    companions=SIGEL_COMPANIONS,
    reader=ArcGisQueryReader(),
    schema=SIGEL_REGIAO_INTERFERENCIA_SCHEMA,
    sort_keys=("OBJECTID",),
    unique_keys=(
        "EOL_VERSAO",
    ),  # one region per farm expected; some farms have several
    time_column=None,
)

SIGEL_PARQUES = SourceSpec(
    name="sigel_parques",
    raw_folder=SIGEL_SNAPSHOT,
    # Layers 2-5 share one schema: farms in operation, under construction,
    # construction not started, and DRO (earliest licensing stage).
    # FASE tells them apart.
    patterns=("camada_[2-5]_pagina_*.json",),
    companions=SIGEL_COMPANIONS,
    reader=ArcGisQueryReader(),
    schema=SIGEL_PARQUES_SCHEMA,
    sort_keys=("OBJECTID",),
    unique_keys=("CEG",),
    time_column=None,
)

# INMET: yearly archives of station CSVs; observations and station lines are two
# sources read from the same archives (scripts.bronze.raw_formats.inmet).
INMET_FOLDER = "inmet"
INMET_PATTERNS = ("*.zip",)
INMET_COMPANIONS = ("SHA256SUMS",)
INMET_DECIMAL_SEPARATOR = ","
# The file name's period, dd-mm-yyyy.
INMET_PERIOD = "%d-%m-%Y"

INMET_HORARIO = SourceSpec(
    name="inmet_horario",
    raw_folder=INMET_FOLDER,
    patterns=INMET_PATTERNS,
    companions=INMET_COMPANIONS,
    reader=InmetObservationReader(),
    schema=INMET_HORARIO_SCHEMA,
    encoding=TextEncoding(
        # Missing values: "-9999" in 2009-2018, empty from 2019.
        null_tokens=("", "-9999"),
        decimal_separator=INMET_DECIMAL_SEPARATOR,
        # 2009-2018 spelling first, 2019 onwards second.
        formats={
            "data": ("%Y-%m-%d", "%Y/%m/%d"),
            "hora_utc": ("%H:%M", "%H%M UTC"),
        },
    ),
    sort_keys=("data", "hora_utc", "codigo_wmo"),
    unique_keys=("codigo_wmo", "data", "hora_utc"),
    time_column="data",
)

INMET_ESTACOES = SourceSpec(
    name="inmet_estacoes",
    raw_folder=INMET_FOLDER,
    patterns=INMET_PATTERNS,
    companions=INMET_COMPANIONS,
    reader=InmetStationReader(),
    schema=INMET_ESTACOES_SCHEMA,
    encoding=TextEncoding(
        # Altitude is "F" for 17 stations in 2016-2018 and "NULL" once (2026).
        # Reading "F" as missing is an inference: INMET doesn't document it.
        null_tokens=("", "F", "NULL"),
        decimal_separator=INMET_DECIMAL_SEPARATOR,
        formats={"periodo_inicio": (INMET_PERIOD,), "periodo_fim": (INMET_PERIOD,)},
    ),
    # One row per station and year: coordinates and altitude change between years.
    sort_keys=("periodo_inicio", "codigo_wmo"),
    unique_keys=("codigo_wmo", "periodo_inicio"),
    time_column="periodo_inicio",
)

SOURCES: dict[str, SourceSpec] = {
    spec.name: spec
    for spec in (
        FATOR_CAPACIDADE,
        COFF_DETALHAMENTO_USINA,
        COFF_USINA_CONJUNTO,
        COFF_INTRA_SEMIHORA,
        DISPONIBILIDADE_USINA,
        GERACAO_USINA_HORARIA,
        PREVISAO_VS_PROGRAMADO,
        CADASTRO_CAPACIDADE_INSTALADA,
        CADASTRO_MODALIDADE_USINA,
        CADASTRO_RELACIONAMENTO_USINA_CONJUNTO,
        SIGEL_AEROGERADORES,
        SIGEL_REGIAO_INTERFERENCIA,
        SIGEL_PARQUES,
        INMET_HORARIO,
        INMET_ESTACOES,
    )
}
