"""Modelo treinado diretamente no grão do município.

Existe ao lado do modelo de aluno, e não no lugar dele. São perguntas
diferentes: o modelo de aluno responde *"esta criança será alfabetizada?"*, que
é o objeto do trabalho; este responde *"este município vai cumprir a meta?"*,
que é a decisão do gestor.

A diferença não é só de grão, é de função de perda. O modelo de aluno minimiza
erro por criança, e o erro municipal aparece como subproduto da média ponderada
— o que faz o ajuste ser dominado pelos municípios grandes, que concentram
alunos. Este aqui otimiza o erro por município, com cada território pesando o
mesmo, que é exatamente como o resultado é medido e como a política é decidida.

O desenho repete o do aluno onde importa: divisão temporal, todo indicador de
resultado em t-1, metas do ano corrente, e nenhuma informação do ano avaliado.
O porte entra por `mun_inse_alunos`, e não por contagem de alunos avaliados:
essa só se conhece depois da avaliação.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from src.config import REDE_META_MUNICIPIO, REDE_META_UF
from src.preprocessing.enriquecimento import ler_inse, ler_taxas_rendimento
from src.report import Relatorio

SEMENTE = 42

NUMERICAS = [
    "mun_taxa_rede_t1", "mun_taxa_publica_t1", "mun_media_lp_t1", "mun_nivel_t1",
    "mun_meta_ano", "uf_taxa_publica_t1", "uf_meta_ano",
    "mun_inse_media", "mun_inse_pct_vulneravel", "mun_inse_alunos",
    "mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1", "mun_reprovacao_2ano_t1",
    "mun_abandono_iniciais_t1", "latitude", "longitude",
]
CATEGORICAS = ["sigla_uf", "regiao", "capital"]
FEATURES = NUMERICAS + CATEGORICAS

COLUNAS_INSE = ["mun_inse_media", "mun_inse_pct_vulneravel", "mun_inse_alunos"]

# Escolhidos por validação cruzada de 5 folds agrupada por UF, **dentro de 2024**,
# entre sete configurações. O agrupamento por UF é o análogo do GroupKFold por
# escola no grão do aluno: municípios do mesmo estado dividem política, calendário
# e choques, e separá-los evita que a validação premie quem decora o estado.
#
# A disciplina custou desempenho e valeu a pena registrar: a configuração que eu
# havia escolhido a olho dava 9,85 p.p. de erro em 2025, contra 9,97 p.p. desta.
# A diferença é o viés de escolher configuração olhando o conjunto de teste.
PADRAO = dict(n_estimators=500, min_samples_leaf=3, max_features="sqrt")


def _inse_municipal(raw: Path, rel: Relatorio) -> pd.DataFrame:
    """INSE da rede municipal, com a rede pública como reserva."""
    bruto = ler_inse(raw, rel)
    municipal = bruto[bruto.rede == REDE_META_MUNICIPIO].drop(columns="rede")
    reserva = (bruto[bruto.rede == REDE_META_UF].drop(columns="rede")
               .rename(columns={c: c + "_pub" for c in COLUNAS_INSE}))
    d = municipal.merge(reserva, on="id_municipio", how="outer")
    for c in COLUNAS_INSE:
        d[c] = d[c].where(d[c].notna(), d[c + "_pub"])
    return d[["id_municipio"] + COLUNAS_INSE]


def montar_quadro(gold: dict[str, pd.DataFrame], raw: Path, ano: int,
                  rel: Relatorio) -> pd.DataFrame:
    """Uma linha por município da rede municipal, com contexto de t-1.

    Traz a coluna `alvo` quando o ano já foi avaliado; num ano futuro ela vem
    inteiramente nula, e quem chamar deve ignorá-la.
    """
    anterior = ano - 1
    ind, resumo = gold["indicador_municipio"], gold["resumo_uf"]

    # A espinha do quadro é o próprio ano quando ele existe; num ano futuro, são
    # os municípios avaliados em t-1, que é quem tem contexto para ser projetado.
    avaliado = ind[(ind.ano == ano) & (ind.rede == REDE_META_MUNICIPIO)]
    espinha = avaliado if len(avaliado) else ind[(ind.ano == anterior)
                                                 & (ind.rede == REDE_META_MUNICIPIO)]
    base = (espinha[["id_municipio", "sigla_uf", "regiao", "capital", "latitude",
                     "longitude", "taxa_alfabetizacao"]]
            .rename(columns={"taxa_alfabetizacao": "alvo"})
            .assign(ano=ano))
    if not len(avaliado):
        base["alvo"] = np.nan

    rede_t1 = (ind[(ind.ano == anterior) & (ind.rede == REDE_META_MUNICIPIO)]
               [["id_municipio", "taxa_alfabetizacao", "media_portugues"]]
               .rename(columns={"taxa_alfabetizacao": "mun_taxa_rede_t1",
                                "media_portugues": "mun_media_lp_t1"}))
    publica_t1 = (ind[(ind.ano == anterior) & (ind.rede == REDE_META_UF)]
                  [["id_municipio", "taxa_alfabetizacao", "nivel_alfabetizacao"]]
                  .rename(columns={"taxa_alfabetizacao": "mun_taxa_publica_t1",
                                   "nivel_alfabetizacao": "mun_nivel_t1"}))
    uf_t1 = (resumo[(resumo.ano == anterior) & (resumo.rede == REDE_META_UF)]
             [["sigla_uf", "taxa_alfabetizacao"]]
             .rename(columns={"taxa_alfabetizacao": "uf_taxa_publica_t1"}))
    meta_mun = (gold["metas_municipio"].query("ano == @ano")
                [["id_municipio", "meta_taxa"]]
                .rename(columns={"meta_taxa": "mun_meta_ano"}))
    meta_uf = (gold["metas_uf"].query("ano == @ano")[["sigla_uf", "meta_taxa"]]
               .rename(columns={"meta_taxa": "uf_meta_ano"}))
    taxas = ler_taxas_rendimento(raw, rel)

    d = (base.merge(rede_t1, on="id_municipio", how="left")
         .merge(publica_t1, on="id_municipio", how="left")
         .merge(uf_t1, on="sigla_uf", how="left")
         .merge(meta_mun, on="id_municipio", how="left")
         .merge(meta_uf, on="sigla_uf", how="left")
         .merge(_inse_municipal(raw, rel), on="id_municipio", how="left")
         .merge(taxas[(taxas.ano == ano) & (taxas.rede == REDE_META_MUNICIPIO)]
                .drop(columns=["ano", "rede"]), on="id_municipio", how="left"))

    # float64 em tudo: o Int64 do pandas carrega pd.NA, que o sklearn recusa.
    for c in NUMERICAS:
        d[c] = pd.to_numeric(d.get(c), errors="coerce").astype("float64")
    for c in CATEGORICAS:
        d[c] = d[c].astype("string").fillna("desconhecido")

    _conferir(d, ind, ano, anterior, rel)
    return d


def _conferir(d: pd.DataFrame, ind: pd.DataFrame, ano: int, anterior: int,
              rel: Relatorio) -> None:
    """A mesma contraprova do quadro de aluno: o contexto tem de ser de t-1."""
    rel.check(f"quadro municipal {ano} — um registro por município",
              not d.id_municipio.duplicated().any(),
              f"{len(d):,} municípios")

    esperado = (ind[(ind.ano == anterior) & (ind.rede == REDE_META_MUNICIPIO)]
                .set_index("id_municipio").taxa_alfabetizacao)
    conf = d[d.mun_taxa_rede_t1.notna()].head(2000)
    bate = np.allclose(conf.mun_taxa_rede_t1,
                       conf.id_municipio.map(esperado).astype("float64"),
                       equal_nan=True)
    rel.check(f"quadro municipal {ano} — o contexto é o do ano anterior", bool(bate),
              f"{len(conf):,} municípios conferidos contra o indicador de {anterior}")

    corrente = (ind[(ind.ano == ano) & (ind.rede == REDE_META_MUNICIPIO)]
                .set_index("id_municipio").taxa_alfabetizacao)
    if len(corrente):
        atual = conf.id_municipio.map(corrente).astype("float64")
        iguais = int(np.isclose(conf.mun_taxa_rede_t1, atual, equal_nan=False).sum())
        rel.check(f"quadro municipal {ano} — o contexto não é o do ano corrente",
                  iguais < max(1, int(0.02 * len(conf))),
                  f"{iguais:,} de {len(conf):,} coincidem (possível quando a taxa "
                  f"não mudou)")


def floresta(**parametros) -> Pipeline:
    """Floresta de regressão sobre o quadro municipal.

    Regressão e não classificação: o alvo é a taxa do município, contínua. A
    decisão binária (cumpre ou não a meta) sai depois, comparando a taxa prevista
    com a meta — o mesmo caminho que a agregação segue.
    """
    config = dict(PADRAO, random_state=SEMENTE, n_jobs=-1)
    config.update(parametros)
    preparo = ColumnTransformer([
        ("numericas", SimpleImputer(strategy="median"), NUMERICAS),
        ("categoricas", OrdinalEncoder(handle_unknown="use_encoded_value",
                                       unknown_value=-1, encoded_missing_value=-1),
         CATEGORICAS),
    ])
    return Pipeline([("preparo", preparo), ("modelo", RandomForestRegressor(**config))])


def treinar(quadros: list[pd.DataFrame], **parametros) -> Pipeline:
    """Ajusta com um ou mais anos de quadro municipal, descartando linhas sem alvo."""
    d = pd.concat(quadros, ignore_index=True)
    d = d.dropna(subset=["alvo", "mun_taxa_rede_t1", "mun_meta_ano"])
    modelo = floresta(**parametros)
    modelo.fit(d[FEATURES], d.alvo)
    return modelo


def prever(modelo: Pipeline, quadro: pd.DataFrame) -> pd.Series:
    """Taxa prevista por município, presa ao intervalo válido."""
    return pd.Series(np.clip(modelo.predict(quadro[FEATURES]), 0.0, 1.0),
                     index=quadro.index, name="taxa_prevista_municipal")
