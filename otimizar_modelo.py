#!/usr/bin/env python3
"""Busca hiperparâmetros por validação cruzada agrupada, sem tocar no ano de teste.

A busca inteira acontece dentro de 2024, com `GroupKFold` por escola. Só depois de
escolhida a configuração é que 2025 entra — uma vez, para medir. Se a seleção
olhasse o teste, o AUC reportado mediria o quanto tentamos, não o quanto o modelo
generaliza.

O resultado que este script pode produzir inclui **"o ajuste não ajudou"**, e isso
é informação: com três algoritmos convergindo na mesma faixa, mostrar que varrer
o espaço de hiperparâmetros não move o número é evidência de que o teto é dos
dados. A configuração só é adotada se ganhar mais que o desvio entre folds.

    python otimizar_modelo.py [--amostra N] [--candidatos N] [--folds N]
                              [--modelos floresta boosting logistica]

Escreve `reports/OTIMIZACAO.md` e a figura em `images/`.
"""
from __future__ import annotations

import argparse
import sys
import time

import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_score

from src.config import DIR_REPORTS, RAIZ
from src.utils import markdown_tabela
from src.evaluation.metricas import avaliar, tabela as tabela_metricas
from src.modeling.dados import ANO_TESTE, ANO_TREINO, carregar, features_utilizaveis
from src.modeling.otimizacao import ESPACOS, adotar, buscar, resumir
from src.modeling.pipeline import MODELOS, SEMENTE
from src.visualization.estilo import (
    SERIE, TINTA, TINTA_2, TINTA_3, aplicar_estilo, milhar, num, salvar, titular,
)

import matplotlib.pyplot as plt

DIR_IMAGENS = RAIZ / "images"


def _linha_do_espaco(nome: str) -> str:
    return " · ".join(f"`{c.removeprefix('modelo__')}` {v}"
                      for c, v in ESPACOS[nome].items())


def main() -> int:
    parser = argparse.ArgumentParser(description="Busca de hiperparâmetros.")
    parser.add_argument("--amostra", type=int, default=None,
                        help="limita as linhas por ano (amostragem por escola)")
    parser.add_argument("--candidatos", type=int, default=15,
                        help="configurações sorteadas por modelo")
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--modelos", nargs="+", default=sorted(MODELOS),
                        choices=sorted(MODELOS))
    args = parser.parse_args()

    aplicar_estilo()
    print(f"Carregando aluno_features"
          f"{f' (amostra de {args.amostra:,}/ano)' if args.amostra else ''}")
    treino, teste = carregar(amostra=args.amostra, semente=SEMENTE)
    numericas, categoricas, _ = features_utilizaveis(treino)
    print(f"  treino {ANO_TREINO}: {len(treino):,} alunos, "
          f"{treino.grupo.nunique():,} escolas")
    print(f"  busca: {args.candidatos} candidatos × {args.folds} folds por modelo, "
          f"agrupados por escola, dentro de {ANO_TREINO}")

    buscas, resultados, adotadas = {}, [], {}
    for nome in args.modelos:
        # O padrão precisa ser medido no mesmo protocolo, senão a comparação
        # confunde ganho de ajuste com diferença de validação.
        print(f"\n{nome}")
        inicio = time.perf_counter()
        notas = cross_val_score(
            MODELOS[nome](numericas, categoricas), treino.X, treino.y,
            groups=treino.grupo, cv=GroupKFold(n_splits=args.folds),
            scoring="roc_auc", params={"modelo__sample_weight": treino.peso})
        score_padrao = float(notas.mean())
        print(f"  padrão:  AUC {score_padrao:.4f} ± {notas.std():.4f} "
              f"({time.perf_counter() - inicio:.0f}s)")

        inicio = time.perf_counter()
        busca = buscar(nome, treino, numericas, categoricas,
                       n_candidatos=args.candidatos, n_folds=args.folds,
                       semente=SEMENTE)
        resumo = resumir(nome, busca, score_padrao, time.perf_counter() - inicio)
        buscas[nome] = resumo
        print(f"  melhor:  AUC {resumo.score_melhor:.4f} ± {resumo.desvio_melhor:.4f} "
              f"({resumo.segundos:.0f}s, {resumo.n_candidatos} candidatos)")
        print(f"  config:  {resumo.melhor_config}")

        escolhida = adotar(resumo)
        adotadas[nome] = escolhida
        print(f"  adotada: {'a ajustada' if escolhida else 'o padrão — ganho dentro do ruído'}")

        # --- prova final: o ganho na CV sobrevive fora do tempo? --------------
        for rotulo, config in (("padrao", {}), ("ajustado", resumo.melhor_config)):
            m = MODELOS[nome](numericas, categoricas, **config) if config else \
                MODELOS[nome](numericas, categoricas)
            m.fit(treino.X, treino.y, modelo__sample_weight=treino.peso)
            r = avaliar(teste.y, m.predict_proba(teste.X)[:, 1], teste.peso,
                        f"{nome}_{rotulo}")
            resultados.append(r)
            print(f"    {rotulo:9s} fora do tempo: AUC {r['auc_roc']:.4f} | "
                  f"Brier {r['brier']:.4f}")

    placar = tabela_metricas(resultados)
    print("\n" + placar.to_string())

    # --- figura: ganho da busca em cada modelo, na CV e fora do tempo ---------
    nomes = list(buscas)
    fig, ax = plt.subplots(figsize=(7.6, 1.2 + 1.1 * len(nomes)))
    y = range(len(nomes))
    altura, folga = 0.34, 0.19
    cv_delta = [(buscas[n].score_melhor - buscas[n].score_padrao) * 100 for n in nomes]
    fora_delta = [
        (next(r for r in resultados if r["modelo"] == f"{n}_ajustado")["auc_roc"]
         - next(r for r in resultados if r["modelo"] == f"{n}_padrao")["auc_roc"]) * 100
        for n in nomes]
    ax.barh([i + folga for i in y], cv_delta, height=altura, color=SERIE[0],
            label=f"validação cruzada em {ANO_TREINO}")
    ax.barh([i - folga for i in y], fora_delta, height=altura, color=SERIE[1],
            label=f"fora do tempo, {ANO_TESTE}")
    for i, (a, b) in enumerate(zip(cv_delta, fora_delta)):
        for v, deslocamento in ((a, folga), (b, -folga)):
            ax.text(v + (0.03 if v >= 0 else -0.03), i + deslocamento,
                    num(v, 2, sinal=True), va="center",
                    ha="left" if v >= 0 else "right", color=TINTA, fontsize=9)
    ax.axvline(0, color=TINTA_3, linewidth=0.9)
    ax.set_yticks(list(y), nomes, fontsize=10, color=TINTA_2)
    ax.xaxis.set_visible(False)
    for lado in ("bottom", "left"):
        ax.spines[lado].set_visible(False)
    margem = max(abs(v) for v in cv_delta + fora_delta) * 1.6 or 1.0
    ax.set_xlim(-margem, margem)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, -0.22), ncol=2)
    titular(ax, "O que a busca de hiperparâmetros acrescentou",
            "Diferença de AUC contra a configuração padrão, em pontos de AUC × 100.")
    figura = salvar(fig, DIR_IMAGENS, "11_ganho_da_otimizacao")

    # --- relatório -------------------------------------------------------------
    linhas = [
        "# Otimização de hiperparâmetros", "",
        f"Busca aleatória de **{args.candidatos} configurações por modelo**, validada "
        f"com `GroupKFold` de {args.folds} folds agrupados por escola, **inteiramente "
        f"dentro de {ANO_TREINO}**. O ano de {ANO_TESTE} entra uma única vez, depois da "
        f"escolha, para medir se o ganho sobrevive fora do tempo.", "",
        f"Treino: {milhar(len(treino))} alunos em {milhar(treino.grupo.nunique())} "
        f"escolas.", "",
        "## Por que a busca não pode ver o teste", "",
        "Escolher configuração olhando o desempenho em "
        f"{ANO_TESTE} transformaria o conjunto fora do tempo em treino disfarçado: o "
        "AUC publicado passaria a medir quantas tentativas fizemos, não quanto o "
        "modelo generaliza. O agrupamento por escola é a segunda proteção — sem ele, "
        "colegas do mesmo aluno caem dos dois lados do fold e a busca escolheria a "
        "configuração que melhor decora turma, já que 14,5% da variância do alvo está "
        "entre escolas.", "",
        "## Resultado por modelo", "",
        "| modelo | AUC padrão (CV) | AUC melhor (CV) | ganho | fora do tempo | adotada |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for n in nomes:
        b = buscas[n]
        fora = next(r for r in resultados if r["modelo"] == f"{n}_ajustado")["auc_roc"]
        fora_p = next(r for r in resultados if r["modelo"] == f"{n}_padrao")["auc_roc"]
        linhas.append(
            f"| {n} | {num(b.score_padrao, 4)} | {num(b.score_melhor, 4)} "
            f"± {num(b.desvio_melhor, 4)} | {num((b.score_melhor - b.score_padrao) * 100, 3, sinal=True)} | "
            f"{num(fora_p, 4)} → {num(fora, 4)} | "
            f"{'ajustada' if adotadas[n] else 'padrão'} |")

    linhas += ["", "## Configuração vencedora de cada busca", ""]
    for n in nomes:
        linhas += [f"**{n}** — espaço: {_linha_do_espaco(n)}", "",
                   f"Melhor: `{buscas[n].melhor_config}` "
                   f"({buscas[n].n_candidatos} candidatos, {buscas[n].segundos:.0f}s)", ""]

    linhas += ["## Critério de adoção", "",
               "A configuração ajustada só substitui o padrão se ganhar **mais que o "
               "desvio entre os folds da própria busca**. Trocar por algo que empata "
               "dentro do ruído não é ajuste fino: é escolher barulho e perder a "
               "justificativa estrutural que o padrão tinha.", "",
               "## Candidatos avaliados", ""]
    for n in nomes:
        linhas += [f"### {n}", "",
                   markdown_tabela(
                       buscas[n].tabela.head(10).assign(
                           params=lambda d: d.params.map(lambda p: f"`{p}`"))
                       .rename(columns={"mean_test_score": "AUC médio",
                                        "std_test_score": "desvio",
                                        "params": "configuração"}), "posição"), ""]

    linhas += ["## Avaliação fora do tempo", "",
               markdown_tabela(placar, "modelo"), "",
               "## Figura", "", f"![ganho da otimização](../images/{figura})", ""]

    DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    (DIR_REPORTS / "OTIMIZACAO.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nrelatório: {DIR_REPORTS / 'OTIMIZACAO.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
