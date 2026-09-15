"""Enriquecimento municipal: nível socioeconômico e taxas de rendimento escolar.

Ambas as fontes são do INEP e vêm **já agregadas por município**, o que resolve
o problema do código de escola mascarado: o `ID_ESCOLA` dos microdados é
fictício e resorteado a cada ano, então nenhum enriquecimento por escola é
possível. Por município, o join é direto.

- **INSE** (Indicador de Nível Socioeconômico): média do município por rede.
  É a variável socioeconômica que o enunciado pede. Publicado junto com o SAEB,
  a cada dois anos — a safra mais recente é 2023, e é tratada como característica
  estrutural, não como série temporal.

- **Taxas de rendimento**: aprovação, reprovação e abandono por município, rede
  e ano escolar. Entram **defasadas em um ano**, como todo indicador de
  resultado. A taxa de aprovação do 1º ano em t-1 é especialmente informativa:
  é a mesma coorte, um ano antes de fazer a prova.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from src.config import ARQUIVO_INSE, TAXAS_RENDIMENTO
from src.report import Relatorio
from src.utils import puro

ABA_INSE = "INSE_MUN_2023"
LINHA_CABECALHO_TAXAS = 8

# NO_DEPENDENCIA das taxas -> código de rede oficial (o mesmo do REDE_MAP).
DEPENDENCIA_PARA_REDE = {
    "Total": 0, "Federal": 1, "Estadual": 2, "Municipal": 3,
    "Privada": 4, "Pública": 5,
}

# Coluna da planilha -> nome da feature. Prefixo 1 aprovação, 2 reprovação,
# 3 abandono; sufixo 01/02 é o ano escolar e AI são os anos iniciais.
COLUNAS_TAXAS = {
    "1_CAT_FUN_01": "mun_aprovacao_1ano_t1",
    "1_CAT_FUN_02": "mun_aprovacao_2ano_t1",
    "2_CAT_FUN_02": "mun_reprovacao_2ano_t1",
    "3_CAT_FUN_AI": "mun_abandono_iniciais_t1",
}


def ler_inse(raw: Path, rel: Relatorio) -> pd.DataFrame:
    d = pd.read_excel(raw / ARQUIVO_INSE, sheet_name=ABA_INSE, dtype=str)
    # TP_LOCALIZACAO 0 = total (urbana e rural): queremos o município inteiro.
    d = d[d.TP_LOCALIZACAO == "0"].copy()
    saida = pd.DataFrame({
        "id_municipio": d.CO_MUNICIPIO.str.strip().str.zfill(7),
        "rede": pd.to_numeric(d.TP_TIPO_REDE, errors="coerce").astype("Int64"),
        "mun_inse_media": pd.to_numeric(d.MEDIA_INSE, errors="coerce"),
        # Níveis 1 e 2 são os estratos socioeconômicos mais baixos.
        "mun_inse_pct_vulneravel": (pd.to_numeric(d.PC_NIVEL_1, errors="coerce")
                                    + pd.to_numeric(d.PC_NIVEL_2, errors="coerce")),
        "mun_inse_alunos": pd.to_numeric(d.QTD_ALUNOS_INSE, errors="coerce").astype("Int64"),
    }).dropna(subset=["mun_inse_media"]).drop_duplicates(["id_municipio", "rede"])

    rel.check("INSE municipal carregado", len(saida) > 0,
              f"{len(saida):,} pares município-rede | "
              f"{saida.id_municipio.nunique():,} municípios | "
              f"média {saida.mun_inse_media.mean():.2f}")
    rel.check("INSE dentro da escala esperada",
              bool(saida.mun_inse_media.between(0, 100).all()),
              f"min={saida.mun_inse_media.min():.2f} max={saida.mun_inse_media.max():.2f}")
    return saida


def ler_taxas_rendimento(raw: Path, rel: Relatorio) -> pd.DataFrame:
    partes = []
    for ano, arquivo in TAXAS_RENDIMENTO.items():
        with zipfile.ZipFile(raw / arquivo) as zf:
            interno = [n for n in zf.namelist() if n.endswith(".xlsx")][0]
            bruto = zf.read(interno)
        d = pd.read_excel(io.BytesIO(bruto), sheet_name=0,
                          header=LINHA_CABECALHO_TAXAS, dtype=str)
        # NO_CATEGORIA 'Total' = urbana e rural juntas.
        d = d[(d.NO_CATEGORIA == "Total") & d.CO_MUNICIPIO.notna()].copy()
        saida = pd.DataFrame({
            # Deslocado para o ano em que será consumido: a taxa de 2023 é
            # contexto do aluno avaliado em 2024.
            "ano": ano + 1,
            "id_municipio": d.CO_MUNICIPIO.str.strip().str.zfill(7),
            "rede": d.NO_DEPENDENCIA.str.strip().map(DEPENDENCIA_PARA_REDE).astype("Int64"),
        })
        for origem, destino in COLUNAS_TAXAS.items():
            saida[destino] = pd.to_numeric(d[origem], errors="coerce")
        partes.append(saida.dropna(subset=["rede"]).drop_duplicates(
            ["ano", "id_municipio", "rede"]))
        rel.info(f"taxas de rendimento de {ano}: {len(partes[-1]):,} pares "
                 f"município-rede (contexto de {ano + 1})")

    taxas = pd.concat(partes, ignore_index=True)
    rel.check("taxas de rendimento carregadas", len(taxas) > 0,
              f"{len(taxas):,} linhas | anos de consumo {puro(sorted(taxas.ano.unique()))}")
    faixa_ok = all(taxas[c].dropna().between(0, 100).all() for c in COLUNAS_TAXAS.values())
    rel.check("taxas de rendimento em escala 0–100 por cento", faixa_ok,
              "aprovação, reprovação e abandono")
    return taxas
