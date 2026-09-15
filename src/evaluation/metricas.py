"""Métricas e baselines.

Toda métrica é ponderada pelo peso amostral. Sem isso ela descreve a amostra
avaliada, não a população de crianças — e o indicador oficial é ponderado.

Os baselines importam mais que de costume aqui. Com 86% da variância entre
alunos da mesma escola (ver `reports/EDA.md`), qualquer modelo terá discriminação
modesta, e o número sozinho não diz se ele é bom. O que diz é a comparação com
**persistência territorial**: prever para todo aluno a taxa do seu município no
ano anterior. Se o modelo não superar isso, ele não aprendeu nada além do que já
estava na tabela.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, f1_score, log_loss,
    roc_auc_score,
)

# Corte para as métricas de classe. A saída do modelo é uma probabilidade que
# depois é somada por município; o corte só existe para acurácia e F1.
CORTE = 0.5


def avaliar(y, probabilidade, peso, nome: str) -> dict:
    """AUC, precisão média, Brier, log loss, acurácia e F1 — todos ponderados."""
    y = np.asarray(y)
    p = np.clip(np.asarray(probabilidade), 1e-6, 1 - 1e-6)
    w = np.asarray(peso, dtype="float64")
    classe = (p >= CORTE).astype(int)
    return {
        "modelo": nome,
        "auc_roc": roc_auc_score(y, p, sample_weight=w),
        "precisao_media": average_precision_score(y, p, sample_weight=w),
        "brier": brier_score_loss(y, p, sample_weight=w),
        "log_loss": log_loss(y, p, sample_weight=w),
        "acuracia": accuracy_score(y, classe, sample_weight=w),
        "f1": f1_score(y, classe, sample_weight=w),
        "taxa_base": float(np.average(y, weights=w)),
    }


def baseline_taxa_base(treino_y, treino_peso, n: int) -> np.ndarray:
    """Prevê a taxa média do treino para todo mundo. O piso absoluto: AUC 0,5."""
    return np.full(n, float(np.average(treino_y, weights=treino_peso)))


def baseline_persistencia(contexto: pd.DataFrame, media_global: float,
                          coluna: str = "mun_taxa_rede_t1") -> np.ndarray:
    """Prevê a taxa do município no ano anterior.

    É o baseline que realmente desafia o modelo: não usa aprendizado nenhum,
    só a coluna que já existe na base. Municípios sem histórico caem na média.

    A coluna padrão é a taxa da **rede do próprio aluno** (`mun_taxa_rede_t1`),
    não a da rede pública agregada. A revisão final mostrou que essa distinção
    decide o placar no grão do aluno: a taxa da rede do aluno sozinha faz AUC
    0,6433 em 2025, acima da floresta (0,6407); a da rede pública faz 0,6397, e
    era contra ela que o README comparava. Como a feature mais importante do
    modelo é justamente `mun_taxa_rede_t1`, o baseline justo é ela. Os dois são
    publicados, para que a diferença fique visível.
    """
    return contexto[coluna].fillna(media_global).to_numpy()


def tabela(resultados: list[dict]) -> pd.DataFrame:
    return (pd.DataFrame(resultados)
            .set_index("modelo")
            .sort_values("auc_roc", ascending=False)
            .round(4))


def ganho_sobre(resultados: list[dict], referencia: str, metrica: str = "auc_roc") -> dict:
    """Quanto cada modelo ganha sobre um baseline, na escala que importa.

    Para AUC o zero útil é 0,5 (moeda), não 0 — então o ganho é medido sobre a
    discriminação efetiva, e não sobre o valor bruto.
    """
    base = next(r for r in resultados if r["modelo"] == referencia)[metrica]
    escala = 0.5 if metrica == "auc_roc" else 0.0
    return {r["modelo"]: (r[metrica] - escala) / (base - escala) - 1
            for r in resultados if r["modelo"] != referencia}
