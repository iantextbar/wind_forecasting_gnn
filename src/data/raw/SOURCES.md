# Raw data sources

All raw datasets come from ONS open data (<https://dados.ons.org.br>). The files are hosted on the public S3 bucket `ons-aws-prod-opendata`. Every dataset is downloaded as **Parquet**, together with its data dictionary PDF. The files themselves are gitignored; only the folder layout is tracked.

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
