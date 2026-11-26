"""INMET automatic-station data: yearly zip archives of CSV files.

Surveyed on 2026-11-26 over every archive from 2009 to 2026 (``raw/SOURCES.md``):
- ``<YYYY>.zip`` holds one CSV per station and year. Some years keep them in a
  ``<YYYY>/`` folder, others at the archive root.
- Latin-1, ``;``-separated, every line ending in ``;``. Eight ``key;value`` lines
  describe the station, then one column header, then hourly rows.
- The station keys and the column header each have three spellings across the
  years. Every spelling is listed here, and the reader rejects any other, so new
  drift is caught. They differ only in names, never in order, so columns are named
  by position.

Values stay text as written (decimal commas, ``-9999``, two date spellings); how
to read them is the spec's ``TextEncoding``.
"""

from __future__ import annotations

import re

TEXT_ENCODING = "latin-1"
SEPARATOR = ";"
NEWLINE = b"\n"  # every surveyed file uses LF; a CR before it would be stripped
STATION_LINES = 8
HEADER_LINES = STATION_LINES + 1  # station lines + column header

# INMET_<REGIAO>_<UF>_<CODIGO>_<ESTACAO>_<dd-mm-yyyy>_A_<dd-mm-yyyy>.CSV; the dates
# are the period the file covers.
MEMBER_NAME = re.compile(
    r"^INMET_(?P<regiao>[A-Z]+)_(?P<uf>[A-Z]{2})_(?P<codigo>[A-Z]\d{3})_"
    r"(?P<estacao>.+)_(?P<inicio>\d{2}-\d{2}-\d{4})_A_(?P<fim>\d{2}-\d{2}-\d{4})\.CSV$"
)

# --- Station lines ---

# Bronze name of each station line, in file order.
STATION_FIELDS = (
    "regiao",
    "uf",
    "estacao",
    "codigo_wmo",
    "latitude",
    "longitude",
    "altitude",
    "data_fundacao",
)
STATION_CODE = "codigo_wmo"

STATION_KEY_SPELLINGS = frozenset(
    {
        # 2009-2018
        (
            "REGIÃO:",
            "UF:",
            "ESTAÇÃO:",
            "CODIGO (WMO):",
            "LATITUDE:",
            "LONGITUDE:",
            "ALTITUDE:",
            "DATA DE FUNDAÇÃO (YYYY-MM-DD):",
        ),
        # 2019: the accented letters are literal "?" in INMET's files.
        (
            "REGI?O:",
            "UF:",
            "ESTAC?O:",
            "CODIGO (WMO):",
            "LATITUDE:",
            "LONGITUDE:",
            "ALTITUDE:",
            "DATA DE FUNDAC?O:",
        ),
        # 2020 onwards
        (
            "REGIAO:",
            "UF:",
            "ESTACAO:",
            "CODIGO (WMO):",
            "LATITUDE:",
            "LONGITUDE:",
            "ALTITUDE:",
            "DATA DE FUNDACAO:",
        ),
    }
)

# --- Column header and hourly rows ---

# Bronze name of each column, in file order. "Hora anterior" columns are extremes
# over the previous hour.
OBSERVATION_COLUMNS = (
    "data",
    "hora_utc",
    "precipitacao_total",
    "pressao_estacao",
    "pressao_max_hora_anterior",
    "pressao_min_hora_anterior",
    "radiacao_global",
    "temperatura_ar",
    "temperatura_orvalho",
    "temperatura_max_hora_anterior",
    "temperatura_min_hora_anterior",
    "temperatura_orvalho_max_hora_anterior",
    "temperatura_orvalho_min_hora_anterior",
    "umidade_relativa_max_hora_anterior",
    "umidade_relativa_min_hora_anterior",
    "umidade_relativa",
    "vento_direcao",
    "vento_rajada_max",
    "vento_velocidade",
)
# Every line ends with the separator, which reads as one more, empty, field.
TRAILING_FIELD = "_trailing"

# Each column header exactly as the line appears in the file, trailing ";" included.
COLUMN_HEADER_SPELLINGS = frozenset(
    {
        # 2009-2018
        "DATA (YYYY-MM-DD);"
        "HORA (UTC);"
        "PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
        "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
        "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB);"
        "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB);"
        "RADIACAO GLOBAL (KJ/m²);"
        "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);"
        "TEMPERATURA DO PONTO DE ORVALHO (°C);"
        "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C);"
        "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%);"
        "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%);"
        "UMIDADE RELATIVA DO AR, HORARIA (%);"
        "VENTO, DIREÇÃO HORARIA (gr) (° (gr));"
        "VENTO, RAJADA MAXIMA (m/s);"
        "VENTO, VELOCIDADE HORARIA (m/s);",
        # 2019: date and hour renamed
        "Data;"
        "Hora UTC;"
        "PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
        "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
        "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB);"
        "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB);"
        "RADIACAO GLOBAL (KJ/m²);"
        "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);"
        "TEMPERATURA DO PONTO DE ORVALHO (°C);"
        "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C);"
        "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%);"
        "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%);"
        "UMIDADE RELATIVA DO AR, HORARIA (%);"
        "VENTO, DIREÇÃO HORARIA (gr) (° (gr));"
        "VENTO, RAJADA MAXIMA (m/s);"
        "VENTO, VELOCIDADE HORARIA (m/s);",
        # 2020 onwards: radiation unit written "Kj"
        "Data;"
        "Hora UTC;"
        "PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
        "PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
        "PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB);"
        "PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB);"
        "RADIACAO GLOBAL (Kj/m²);"
        "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);"
        "TEMPERATURA DO PONTO DE ORVALHO (°C);"
        "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C);"
        "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C);"
        "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%);"
        "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%);"
        "UMIDADE RELATIVA DO AR, HORARIA (%);"
        "VENTO, DIREÇÃO HORARIA (gr) (° (gr));"
        "VENTO, RAJADA MAXIMA (m/s);"
        "VENTO, VELOCIDADE HORARIA (m/s);",
    }
)

# --- Station table ---

STATION_COLUMNS = (
    "arquivo",  # CSV name inside the archive
    *STATION_FIELDS,
    "periodo_inicio",  # period the file covers, from its name (dd-mm-yyyy)
    "periodo_fim",
)
