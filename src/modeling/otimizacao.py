"""Busca de hiperparâmetros com validação agrupada, dentro do ano de treino.

Duas regras governam tudo aqui, e as duas existem para que o número publicado
continue significando alguma coisa:

1. **A busca não vê o ano de teste.** Toda a seleção acontece por validação
   cruzada dentro de 2024. Escolher configuração olhando 2025 transformaria o
   teste fora do tempo em conjunto de treino disfarçado, e o AUC reportado
   passaria a descrever o quanto tentamos, não o quanto o modelo generaliza.

2. **Os folds agrupam por escola.** Sem isso, colegas do mesmo aluno caem dos dois
   lados da divisão e o score infla — 14,5% da variância do alvo está entre
   escolas. A busca escolheria a configuração que melhor decora turma.

Busca aleatória e não exaustiva: com sinal fraco, o ganho de varrer a grade
inteira não paga o tempo. Amostrar o espaço cobre mais dimensões por unidade de
custo, que é o que importa quando a dúvida é *se* o ajuste move alguma coisa.

O score da validação cruzada sai **sem peso amostral** — o `sample_weight` entra
no ajuste, mas o scorer do sklearn não o recebe por este caminho. Serve para
ordenar configurações entre si, que é o uso aqui; a estimativa populacional vem
da avaliação fora do tempo, essa sim ponderada.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, RandomizedSearchCV

from src.modeling.pipeline import MODELOS, SEMENTE

# Espaços de busca. Cada um centrado no valor que já estava fixo no pipeline, para
# que a comparação "ajustado contra padrão" seja informativa: se o padrão vencer,
# a busca confirma a escolha estrutural em vez de não ter procurado.
ESPACOS: dict[str, dict] = {
    "logistica": {
        # Regularização: o único eixo que muda o comportamento de uma logística
        # com pré-processamento fixo.
        "modelo__C": [0.01, 0.1, 0.3, 1.0, 3.0, 10.0],
        "modelo__class_weight": [None, "balanced"],
    },
    "floresta": {
        "modelo__n_estimators": [150, 200, 300],
        # Profundidade e folha mínima são os dois freios de overfitting numa
        # floresta; varrê-los juntos é o ponto da busca.
        "modelo__max_depth": [10, 14, 18, 24, None],
        "modelo__min_samples_leaf": [20, 50, 100, 200, 400],
        "modelo__max_features": ["sqrt", 0.3, 0.5],
    },
    "boosting": {
        "modelo__learning_rate": [0.02, 0.05, 0.08, 0.15],
        "modelo__max_iter": [200, 300, 500],
        "modelo__max_leaf_nodes": [15, 31, 63],
        "modelo__min_samples_leaf": [50, 100, 200, 400],
        "modelo__l2_regularization": [0.0, 0.5, 1.0, 5.0],
    },
}


@dataclass
class Busca:
    """O que uma busca produziu, pronto para relatório."""
    modelo: str
    melhor_config: dict
    score_melhor: float
    score_padrao: float
    desvio_melhor: float
    n_candidatos: int
    segundos: float
    tabela: pd.DataFrame = field(repr=False)

    @property
    def ganho(self) -> float:
        """Ganho em discriminação efetiva — AUC se lê a partir de 0,5, não de 0."""
        return (self.score_melhor - 0.5) / (self.score_padrao - 0.5) - 1


def _limpar(config: dict) -> dict:
    """Tira o prefixo `modelo__` para que a configuração possa ser lida e reusada."""
    return {c.removeprefix("modelo__"): v for c, v in config.items()}


def buscar(nome: str, treino, numericas, categoricas, n_candidatos: int = 15,
           n_folds: int = 3, semente: int = SEMENTE) -> RandomizedSearchCV:
    """Busca aleatória com `GroupKFold` por escola, dentro do conjunto de treino."""
    busca = RandomizedSearchCV(
        MODELOS[nome](numericas, categoricas),
        param_distributions=ESPACOS[nome],
        n_iter=n_candidatos,
        cv=GroupKFold(n_splits=n_folds),
        scoring="roc_auc",
        random_state=semente,
        # O estimador já paraleliza internamente; paralelizar a busca por cima
        # disputaria os mesmos núcleos e sairia mais lento.
        n_jobs=1,
        refit=False,
        error_score="raise",
    )
    busca.fit(treino.X, treino.y, groups=treino.grupo,
              **{"modelo__sample_weight": treino.peso})
    return busca


def resumir(nome: str, busca: RandomizedSearchCV, score_padrao: float,
            segundos: float) -> Busca:
    """Extrai da busca o que vai ao relatório, incluindo a lista de candidatos."""
    r = pd.DataFrame(busca.cv_results_)
    tabela = (r[["mean_test_score", "std_test_score", "params"]]
              .sort_values("mean_test_score", ascending=False)
              .assign(params=lambda d: d.params.map(_limpar))
              .reset_index(drop=True))
    melhor = int(np.argmax(r.mean_test_score))
    return Busca(
        modelo=nome,
        melhor_config=_limpar(r.params.iloc[melhor]),
        score_melhor=float(r.mean_test_score.iloc[melhor]),
        desvio_melhor=float(r.std_test_score.iloc[melhor]),
        score_padrao=score_padrao,
        n_candidatos=len(r),
        segundos=segundos,
        tabela=tabela,
    )


def adotar(busca: Busca, ganho_minimo: float = 0.0) -> dict:
    """Devolve a configuração a usar: a ajustada só se ela realmente ganhou.

    Trocar o padrão por uma configuração que empata dentro do ruído entre folds
    não é ajuste fino, é escolher barulho. O critério é ganhar mais que o desvio
    observado entre os folds da própria busca.
    """
    limiar = max(ganho_minimo, busca.desvio_melhor)
    if busca.score_melhor - busca.score_padrao > limiar:
        return busca.melhor_config
    return {}
