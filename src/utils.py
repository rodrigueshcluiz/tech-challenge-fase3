"""Funções compartilhadas pelas etapas do pipeline."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import FAIXAS, FAIXA_TOPO


def round_half_up(serie: pd.Series, casas: int) -> pd.Series:
    """Arredonda meio para longe do zero, como o `round` do Spark.

    O `round` do numpy usa arredondamento bancário e divergiria da Gold
    publicada no Databricks nos valores terminados exatamente em 5.
    """
    fator = 10 ** casas
    v = serie.astype("float64")
    return pd.Series(np.sign(v) * np.floor(np.abs(v) * fator + 0.5) / fator, index=serie.index)


def puro(valor):
    """Converte escalares e coleções do numpy em tipos Python, para impressão."""
    if isinstance(valor, dict):
        return {puro(k): puro(v) for k, v in valor.items()}
    if isinstance(valor, tuple):
        return tuple(puro(v) for v in valor)
    if isinstance(valor, (list, set)):
        return [puro(v) for v in valor]
    return valor.item() if hasattr(valor, "item") else valor


def texto_int(serie: pd.Series, ausente: str) -> pd.Series:
    """Inteiro anulável para texto, sem sufixo decimal (como o cast do Spark)."""
    return serie.astype("Int64").astype("object").map(
        lambda v: ausente if pd.isna(v) else str(int(v)))


def sha256_concat_ws(partes: list[pd.Series]) -> pd.Series:
    """Equivalente a sha2(concat_ws('|', ...), 256) do Spark."""
    junto = partes[0].astype("string").fillna("")
    for p in partes[1:]:
        junto = junto + "|" + p.astype("string").fillna("")
    return junto.map(lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest())


def faixa_label(prof: pd.Series) -> pd.Series:
    cond = [prof < corte for corte, _ in FAIXAS]
    return pd.Series(np.select(cond, [rot for _, rot in FAIXAS], default=FAIXA_TOPO),
                     index=prof.index, dtype="string")


def numero(serie: pd.Series) -> pd.Series:
    """Converte para número tolerando '> 80', '>80', '- ' e vazio."""
    return pd.to_numeric(
        serie.astype("string").str.replace(">", "", regex=False).str.strip(),
        errors="coerce")


def ler_do_zip(caminho: Path, interno: str, **kwargs) -> pd.DataFrame:
    """Lê um CSV de dentro do zip. Os microdados vêm em latin-1, separados por ';'."""
    with zipfile.ZipFile(caminho) as zf, zf.open(interno) as fh:
        return pd.read_csv(fh, sep=";", encoding="latin-1", **kwargs)


def markdown_tabela(dados, indice: str = "") -> str:
    """DataFrame ou Series como tabela markdown, sem depender do `tabulate`."""
    df = dados.to_frame() if hasattr(dados, "to_frame") and dados.ndim == 1 else dados
    cabecalho = [indice or (df.index.name or "")] + [str(c) for c in df.columns]
    def celula(v):
        if isinstance(v, float):
            return f"{v:.4f}".replace(".", ",")
        return str(v)
    linhas = ["| " + " | ".join(cabecalho) + " |",
              "|" + "|".join(["---"] + ["---:"] * len(df.columns)) + "|"]
    # `itertuples` e não `to_numpy`: num quadro de tipos mistos o numpy promove
    # tudo a float, e uma contagem de 404 municípios sairia como "404,0000".
    linhas += ["| " + " | ".join([str(t[0])] + [celula(v) for v in t[1:]]) + " |"
               for t in df.itertuples(index=True, name=None)]
    return "\n".join(linhas)
