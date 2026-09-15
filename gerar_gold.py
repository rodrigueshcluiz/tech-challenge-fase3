#!/usr/bin/env python3
"""Gera a camada Gold em Parquet a partir das fontes oficiais do INEP.

Orquestra Bronze -> Silver -> Quality Gate -> Gold e grava os marts em
`data/gold`, com o relatório de verificação em `reports`. Nenhum Parquet é
gravado se alguma checagem bloqueante falhar.

Uso:
    python gerar_gold.py [--raw DIR] [--external DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import pandas as pd

from src.config import (
    ARQUIVO_INSE, DIM_MUNICIPIO, DIM_UF, DIR_EXTERNAL, DIR_GOLD, DIR_RAW,
    DIR_REPORTS, MARTS, MICRODADOS, PUBLICACOES_META, TAXAS_RENDIMENTO,
)
from src.evaluation.validacao import diagnosticos, validar_gold
from src.preprocessing.aluno_features import construir_aluno_features
from src.preprocessing.bronze import ler_dimensoes, ler_fatos, ler_metas, processar_alunos
from src.preprocessing.enriquecimento import ler_inse, ler_taxas_rendimento
from src.preprocessing.gold import construir_gold, escrever
from src.preprocessing.quality_gate import quality_gate
from src.preprocessing.silver import compor_escopos, construir_silver
from src.report import Relatorio


def conferir_fontes(raw: Path, external: Path) -> list[str]:
    esperados = ([(raw, a) for a in MICRODADOS.values()]
                 + [(raw, a) for grupo in PUBLICACOES_META.values() for a in grupo.values()]
                 + [(raw, ARQUIVO_INSE)] + [(raw, a) for a in TAXAS_RENDIMENTO.values()]
                 + [(external, DIM_UF), (external, DIM_MUNICIPIO)])
    return [str(d / a) for d, a in esperados if not (d / a).exists()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera a camada Gold em Parquet a partir das fontes oficiais do INEP.")
    parser.add_argument("--raw", type=Path, default=DIR_RAW,
                        help="microdados e planilhas de metas do INEP")
    parser.add_argument("--external", type=Path, default=DIR_EXTERNAL,
                        help="dimensões territoriais do IBGE")
    parser.add_argument("--out", type=Path, default=DIR_GOLD)
    parser.add_argument("--reports", type=Path, default=DIR_REPORTS)
    args = parser.parse_args()

    raw, external, out, reports = (p.expanduser().resolve()
                                   for p in (args.raw, args.external, args.out, args.reports))
    faltando = conferir_fontes(raw, external)
    if faltando:
        print("ERRO: fontes ausentes — veja data/raw/README.md para baixá-las:",
              file=sys.stderr)
        for f in faltando:
            print(f"  - {f}", file=sys.stderr)
        return 2

    run_id = str(uuid.uuid4())
    processed_at = pd.Timestamp.now(tz="UTC").floor("us")
    rel = Relatorio()
    print("Tech Challenge — Fase 3 · camada Gold a partir das fontes oficiais do INEP")
    print(f"run_id: {run_id}\nfontes: {raw}\nsaída: {out}")

    try:
        rel.etapa("BRONZE — ingestão das fontes oficiais")
        meta_uf, meta_mun, meta_br, nivel = ler_metas(raw, rel)
        fatos_uf, fatos_mun = ler_fatos(raw, rel)
        dim_uf, dim_mun = ler_dimensoes(external, rel)
        alunos_por_dep, alunos_por_faixa = processar_alunos(raw, rel)
        rel.etapa("ENRIQUECIMENTO — INSE e taxas de rendimento por município")
        inse = ler_inse(raw, rel)
        taxas = ler_taxas_rendimento(raw, rel)

        silver = construir_silver(fatos_uf, fatos_mun, dim_uf, dim_mun, meta_uf, meta_mun,
                                  meta_br, nivel, compor_escopos(alunos_por_dep,
                                                                 ["ano", "sigla_uf"]),
                                  rel, processed_at)
        aprovados = quality_gate(silver, dim_uf, dim_mun, rel)
        gold = construir_gold(aprovados, alunos_por_faixa, rel)
        gold["aluno_features"] = construir_aluno_features(raw, gold, dim_uf, dim_mun,
                                                          inse, taxas, rel)
        validar_gold(gold, aprovados, alunos_por_dep, raw, rel)
        diagnosticos(gold, rel)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"\nERRO na ingestão: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    reports.mkdir(parents=True, exist_ok=True)
    if rel.falhas:
        print(f"\n{'=' * 78}\nPIPELINE REPROVADO — nada foi gravado. Falhas:")
        for f in rel.falhas:
            print(f"  - {f}")
        (reports / "RELATORIO_VALIDACAO.md").write_text(rel.markdown(run_id, raw),
                                                        encoding="utf-8")
        return 1

    escrever(gold, out, reports, rel, run_id, raw)
    (reports / "RELATORIO_VALIDACAO.md").write_text(rel.markdown(run_id, raw), encoding="utf-8")
    c = rel.contagem()
    print(f"\n{'=' * 78}\nCONCLUÍDO — {len(MARTS)} marts gravados em {out}")
    print(f"{c['OK']} verificações aprovadas, {c['AVISO']} avisos, 0 falhas")
    print(f"Relatório: {reports / 'RELATORIO_VALIDACAO.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
