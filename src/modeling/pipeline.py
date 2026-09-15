"""Pipelines de modelagem, com o pré-processamento acoplado ao estimador.

Acoplar não é preferência de estilo: é o que impede vazamento. Um imputador ou
um scaler ajustado fora do pipeline aprende a mediana e o desvio do conjunto
inteiro — teste incluído — e essa informação escorre para dentro do treino. Com
tudo dentro de um `Pipeline`, cada fold da validação cruzada reajusta o
pré-processamento apenas com os seus próprios dados de treino.

Três modelos, com pré-processamentos diferentes porque precisam de coisas
diferentes:

- **Regressão logística** — referência linear. Precisa de imputação explícita,
  padronização e one-hot.
- **Random forest** — árvores fundas e independentes, depois a média. Precisa de
  imputação e one-hot, mas não de escala.
- **Gradient boosting em histograma** — trata valor faltante nativamente
  (aprende para que lado mandar o nulo em cada divisão) e lida com categórica
  ordinal sem supor ordem, porque as divisões são por conjunto de categorias.
"""
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

SEMENTE = 42


def _preprocessador_linear(numericas, categoricas) -> ColumnTransformer:
    return ColumnTransformer([
        ("numericas", Pipeline([
            ("imputar", SimpleImputer(strategy="median", add_indicator=True)),
            ("padronizar", StandardScaler()),
        ]), numericas),
        ("categoricas", OneHotEncoder(handle_unknown="ignore", min_frequency=0.005,
                                      sparse_output=False), categoricas),
    ], remainder="drop")


def _preprocessador_arvore(numericas, categoricas) -> ColumnTransformer:
    return ColumnTransformer([
        ("numericas", "passthrough", numericas),
        ("categoricas", OrdinalEncoder(handle_unknown="use_encoded_value",
                                       unknown_value=-1,
                                       encoded_missing_value=-1), categoricas),
    ], remainder="drop")


def _preprocessador_floresta(numericas, categoricas) -> ColumnTransformer:
    """Imputa e aplica one-hot, sem padronizar.

    A floresta não precisa de escala, mas precisa de imputação: ao contrário do
    boosting em histograma, ela não aprende para que lado mandar o nulo. E
    precisa de one-hot em vez de ordinal — sem divisão por conjunto de
    categorias, um código ordinal faria a árvore tratar `sigla_uf` como se
    houvesse ordem entre os estados.
    """
    return ColumnTransformer([
        ("numericas", SimpleImputer(strategy="median", add_indicator=True), numericas),
        ("categoricas", OneHotEncoder(handle_unknown="ignore", min_frequency=0.005,
                                      sparse_output=False), categoricas),
    ], remainder="drop")


def logistica(numericas, categoricas, **parametros) -> Pipeline:
    padrao = dict(max_iter=1000, random_state=SEMENTE)
    padrao.update(parametros)
    return Pipeline([
        ("preparo", _preprocessador_linear(numericas, categoricas)),
        ("modelo", LogisticRegression(**padrao)),
    ])


def boosting(numericas, categoricas, **parametros) -> Pipeline:
    padrao = dict(
        max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
        min_samples_leaf=200,
        # Regularização: o objetivo é generalizar para o ano seguinte, não
        # decorar 2024.
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
        n_iter_no_change=20, random_state=SEMENTE,
    )
    padrao.update(parametros)
    indices_categoricas = list(range(len(numericas), len(numericas) + len(categoricas)))
    return Pipeline([
        ("preparo", _preprocessador_arvore(numericas, categoricas)),
        ("modelo", HistGradientBoostingClassifier(
            categorical_features=indices_categoricas, **padrao)),
    ])


def floresta(numericas, categoricas, **parametros) -> Pipeline:
    """Random forest: muitas árvores profundas e independentes, depois a média.

    Complementa o boosting por um caminho oposto. O boosting encadeia árvores
    rasas, cada uma corrigindo o erro da anterior — ataca viés. A floresta faz
    árvores fundas e descorrelacionadas em amostras e subconjuntos de variáveis
    diferentes, e tira a média — ataca variância. Com sinal fraco e 1,8 milhão de
    linhas, ver se os dois chegam ao mesmo teto é informativo: se chegam, o
    limite é dos dados, não do algoritmo.

    A profundidade é limitada por necessidade prática: sem teto, cada árvore
    guardaria da ordem de um milhão de nós e o modelo decoraria o treino.
    """
    padrao = dict(
        n_estimators=200, max_depth=18, min_samples_leaf=100,
        max_features="sqrt", n_jobs=-1, random_state=SEMENTE,
    )
    padrao.update(parametros)
    return Pipeline([
        ("preparo", _preprocessador_floresta(numericas, categoricas)),
        ("modelo", RandomForestClassifier(**padrao)),
    ])


MODELOS = {"logistica": logistica, "floresta": floresta, "boosting": boosting}


def nomes_das_features(pipeline: Pipeline) -> list[str]:
    """Nomes na ordem em que o estimador os vê, para ler importância e SHAP."""
    return list(pipeline.named_steps["preparo"].get_feature_names_out())
