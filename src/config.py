"""Caminhos, domínios oficiais e constantes do pipeline.

Um único lugar para tudo que, se divergir, quebra silenciosamente o resultado.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_EXTERNAL = RAIZ / "data" / "external"
DIR_GOLD = RAIZ / "data" / "gold"
DIR_REPORTS = RAIZ / "reports"

# ---------------------------------------------------------------------------
# Domínios oficiais — Dicionário dos Microdados da AEEB, aba TS_ESTADO.
#
# ATENÇÃO: o código 5 é PÚBLICA (estadual + municipal), não privada. Privada é
# o 4. O pipeline da Fase 2 trocava os dois, o que inverteu todo filtro de rede
# no painel e nos números apresentados.
# ---------------------------------------------------------------------------
REDE_MAP = {
    0: "total",                # Federal, Estadual, Municipal e Privada
    1: "federal",
    2: "estadual",
    3: "municipal",
    4: "privada",
    5: "publica",              # Estadual e Municipal
    6: "publica_com_federal",  # Federal, Estadual e Municipal
}

# Como cada escopo se compõe a partir de TP_DEPENDENCIA dos microdados de aluno
# (1 Federal, 2 Estadual, 3 Municipal, 4 Privada).
REDE_COMPOSICAO = {
    0: {1, 2, 3, 4},
    1: {1},
    2: {2},
    3: {3},
    4: {4},
    5: {2, 3},
    6: {1, 2, 3},
}

# Regra de negócio versionada. Validada contra IN_ALFABETIZADO do INEP.
ALFABETIZACAO_CORTE = 743
ALFABETIZACAO_RULE_VERSION = "1.0"
SCHEMA_VERSION = "2.0"

COBERTURA_MIN = 0.80
ANO_META_MIN, ANO_META_MAX = 2024, 2030

# O INEP publica meta de rede pública no grão UF e de rede municipal no grão
# município — e só nesses recortes. Comparar meta de rede pública contra o
# resultado da rede estadual isolada não significa nada.
REDE_META_UF = 5
REDE_META_MUNICIPIO = 3

UFS_VALIDAS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]

# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------
MICRODADOS = {
    2023: "microdados_avaliacao_da_alfabetizacao_2023.zip",
    2024: "microdados_avaliacao_da_alfabetizacao_2024.zip",
    2025: "microdados_AEEB_2025.zip",
}

# Divulgações das metas, da mais precisa para a menos precisa. A de 2023 publica
# o float completo, a de 2024 arredonda para duas casas e a de 2025 para
# inteiro — os valores são os mesmos. A de 2025 tem a maior cobertura de
# municípios, então entra como complemento.
PUBLICACOES_META = {
    2023: {"uf": "resultados_e_metas_ufs.xlsx",
           "municipio": "resultados_e_metas_municipios.xlsx"},
    2024: {"uf": "resultados_e_metas_ufs_2024_2.xlsx",
           "municipio": "resultados_e_metas_municipios_2024.xlsx"},
    2025: {"uf": "resultados_e_metas_ufs_2025_v1.xlsx",
           "municipio": "resultados_e_metas_municipios_2025_3.xlsx"},
}
PRECEDENCIA_META = [2023, 2024, 2025]

ABA_UF = "Divulgação Alfabet UF e Brasil"
ABA_MUNICIPIO = "Divulgação Alfabet Municipio"

# Enriquecimento municipal (INEP). O INSE sai a cada dois anos junto com o SAEB;
# 2023 é a safra mais recente e entra como característica estrutural.
ARQUIVO_INSE = "INSE_2023_municipios.xlsx"
# As taxas entram defasadas em um ano: as de 2023 alimentam 2024. A safra de 2025
# não encontra aluno em `aluno_features` (não há avaliação de 2026) e existe aqui
# para compor o contexto da projeção.
TAXAS_RENDIMENTO = {2023: "tx_rend_municipios_2023.zip",
                    2024: "tx_rend_municipios_2024.zip",
                    2025: "tx_rend_municipios_2025.zip"}

DIM_UF = "uf.csv"
DIM_MUNICIPIO = "municipio.csv"

COLUNAS_ALUNO = ["NU_ANO_AVALIACAO", "SG_UF", "CO_MUNICIPIO", "ID_ALUNO", "TP_SERIE",
                 "TP_DEPENDENCIA", "ID_ESCOLA", "CO_CADERNO_LP", "VL_PESO_ALUNO_LP",
                 "VL_PROFICIENCIA_LP", "IN_ALFABETIZADO", "IN_PRESENCA_LP"]

# Distribuição oficial dos alunos pelos nove níveis de proficiência, publicada em
# TS_ESTADO e TS_MUNICIPIO. A taxa de alfabetização é um resumo dela: dois
# municípios com a mesma taxa podem ter distribuições muito diferentes, e o que
# tem massa logo abaixo do corte tem muito mais chance de cruzá-lo no ano
# seguinte. Medido: +0,029 de R² na projeção municipal (ver reports/AUDITORIA.md).
N_NIVEIS_PROFICIENCIA = 9
COLUNAS_NIVEL = {f"PC_ALUNO_NIVEL_{i}_LP": f"pc_nivel_{i}"
                 for i in range(N_NIVEIS_PROFICIENCIA)}

# Faixas do histograma de proficiência. `faixa_label` não é derivável de
# `faixa_pontos`: o corte de 743 cai dentro do bloco 725–749.
FAIXAS = [(650, "1 · Abaixo de 650"), (700, "2 · 650 a 699"),
          (743, "3 · 700 a 742"), (800, "4 · 743 a 799")]
FAIXA_TOPO = "5 · 800 ou mais"
FAIXAS_ALFABETIZADAS = [FAIXAS[3][1], FAIXA_TOPO]

MARTS = [
    "indicador_municipio",
    "resumo_uf",
    "meta_vs_resultado_uf",
    "meta_vs_resultado_municipio",
    # Trajetória completa das metas, 2024–2030. Os marts `meta_vs_resultado_*`
    # são a interseção com o resultado e por isso param no último ano avaliado;
    # projetar um ano futuro exige a meta desse ano.
    "metas_uf",
    "metas_municipio",
    "evolucao_uf",
    "evolucao_municipio",
    "distribuicao_proficiencia",
    "aluno_features",
]
