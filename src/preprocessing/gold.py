"""Gold — os marts analíticos, um grão por mart.

Dividir `meta_vs_resultado` e `evolucao_temporal` por nível territorial evita o
problema de um mart cujo grão varia por linha: um SUM ou AVG sem filtro somaria
UF com município e contaria o mesmo dado duas vezes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config import MARTS, REDE_MAP, REDE_META_MUNICIPIO, REDE_META_UF
from src.preprocessing.silver import compor_escopos
from src.report import Relatorio
from src.utils import round_half_up

COLUNAS_UF = ["ano", "sigla_uf", "nome_uf", "regiao"]
COLUNAS_MUN = ["id_municipio", "nome_municipio", "capital", "latitude", "longitude"]
COLUNAS_REDE = ["rede", "rede_label", "fonte_dados"]


def construir_gold(aprovados: pd.DataFrame, faixas: pd.DataFrame,
                   rel: Relatorio) -> dict[str, pd.DataFrame]:
    rel.etapa("GOLD — construção dos marts (um grão por mart)")
    gold: dict[str, pd.DataFrame] = {}
    por_grao = {g: aprovados[aprovados.grao == g] for g in ("uf", "municipio")}

    # --- 1. indicador por município ----------------------------------------
    chave = COLUNAS_UF + COLUNAS_MUN + ["nivel_alfabetizacao"] + COLUNAS_REDE
    gold["indicador_municipio"] = (
        por_grao["municipio"].groupby(chave, dropna=False, as_index=False)
        .agg(taxa_alfabetizacao=("taxa_alfabetizacao", "mean"),
             media_portugues=("media_portugues", "mean"),
             updated_at=("processed_at", "max"))
        .sort_values(["ano", "sigla_uf", "id_municipio", "rede"]).reset_index(drop=True))

    # --- 2. resumo por UF ---------------------------------------------------
    resumo = (por_grao["uf"].groupby(COLUNAS_UF + COLUNAS_REDE, dropna=False, as_index=False)
              .agg(taxa_alfabetizacao=("taxa_alfabetizacao", "mean"),
                   media_portugues=("media_portugues", "mean"),
                   alunos_taxa_ponderada=("alunos_taxa_ponderada", "mean"),
                   alunos_proficiencia_media=("alunos_proficiencia_media", "mean"),
                   alunos_amostra=("alunos_amostra", "max"),
                   updated_at=("processed_at", "max")))
    # Cobertura: municípios da UF com medição. Métrica de alcance do pipeline,
    # não entra no cálculo da taxa.
    cobertura = (por_grao["municipio"]
                 .groupby(["ano", "sigla_uf", "rede"], dropna=False, as_index=False)
                 .agg(municipios_cobertos=("id_municipio", "nunique")))
    resumo = resumo.merge(cobertura, on=["ano", "sigla_uf", "rede"], how="left")
    resumo["municipios_cobertos"] = resumo.municipios_cobertos.fillna(0).astype("Int64")
    gold["resumo_uf"] = resumo.sort_values(["ano", "sigla_uf", "rede"]).reset_index(drop=True)

    # --- 3 e 4. meta versus resultado, um mart por nível territorial -------
    def meta_mart(grao: str, rede_escopo: int, ordem: list[str]) -> pd.DataFrame:
        extra = COLUNAS_MUN + ["nivel_alfabetizacao"] if grao == "municipio" else []
        cols = COLUNAS_UF + extra + COLUNAS_REDE
        d = (por_grao[grao][por_grao[grao].rede == rede_escopo]
             .groupby(cols, dropna=False, as_index=False)
             .agg(taxa_alfabetizacao=("taxa_alfabetizacao", "mean"),
                  meta_taxa=("meta_taxa", "mean"),
                  meta_brasil=("meta_brasil", "mean"),
                  meta_limiar=("meta_limiar", "max"),
                  meta_publicacao=("meta_publicacao", "max"),
                  updated_at=("processed_at", "max")))
        tem = d.meta_taxa.notna()
        d["meta_origem"] = pd.Series(
            np.where(tem, "inep_compromisso_nacional", pd.NA), index=d.index, dtype="string")
        d["meta_escopo"] = pd.Series(
            np.where(tem, "rede_publica" if grao == "uf" else "rede_municipal", pd.NA),
            index=d.index, dtype="string")
        d["gap_meta"] = round_half_up(d.taxa_alfabetizacao - d.meta_taxa, 4)
        d["atingiu_meta"] = (d.taxa_alfabetizacao >= d.meta_taxa).astype("boolean")
        d.loc[~tem, "atingiu_meta"] = pd.NA
        d["atingiu_meta_brasil"] = (d.taxa_alfabetizacao >= d.meta_brasil).astype("boolean")
        d.loc[d.meta_brasil.isna(), "atingiu_meta_brasil"] = pd.NA
        return d.sort_values(ordem).reset_index(drop=True)

    gold["meta_vs_resultado_uf"] = meta_mart("uf", REDE_META_UF, ["ano", "sigla_uf"])
    gold["meta_vs_resultado_municipio"] = meta_mart(
        "municipio", REDE_META_MUNICIPIO, ["ano", "sigla_uf", "id_municipio"])

    # --- 5 e 6. evolução temporal, um mart por nível territorial -----------
    def evolucao(grao: str) -> pd.DataFrame:
        territorio = ["id_municipio"] if grao == "municipio" else ["sigla_uf"]
        extra = ["id_municipio", "nome_municipio"] if grao == "municipio" else []
        d = (por_grao[grao].groupby(COLUNAS_UF + extra + COLUNAS_REDE,
                                    dropna=False, as_index=False)
             .agg(taxa_alfabetizacao=("taxa_alfabetizacao", "mean"),
                  updated_at=("processed_at", "max")))
        particao = territorio + ["rede"]
        d = d.sort_values(particao + ["ano"], kind="stable").reset_index(drop=True)
        g = d.groupby(particao, dropna=False, sort=False)
        d["taxa_ano_anterior"] = g.taxa_alfabetizacao.shift(1)
        d["ano_anterior"] = g.ano.shift(1).astype("Int64")
        d["variacao_absoluta"] = round_half_up(d.taxa_alfabetizacao - d.taxa_ano_anterior, 4)
        d["variacao_relativa"] = round_half_up(
            (d.taxa_alfabetizacao - d.taxa_ano_anterior) / d.taxa_ano_anterior, 4
        ).where(d.taxa_ano_anterior > 0)
        d["tendencia"] = pd.Series(
            np.select([d.variacao_absoluta > 0, d.variacao_absoluta < 0,
                       d.variacao_absoluta == 0], ["alta", "queda", "estavel"], default=None),
            index=d.index, dtype="string")
        return d.sort_values(["ano"] + particao).reset_index(drop=True)

    gold["evolucao_uf"] = evolucao("uf")
    gold["evolucao_municipio"] = evolucao("municipio")

    # --- 7. distribuição de proficiência (microdados reais) ----------------
    d7 = compor_escopos(faixas, ["ano", "sigla_uf", "faixa_pontos", "faixa_label"]).rename(
        columns={"alunos": "alunos_avaliados", "peso": "alunos_estimados",
                 "alunos_alfab": "alunos_alfabetizados"})
    d7["rede_label"] = d7.rede.map(REDE_MAP).astype("string")
    d7["proficiencia_media"] = d7.proficiencia_ponderada
    d7["fonte_dados"] = "oficial_inep"
    for c in ("alunos_avaliados", "alunos_alfabetizados", "faixa_pontos"):
        d7[c] = d7[c].astype("Int64")
    gold["distribuicao_proficiencia"] = (
        d7[["ano", "sigla_uf", "rede", "rede_label", "faixa_pontos", "faixa_label",
            "fonte_dados", "alunos_avaliados", "alunos_alfabetizados", "alunos_estimados",
            "proficiencia_media"]]
        .sort_values(["ano", "sigla_uf", "rede", "faixa_pontos", "faixa_label"])
        .reset_index(drop=True))

    for nome, df in gold.items():
        rel.info(f"gold.{nome}: {len(df):,} linhas, {len(df.columns)} colunas")
    return gold


def escrever(gold: dict[str, pd.DataFrame], destino: Path, reports: Path,
             rel: Relatorio, run_id: str, fontes: Path) -> None:
    rel.etapa("ESCRITA — materialização dos Parquet")
    destino.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    manifesto = {"run_id": run_id, "gerado_em": datetime.now(timezone.utc).isoformat(),
                 "fontes": str(fontes), "tabelas": {}}
    for nome in MARTS:
        df = gold[nome]
        arquivo = destino / f"{nome}.parquet"
        tabela = pa.Table.from_pandas(df, preserve_index=False)
        # O pandas 3 serializa texto como large_string (offsets de 64 bits); nem
        # todo consumidor lê esse tipo, e string comum basta aqui.
        tabela = tabela.cast(pa.schema([
            c.with_type(pa.string()) if c.type == pa.large_string() else c
            for c in tabela.schema]))
        pq.write_table(tabela, arquivo, compression="snappy")
        rel.check(f"{nome}.parquet relido íntegro", len(pd.read_parquet(arquivo)) == len(df),
                  f"{len(df):,} linhas, {arquivo.stat().st_size / 1024:.1f} KB")
        manifesto["tabelas"][nome] = {
            "arquivo": arquivo.name, "linhas": int(len(df)),
            "colunas": {c: str(t) for c, t in df.dtypes.items()},
            "bytes": arquivo.stat().st_size,
            "sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest()}
    (reports / "manifest.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
