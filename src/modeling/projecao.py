"""Monta o quadro de features de um ano ainda não avaliado.

Para projetar 2026 não existe roteiro de alunos: a avaliação ainda não ocorreu.
O que existe é tudo de que as features precisam, porque **nenhuma delas descreve
a criança** — são contexto municipal e estadual de t-1 mais as metas do ano, e
2025 já fechou.

A construção reaproveita o roteiro de 2025 como molde: cada aluno avaliado em
2025 vira uma linha de 2026 com o mesmo território, a mesma escola e o mesmo
peso, e com todo o contexto trocado pelo de 2026. Isso preserva a composição do
município — distribuição de porte de escola e de pesos amostrais — que é o que
faz a média ponderada reproduzir o indicador oficial.

A suposição embutida, e que precisa ser dita: **a coorte de 2026 se parece com a
de 2025 em composição**. Se um município fechar escolas, crescer ou mudar de
rede, a projeção erra por um motivo que não é do modelo.

Nada aqui tem alvo. O quadro serve para prever, não para avaliar — a aferição do
método está no recorte 2024 → 2025, onde existe gabarito.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import REDE_META_UF
from src.modeling.dados import CATEGORICAS, CONTEXTO, FEATURES, Conjunto
from src.preprocessing.enriquecimento import ler_taxas_rendimento
from src.report import Relatorio

# Colunas de contexto que precisam ser reescritas para o ano projetado. As demais
# — território, porte, INSE — são estruturais e seguem valendo.
CONTEXTO_DEFASADO = [
    "mun_taxa_rede_t1", "mun_media_lp_t1", "mun_taxa_publica_t1", "mun_nivel_t1",
    "mun_variacao_publica_t1", "uf_taxa_publica_t1", "uf_variacao_publica_t1",
]
METAS = ["mun_meta_ano", "uf_meta_ano"]
TAXAS = ["mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1",
         "mun_reprovacao_2ano_t1", "mun_abandono_iniciais_t1"]


def _contexto_do_ano(gold: dict[str, pd.DataFrame], ano_projetado: int) -> dict:
    """Quadros de contexto endereçados ao ano projetado.

    Mesma regra de `aluno_features`: resultado vem de t-1, meta vem do ano
    corrente, porque a meta é publicada antes da avaliação.
    """
    anterior = ano_projetado - 1
    ind = gold["indicador_municipio"]
    resumo = gold["resumo_uf"]

    mun_rede = (ind[ind.ano == anterior]
                [["id_municipio", "rede", "taxa_alfabetizacao", "media_portugues"]]
                .rename(columns={"taxa_alfabetizacao": "mun_taxa_rede_t1",
                                 "media_portugues": "mun_media_lp_t1"}))
    mun_publica = (ind[(ind.ano == anterior) & (ind.rede == REDE_META_UF)]
                   [["id_municipio", "taxa_alfabetizacao", "nivel_alfabetizacao"]]
                   .rename(columns={"taxa_alfabetizacao": "mun_taxa_publica_t1",
                                    "nivel_alfabetizacao": "mun_nivel_t1"}))
    mun_variacao = (gold["evolucao_municipio"]
                    .query("ano == @anterior and rede == @REDE_META_UF")
                    [["id_municipio", "variacao_absoluta"]]
                    .rename(columns={"variacao_absoluta": "mun_variacao_publica_t1"}))
    uf_publica = (resumo[(resumo.ano == anterior) & (resumo.rede == REDE_META_UF)]
                  [["sigla_uf", "taxa_alfabetizacao"]]
                  .rename(columns={"taxa_alfabetizacao": "uf_taxa_publica_t1"}))
    uf_variacao = (gold["evolucao_uf"].query("ano == @anterior and rede == @REDE_META_UF")
                   [["sigla_uf", "variacao_absoluta"]]
                   .rename(columns={"variacao_absoluta": "uf_variacao_publica_t1"}))
    meta_mun = (gold["metas_municipio"].query("ano == @ano_projetado")
                [["id_municipio", "meta_taxa"]]
                .rename(columns={"meta_taxa": "mun_meta_ano"}))
    meta_uf = (gold["metas_uf"].query("ano == @ano_projetado")[["sigla_uf", "meta_taxa"]]
               .rename(columns={"meta_taxa": "uf_meta_ano"}))
    return {"mun_rede": mun_rede, "mun_publica": mun_publica, "mun_variacao": mun_variacao,
            "uf_publica": uf_publica, "uf_variacao": uf_variacao,
            "meta_mun": meta_mun, "meta_uf": meta_uf}


def montar_quadro(gold: dict[str, pd.DataFrame], molde: pd.DataFrame, raw: Path,
                  ano_projetado: int, rel: Relatorio) -> Conjunto:
    """Devolve um `Conjunto` sem alvo, pronto para `predict_proba`.

    `molde` é o recorte do último ano avaliado em `aluno_features`, usado como
    roteiro de alunos. O `y` vem zerado e não deve ser lido: não há gabarito.
    """
    rel.etapa(f"PROJEÇÃO — quadro de features para {ano_projetado}")
    ctx = _contexto_do_ano(gold, ano_projetado)
    d = molde.drop(columns=CONTEXTO_DEFASADO + METAS + TAXAS).copy()
    d["ano"] = ano_projetado

    d = (d.merge(ctx["mun_rede"], on=["id_municipio", "rede"], how="left")
         .merge(ctx["mun_publica"], on="id_municipio", how="left")
         .merge(ctx["mun_variacao"], on="id_municipio", how="left")
         .merge(ctx["uf_publica"], on="sigla_uf", how="left")
         .merge(ctx["uf_variacao"], on="sigla_uf", how="left")
         .merge(ctx["meta_mun"], on="id_municipio", how="left")
         .merge(ctx["meta_uf"], on="sigla_uf", how="left"))

    # As taxas de rendimento já saem endereçadas ao ano de consumo.
    taxas = ler_taxas_rendimento(raw, rel)
    d = d.merge(taxas[taxas.ano == ano_projetado].drop(columns="ano"),
                on=["id_municipio", "rede"], how="left")

    faltando = [c for c in FEATURES if c not in d.columns]
    if faltando:
        raise ValueError(f"quadro de {ano_projetado} sem as colunas {faltando}")

    _conferir(d, molde, ano_projetado, rel)

    X = d[FEATURES].copy()
    X["capital"] = X.capital.astype("string").fillna("desconhecido")
    for c in CATEGORICAS:
        X[c] = X[c].astype("string").fillna("desconhecido")
    return Conjunto(X=X, y=pd.Series(0, index=d.index, dtype="int8"),
                    peso=d.peso_amostral, grupo=d.id_escola_ano,
                    contexto=d[CONTEXTO])


def _conferir(d: pd.DataFrame, molde: pd.DataFrame, ano: int, rel: Relatorio) -> None:
    rel.check(f"projeção {ano} — mantém o roteiro do ano-molde",
              len(d) == len(molde),
              f"{len(d):,} linhas, {d.id_municipio.nunique():,} municípios")

    # A contraprova que importa: o contexto tem de ter mudado. Se um merge
    # falhasse em silêncio e as colunas viessem do molde, a projeção repetiria o
    # ano anterior e ninguém veria diferença no formato da saída.
    comparaveis = [c for c in CONTEXTO_DEFASADO + METAS
                   if molde[c].notna().any() and d[c].notna().any()]
    iguais = [c for c in comparaveis
              if d[c].fillna(-1).round(6).equals(molde[c].fillna(-1).round(6))]
    rel.check(f"projeção {ano} — o contexto foi de fato reescrito",
              not iguais, f"colunas idênticas ao molde: {iguais or 'nenhuma'}")

    ausentes = {c: f"{d[c].isna().mean():.1%}" for c in FEATURES if d[c].isna().any()}
    rel.info(f"projeção {ano} — features com valor faltante: {ausentes or 'nenhuma'} "
             f"(a imputação é do pipeline)")
    sem_meta = int(d.mun_meta_ano.isna().sum())
    rel.info(f"projeção {ano} — {sem_meta:,} linhas sem meta municipal publicada "
             f"({sem_meta / len(d):.1%})")
