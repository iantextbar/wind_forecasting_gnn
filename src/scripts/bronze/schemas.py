"""Bronze schema of every raw source: each column and its bronze dtype, in order.

Schemas were surveyed from the raw files: ONS downloaded on 2026-11-20, SIGEL on
2026-11-24. Type drift between raw files is noted next to the column; ``casting.py``
converts every file to these dtypes. Units follow each source's data dictionary
(ONS PDFs, SIGEL layer metadata ``camada_<n>_metadata.json``).
"""

from __future__ import annotations

import polars as pl

Schema = dict[str, pl.DataType]

# ONS stores instants as timezone-naive nanosecond timestamps. Bronze keeps them
# naive: the timezone convention is unverified and is assigned in silver.
INSTANT = pl.Datetime("ns")
# ArcGIS dates are milliseconds since 1970 in UTC, so SIGEL dates are UTC-aware.
ARCGIS_DATE = pl.Datetime("ms", time_zone="UTC")

# --- ONS ---

FATOR_CAPACIDADE_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "nom_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_estado": pl.String,
    "cod_pontoconexao": pl.String,
    "nom_pontoconexao": pl.String,
    "nom_localizacao": pl.String,
    "val_latitudesecoletora": pl.Float64,  # degrees
    "val_longitudesecoletora": pl.Float64,  # degrees
    "val_latitudepontoconexao": pl.Float64,  # degrees
    "val_longitudepontoconexao": pl.Float64,  # degrees
    "nom_modalidadeoperacao": pl.String,
    "nom_tipousina": pl.String,  # "Eólica" and "Solar"; filtered in silver
    "nom_usina_conjunto": pl.String,
    "id_ons": pl.String,
    "ceg": pl.String,
    "din_instante": INSTANT,
    "val_geracaoprogramada": pl.Float64,  # MWmed; raw decimal string
    "val_geracaoverificada": pl.Float64,  # MWmed; raw decimal string
    "val_capacidadeinstalada": pl.Float64,  # MW; raw decimal string
    # p.u.; decimal string until 2025, Float64 from 2026.
    "val_fatorcapacidade": pl.Float64,
}

COFF_DETALHAMENTO_USINA_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_modalidadeoperacao": pl.String,
    "nom_conjuntousina": pl.String,
    "nom_usina": pl.String,
    "id_ons": pl.String,
    "ceg": pl.String,
    "din_instante": INSTANT,
    # m/s (the dictionary says "m3/s", a typo); speed only, no direction.
    "val_ventoverificado": pl.Float64,
    "flg_dadoventoinvalido": pl.Int32,
    "val_geracaoestimada": pl.Float64,  # MWmed
    "val_geracaoverificada": pl.Float64,  # MWmed
    "id_ons_conjuntousina": pl.String,
    "nom_origemvento": pl.String,
    "flg_dadoventosupervisaoinvalido": pl.Int32,
    "nom_origemgeracaoreferencia": pl.String,
    "val_geracaoreferenciafinal": pl.Float64,  # MWmed
    "flg_geracaorestrita": pl.Int32,
}

COFF_USINA_CONJUNTO_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "nom_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_estado": pl.String,
    "nom_usina": pl.String,
    "id_ons": pl.String,
    "ceg": pl.String,
    "din_instante": INSTANT,
    "val_geracao": pl.Float64,  # MWmed
    "val_geracaolimitada": pl.Float64,  # MWmed
    "val_disponibilidade": pl.Float64,  # MWmed
    "val_geracaoreferencia": pl.Float64,  # MWmed
    "val_geracaoreferenciafinal": pl.Float64,  # MWmed
    "cod_razaorestricao": pl.String,
    "cod_origemrestricao": pl.String,
    "dsc_restricao": pl.String,
    "id_pontoconexao": pl.String,
    "nom_pontoconexao": pl.String,
    "nom_agenteoperador": pl.String,
    "val_geracaonaorealizadaapurada": pl.Float64,
    "num_minutos_rel": pl.Int64,
    "num_minutos_cnf": pl.Int64,
    "num_minutos_ene": pl.Int64,
    "num_minutos_restricao": pl.Int64,
}

COFF_INTRA_SEMIHORA_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_agenteoperador": pl.String,
    "nom_usina": pl.String,
    "id_ons": pl.String,
    "din_instante": INSTANT,
    "hor_inicial": pl.Time,  # raw "HH:MM:SS"
    "hor_final": pl.Time,  # raw "HH:MM:SS"
    "num_minutosrestricao": pl.Int64,  # minutes
    "cod_razaorestricao": pl.String,
    "cod_origemrestricao": pl.String,
    "val_geracaolimitada": pl.Float64,  # MW
    "dsc_restricao": pl.String,
}

DISPONIBILIDADE_USINA_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "nom_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_estado": pl.String,
    "nom_usina": pl.String,
    "id_tipousina": pl.String,
    "nom_tipocombustivel": pl.String,
    "id_ons": pl.String,
    "ceg": pl.String,
    "din_instante": INSTANT,
    # MW. Decimal strings in 2023-01..2025-12, Float64 in 2015 and from 2026.
    "val_potenciainstalada": pl.Float64,
    "val_dispoperacional": pl.Float64,
    "val_dispsincronizada": pl.Float64,
}

GERACAO_USINA_HORARIA_SCHEMA: Schema = {
    "din_instante": INSTANT,
    "id_subsistema": pl.String,
    "nom_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_estado": pl.String,
    "cod_modalidadeoperacao": pl.String,
    "nom_tipousina": pl.String,
    "nom_tipocombustivel": pl.String,
    "nom_usina": pl.String,
    "id_ons": pl.String,
    "ceg": pl.String,
    "val_geracao": pl.Float64,  # MWmed; decimal string until 2026-04, Float64 after
}

PREVISAO_VS_PROGRAMADO_SCHEMA: Schema = {
    # Raw "YYYYMMDD" string; one file (2025-05-31) stores it as Int64 instead.
    "dat_programacao": pl.Date,
    "num_patamar": pl.Int32,  # half-hour slot of the day; Int64 in the same file
    "cod_usinapdp": pl.String,  # PDP code, not id_ons
    "nom_usinapdp": pl.String,
    "val_previsao": pl.Float64,  # MW; decimal string except in that file
    "val_programado": pl.Float64,  # MW; decimal string except in that file
}

CADASTRO_CAPACIDADE_INSTALADA_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "nom_subsistema": pl.String,
    "id_estado": pl.String,
    "nom_estado": pl.String,
    "nom_modalidadeoperacao": pl.String,
    "nom_agenteproprietario": pl.String,
    "nom_agenteoperador": pl.String,
    "nom_tipousina": pl.String,
    "nom_usina": pl.String,
    "ceg": pl.String,
    "nom_unidadegeradora": pl.String,
    "cod_equipamento": pl.String,
    # Kept as stored: fixed-width, space-padded, with placeholder values like "XXX".
    "num_unidadegeradora": pl.String,
    "nom_combustivel": pl.String,
    "dat_entradateste": pl.Date,
    "dat_entradaoperacao": pl.Date,
    "dat_desativacao": pl.Date,
    "val_potenciaefetiva": pl.Float64,  # MW
}

CADASTRO_MODALIDADE_USINA_SCHEMA: Schema = {
    "nom_usina": pl.String,
    "ceg": pl.String,
    "nom_modalidadeoperacao": pl.String,
    "val_potenciaautorizada": pl.Float64,  # MW; raw decimal string
    "sgl_centrooperacao": pl.String,
    "nom_pontoconexao": pl.String,
    "id_estado": pl.String,
    "nom_estado": pl.String,
    "sts_aneel": pl.String,
    "id_ons": pl.String,
}

CADASTRO_RELACIONAMENTO_USINA_CONJUNTO_SCHEMA: Schema = {
    "id_subsistema": pl.String,
    "nom_subsistema": pl.String,
    "estad_id": pl.String,
    "nom_estado": pl.String,
    "id_tipousina": pl.String,
    "nom_tipousina": pl.String,
    "id_conjuntousina": pl.Int32,
    "id_ons_conjunto": pl.String,
    "id_ons_usina": pl.String,
    "nom_conjunto": pl.String,
    "nom_usina": pl.String,
    "ceg": pl.String,
    # Membership validity interval; an open end (null) means still valid.
    "dat_iniciorelacionamento": pl.Date,
    "dat_fimrelacionamento": pl.Date,
}

# --- ANEEL SIGEL: columns follow each layer's own field list ---

SIGEL_AEROGERADORES_SCHEMA: Schema = {
    "POT_MW": pl.Float64,  # rated power, MW
    "ALT_TOTAL": pl.Float64,  # total height (tip), m
    "ALT_TORRE": pl.Float64,  # tower (hub) height, m
    "DIAM_ROTOR": pl.Float64,  # rotor diameter, m
    "DATA_ATUALIZACAO": ARCGIS_DATE,
    "EOL_VERSAO_ID": pl.Int32,  # farm id, links to layers 1-5
    "NOME_EOL": pl.String,
    "DEN_AEG": pl.String,  # turbine designation within the farm
    "X": pl.Float64,  # UTM easting, m, in zone FUSO_AG and datum DATUM_EMP
    "Y": pl.Float64,  # UTM northing, m
    "VERSAO": pl.String,
    "DATUM_EMP": pl.String,
    "OPERACAO": pl.String,  # mixed vocabulary: "Sim"/"Não", phase names, "1"
    "FUSO_AG": pl.String,
    "PROPRIETARIO": pl.String,
    "OBJECTID": pl.Int64,
    "UF": pl.String,
    "CEG": pl.String,  # ANEEL plant code; ONS format is derived in silver
    "ORIGEM": pl.String,
    "geometry_x": pl.Float64,  # longitude, degrees WGS84 (server reprojection)
    "geometry_y": pl.Float64,  # latitude, degrees WGS84
}

SIGEL_REGIAO_INTERFERENCIA_SCHEMA: Schema = {
    "NOME_EOL": pl.String,
    "NUM_PETALAS": pl.Int16,  # wind-rose sectors the region is drawn from
    "DATA_ATUALIZACAO": ARCGIS_DATE,
    "ID_EST": pl.String,  # measurement station behind the wind rose
    "DIRECAO_PREDO": pl.Float64,  # prevailing wind direction, degrees
    "EOL_VERSAO": pl.Float64,  # farm id (EOL_VERSAO_ID elsewhere), stored as Double
    "VERSAO": pl.String,
    # Computed by the server in the layer's native coordinates: square degrees
    # and degrees (a ~25 km2 region has an area of ~0.002).
    "SHAPE.STArea()": pl.Float64,
    "SHAPE.STLength()": pl.Float64,
    "OBJECTID": pl.Int64,
    "ORIGEM": pl.String,
    "geometry_json": pl.String,  # polygon rings, WGS84 lon/lat, as JSON text
}

SIGEL_PARQUES_SCHEMA: Schema = {
    "CODMUN": pl.Float64,  # IBGE municipality code, stored as Double
    "MUNIC1": pl.String,
    "UF1": pl.String,
    "PROC_ANEEL": pl.String,
    "ATO_LEGAL": pl.String,
    "P_OUT_KW": pl.Float64,  # granted power, kW
    "P_FISC_KW": pl.Float64,  # inspected power, kW
    "PROPRIETAR": pl.String,
    "CaminhoFoto": pl.String,
    "CaminhoContrato": pl.String,
    "DATA_ATUALIZACAO": ARCGIS_DATE,
    "EOL_VERSAO_ID": pl.Int32,
    "DRO_ID_SCG": pl.Int32,
    "LONG_GMS": pl.String,  # degrees-minutes-seconds text, inconsistent formats
    "LAT_GMS": pl.String,
    "NOMES_EOL_ANTERIOR": pl.String,
    "DRO_DATA": ARCGIS_DATE,
    "ID_LT": pl.Int32,  # transmission line id
    "ID_SE": pl.Int32,  # substation id
    "ID_EST": pl.String,  # measurement station id
    "DRO_DT_VIG": ARCGIS_DATE,
    "ID_EMPREENDIMENTO": pl.Int32,
    "LAT_DEC": pl.Float64,  # degrees; some values are far out of range (check in EDA)
    "LONG_DEC": pl.Float64,
    "QTD_AEG": pl.Int32,  # number of turbines
    "INICIO_OPER": ARCGIS_DATE,  # start of commercial operation
    "FASE": pl.String,
    "VERSAO": pl.String,
    "VALIDACAO": pl.String,
    "FUSO": pl.String,
    "DATUM_EMP": pl.String,
    "TIPO_EXP": pl.String,
    "OBJECTID": pl.Int64,
    "Nome": pl.String,
    "CEG": pl.String,
    "OBS": pl.String,
    "Cod_Leilao": pl.String,
    "geometry_x": pl.Float64,  # longitude, degrees WGS84 (server reprojection)
    "geometry_y": pl.Float64,  # latitude, degrees WGS84
}
