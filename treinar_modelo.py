#!/usr/bin/env python3
"""Treina e avalia os modelos de predição de alfabetização.

Divisão temporal: treina em 2024, testa em 2025. Dentro do treino, validação
cruzada agrupada por escola. Tudo ponderado pelo peso amostral.

    python treinar_modelo.py [--amostra N] [--sem-shap]

Escreve o relatório em `reports/MODELAGEM.md` e as figuras em `images/`.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.inspection import permutation_importance

from src.config import DIR_REPORTS, RAIZ
from src.utils import markdown_tabela
from src.evaluation.metricas import (
    avaliar, baseline_persistencia, baseline_taxa_base, ganho_sobre, tabela,
)
from src.modeling.dados import ANO_TESTE, ANO_TREINO, carregar, features_utilizaveis
from src.modeling.pipeline import MODELOS, SEMENTE, nomes_das_features
from src.visualization.estilo import (
    SERIE, TINTA, TINTA_3, aplicar_estilo, milhar, num, salvar, titular,
)

import matplotlib.pyplot as plt

DIR_IMAGENS = RAIZ / "images"
N_FOLDS = 3
N_PERMUTACAO = 40_000   # subconjunto para a importância por permutação
N_SHAP = 4_000          # subconjunto para o SHAP


def cronometrar(rotulo, funcao, *args, **kwargs):
    inicio = time.perf_counter()
    resultado = funcao(*args, **kwargs)
    print(f"  {rotulo}: {time.perf_counter() - inicio:.1f}s", flush=True)
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description="Treina os modelos de alfabetização.")
    parser.add_argument("--amostra", type=int, default=None,
                        help="limita as linhas por ano (amostragem por escola)")
    parser.add_argument("--sem-shap", action="store_true")
    args = parser.parse_args()

    aplicar_estilo()
    print(f"Carregando aluno_features{f' (amostra de {args.amostra:,}/ano)' if args.amostra else ''}")
    treino, teste = carregar(amostra=args.amostra, semente=SEMENTE)
    print(f"  treino {ANO_TREINO}: {len(treino):,} alunos, "
          f"{treino.grupo.nunique():,} escolas")
    print(f"  teste  {ANO_TESTE}: {len(teste):,} alunos, {teste.grupo.nunique():,} escolas")

    numericas, categoricas, descartadas = features_utilizaveis(treino)
    usadas = numericas + categoricas
    if descartadas:
        print(f"  descartadas (100% nulas em {ANO_TREINO}): {descartadas}")
    print(f"  features usadas: {len(usadas)}")

    resultados, linhas_extra = [], []
    if descartadas:
        linhas_extra.append(
            f"**Features descartadas:** `{'`, `'.join(descartadas)}` — inteiramente nulas "
            f"em {ANO_TREINO}, porque a variação em t-1 exige t-2. Sob divisão temporal elas "
            f"estariam presentes só no teste, e o modelo nunca teria visto um valor delas.")

    # --- baselines ---------------------------------------------------------
    print("\nBaselines")
    media_treino = float(np.average(treino.y, weights=treino.peso))
    resultados.append(avaliar(teste.y, baseline_taxa_base(treino.y, treino.peso, len(teste)),
                              teste.peso, "taxa_base"))
    resultados.append(avaliar(teste.y, baseline_persistencia(teste.contexto, media_treino),
                              teste.peso, "persistencia_municipal"))
    for r in resultados:
        print(f"  {r['modelo']:24s} AUC {r['auc_roc']:.4f}")

    # --- validação cruzada agrupada por escola -----------------------------
    print(f"\nValidação cruzada ({N_FOLDS} folds, agrupada por escola, dentro de {ANO_TREINO})")
    # O peso entra no ajuste; o score do fold sai sem peso, porque o scorer do
    # sklearn não recebe roteamento aqui. Serve como medida de estabilidade
    # entre folds, não como estimativa populacional — essa vem do teste.
    cv_resumo = {}
    for nome, construtor in MODELOS.items():
        notas = cronometrar(nome, cross_val_score, construtor(numericas, categoricas),
                            treino.X, treino.y,
                            groups=treino.grupo, cv=GroupKFold(n_splits=N_FOLDS),
                            scoring="roc_auc",
                            params={"modelo__sample_weight": treino.peso})
        cv_resumo[nome] = (notas.mean(), notas.std())
        print(f"    AUC {notas.mean():.4f} ± {notas.std():.4f}")

    # --- treino final e avaliação fora do tempo ----------------------------
    print(f"\nTreino final em {ANO_TREINO}, avaliação em {ANO_TESTE}")
    ajustados = {}
    for nome, construtor in MODELOS.items():
        modelo = construtor(numericas, categoricas)
        cronometrar(f"{nome} (fit)", modelo.fit, treino.X, treino.y,
                    modelo__sample_weight=treino.peso)
        ajustados[nome] = modelo
        prob = modelo.predict_proba(teste.X)[:, 1]
        resultados.append(avaliar(teste.y, prob, teste.peso, nome))
        print(f"    AUC fora do tempo {resultados[-1]['auc_roc']:.4f}")

    placar = tabela(resultados)
    print("\n" + placar.to_string())
    ganhos = ganho_sobre(resultados, "persistencia_municipal")
    melhor = placar.index[0]

    # --- interpretabilidade -------------------------------------------------
    print("\nInterpretabilidade")
    modelo_melhor = ajustados.get(melhor, ajustados["boosting"])
    if melhor not in ajustados:
        melhor = "boosting"
    amostra = teste.X[usadas].sample(min(N_PERMUTACAO, len(teste.X)), random_state=SEMENTE)
    perm = cronometrar("permutação", permutation_importance, modelo_melhor, amostra,
                       teste.y.loc[amostra.index], n_repeats=3,
                       random_state=SEMENTE, scoring="roc_auc", n_jobs=1)
    importancia = (pd.Series(perm.importances_mean, index=usadas)
                   .sort_values(ascending=False))
    print(importancia.head(8).round(4).to_string())

    shap_series = None
    if not args.sem_shap:
        try:
            import shap
            sub = teste.X[usadas].sample(min(N_SHAP, len(teste.X)), random_state=SEMENTE)
            transformado = modelo_melhor.named_steps["preparo"].transform(sub)
            explicador = shap.TreeExplainer(modelo_melhor.named_steps["modelo"])
            valores = cronometrar("shap", explicador.shap_values, transformado)
            valores = np.asarray(valores)
            # A floresta devolve um eixo por classe; fica o da classe positiva.
            if valores.ndim == 3:
                valores = valores[..., -1]
            shap_series = (pd.Series(np.abs(valores).mean(axis=0),
                                     index=nomes_das_features(modelo_melhor))
                           .sort_values(ascending=False))
            print(shap_series.head(8).round(4).to_string())
        except Exception as e:  # noqa: BLE001 — SHAP é acessório, não pode derrubar o treino
            linhas_extra.append(f"SHAP não pôde ser calculado: {type(e).__name__}: {e}")
            print(f"  SHAP indisponível: {e}")

    # --- figuras ------------------------------------------------------------
    # Duas métricas, dois painéis: discriminação (ordenar alunos) e calibração
    # (acertar a probabilidade). O modelo perde numa e ganha na outra, e um
    # gráfico só contaria metade da história.
    rotulo_modelo = {"taxa_base": "Taxa média (moeda)",
                     "persistencia_municipal": "Persistência municipal",
                     "logistica": "Regressão logística",
                     "floresta": "Random forest",
                     "boosting": "Gradient boosting"}
    baselines = ("taxa_base", "persistencia_municipal")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 3.3),
                                   gridspec_kw={"wspace": 0.55})

    ordem = placar.sort_values("auc_roc")
    cores = [SERIE[1] if i in baselines else SERIE[0] for i in ordem.index]
    ax1.barh([rotulo_modelo[i] for i in ordem.index], (ordem.auc_roc - 0.5) * 100,
             height=0.6, color=cores)
    for i, v in enumerate(ordem.auc_roc):
        ax1.text((v - 0.5) * 100 + 0.4, i, num(v, 3), va="center", color=TINTA, fontsize=10)
    ax1.set_xlim(0, (ordem.auc_roc.max() - 0.5) * 100 * 1.32)
    titular(ax1, "Discriminação — AUC", "Maior é melhor. Escala: distância de 0,5.")

    ordem_b = placar.sort_values("brier", ascending=False)
    cores_b = [SERIE[1] if i in baselines else SERIE[0] for i in ordem_b.index]
    ax2.barh([rotulo_modelo[i] for i in ordem_b.index], ordem_b.brier,
             height=0.6, color=cores_b)
    for i, v in enumerate(ordem_b.brier):
        ax2.text(v + ordem_b.brier.max() * 0.015, i, num(v, 4), va="center",
                 color=TINTA, fontsize=10)
    ax2.set_xlim(0, ordem_b.brier.max() * 1.25)
    titular(ax2, "Calibração — Brier", "Menor é melhor. Laranja: sem aprendizado.")

    for eixo in (ax1, ax2):
        eixo.xaxis.set_visible(False)
        for lado in ("bottom", "left"):
            eixo.spines[lado].set_visible(False)
    fig_placar = salvar(fig, DIR_IMAGENS, "06_desempenho_modelos")

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    topo = importancia.head(12).sort_values()
    ax.barh(topo.index.tolist(), topo.values, height=0.62, color=SERIE[0])
    ax.axvline(0, color=TINTA_3, linewidth=0.8)
    ax.xaxis.set_visible(False)
    for lado in ("bottom", "left"):
        ax.spines[lado].set_visible(False)
    for i, v in enumerate(topo.values):
        ax.text(v + topo.max() * 0.02, i, num(v, 4), va="center", color=TINTA, fontsize=9)
    ax.set_xlim(min(0, topo.min() * 1.2), topo.max() * 1.35)
    titular(ax, "Importância por permutação",
            f"Queda de AUC ao embaralhar cada variável. Modelo {melhor}, {ANO_TESTE}.")
    fig_importancia = salvar(fig, DIR_IMAGENS, "07_importancia_permutacao")

    # --- relatório ----------------------------------------------------------
    linhas = [
        "# Modelagem — predição de alfabetização no grão do aluno", "",
        f"Treino em {ANO_TREINO} ({milhar(len(treino))} alunos, "
        f"{milhar(treino.grupo.nunique())} escolas), "
        f"teste em {ANO_TESTE} ({milhar(len(teste))} alunos). Divisão temporal, validação cruzada "
        f"agrupada por escola, tudo ponderado pelo peso amostral.",
        "", "## Resultados", "", markdown_tabela(placar, "modelo"), "",
        "### Validação cruzada dentro do treino", "",
        "| modelo | AUC média | desvio entre folds |", "|---|---:|---:|",
    ]
    linhas += [f"| {n} | {m:.4f} | {s:.4f} |" for n, (m, s) in cv_resumo.items()]
    linhas += [
        "", "### Ganho sobre a persistência territorial", "",
        "O baseline que importa não é a moeda: é prever, para cada aluno, a taxa do seu "
        "município no ano anterior. Ele não usa aprendizado nenhum.", "",
    ]
    linhas += [f"- **{n}**: {v:+.1%} de discriminação sobre a persistência"
               for n, v in ganhos.items()]
    linhas += ["", "## Interpretabilidade", "",
               "### Importância por permutação (queda de AUC ao embaralhar)", "",
               markdown_tabela(importancia.head(12).round(5).rename("queda_de_auc"), "feature"), ""]
    if shap_series is not None:
        linhas += ["### SHAP (magnitude média)", "",
                   markdown_tabela(shap_series.head(12).round(5).rename("shap_medio"), "feature"), ""]
    linhas += linhas_extra
    linhas += ["## Figuras", "",
               f"![desempenho](../images/{fig_placar})", "",
               f"![importância](../images/{fig_importancia})", ""]

    DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    (DIR_REPORTS / "MODELAGEM.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"\nrelatório: {DIR_REPORTS / 'MODELAGEM.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
