"""Preparação dos dados para a modelagem: features, alvo, grupos e divisão.

A divisão é **temporal**: treina em 2024 e testa em 2025. É mais exigente que
uma divisão aleatória e mede o que interessa de verdade — se o modelo
generaliza para o ano seguinte, que é como ele seria usado.

Dentro do treino, a validação cruzada agrupa por escola. Sem isso, colegas do
mesmo aluno caem dos dois lados da divisão e a métrica infla: como 14,5% da
variância do alvo está entre escolas (ver `reports/EDA.md`), conhecer um colega
é quase conhecer a resposta.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import DIR_GOLD

ANO_TREINO, ANO_TESTE = 2024, 2025
ALVO = "alfabetizado"
PESO = "peso_amostral"
GRUPO = "id_escola_ano"

# Identificadores nunca entram como feature. `id_municipio` em particular seria
# uma categórica de 5,5 mil níveis: o modelo decoraria o município em vez de
# aprender o que o torna diferente, e não generalizaria para nenhum território
# fora da base. O contexto municipal já entra pelas variáveis derivadas.
IDENTIFICADORES = ["id_aluno", "id_escola_ano", "id_municipio", "ano"]

NUMERICAS = [
    "escola_alunos_avaliados", "mun_alunos_avaliados",
    "latitude", "longitude",
    "mun_taxa_rede_t1", "mun_taxa_publica_t1", "mun_nivel_t1",
    "mun_variacao_publica_t1", "mun_meta_ano",
    "uf_taxa_publica_t1", "uf_variacao_publica_t1", "uf_meta_ano",
    "mun_inse_media", "mun_inse_pct_vulneravel", "mun_inse_alunos",
    "mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1",
    "mun_reprovacao_2ano_t1", "mun_abandono_iniciais_t1",
]
CATEGORICAS = ["sigla_uf", "regiao", "rede_label", "capital"]
FEATURES = NUMERICAS + CATEGORICAS


# Colunas que não são feature mas que a avaliação precisa: o baseline de
# persistência consulta a taxa do município em t-1, e a agregação municipal
# precisa saber a rede do aluno e a meta do seu município.
CONTEXTO = ["id_municipio", "sigla_uf", "rede", "mun_taxa_publica_t1",
            "mun_taxa_rede_t1", "mun_meta_ano"]


@dataclass
class Conjunto:
    """Um recorte temporal pronto para treino ou avaliação."""
    X: pd.DataFrame
    y: pd.Series
    peso: pd.Series
    grupo: pd.Series
    # Guardado à parte para os baselines e para a agregação territorial. Nada
    # daqui entra como feature.
    contexto: pd.DataFrame

    def __len__(self) -> int:
        return len(self.y)


def recortar(base: pd.DataFrame, ano: int) -> Conjunto:
    d = base[base.ano == ano]
    X = d[FEATURES].copy()
    # A categórica precisa ser texto para o OneHot/Ordinal: `capital` é 0/1 mas
    # significa interior/capital, não uma quantidade.
    X["capital"] = X.capital.astype("string").fillna("desconhecido")
    for c in CATEGORICAS:
        X[c] = X[c].astype("string").fillna("desconhecido")
    return Conjunto(X=X, y=d[ALVO], peso=d[PESO], grupo=d[GRUPO],
                    contexto=d[CONTEXTO])


def features_utilizaveis(treino: Conjunto) -> tuple[list[str], list[str]]:
    """Separa as features que o treino realmente pode ensinar.

    Uma variável inteiramente nula no ano de treino não é apenas inútil: sob
    divisão temporal ela é perigosa, porque estará presente no teste e o modelo
    nunca viu um valor dela. `mun_variacao_publica_t1` e `uf_variacao_publica_t1`
    caem exatamente nesse caso — a variação em t-1 exige t-2, que não existe para
    2024. Melhor descartar de forma explícita do que imputar um valor inventado.
    """
    vazias = [c for c in NUMERICAS if treino.X[c].isna().all()]
    return [c for c in NUMERICAS if c not in vazias], list(CATEGORICAS), vazias


def unir(*conjuntos: Conjunto) -> Conjunto:
    """Junta recortes de anos diferentes num único conjunto de treino.

    Serve ao modelo de produção, que não tem por que descartar metade dos dados:
    a divisão temporal existe para *medir* generalização, não para limitar o que
    o modelo final aprende. Ver `prever_municipios.py`, que ajusta os dois.
    """
    return Conjunto(
        X=pd.concat([c.X for c in conjuntos], ignore_index=True),
        y=pd.concat([c.y for c in conjuntos], ignore_index=True),
        peso=pd.concat([c.peso for c in conjuntos], ignore_index=True),
        grupo=pd.concat([c.grupo for c in conjuntos], ignore_index=True),
        contexto=pd.concat([c.contexto for c in conjuntos], ignore_index=True),
    )


def ler_base(amostra: int | None = None, semente: int = 42) -> pd.DataFrame:
    """A `aluno_features` inteira, opcionalmente amostrada.

    `amostra` limita o número de linhas por ano, para iteração rápida. A
    amostragem é por **escola**, não por aluno: sortear alunos soltos quebraria
    os grupos e tornaria a validação agrupada inconsistente.

    Exposta além de `carregar` porque a projeção precisa das colunas cruas — o
    roteiro de alunos do último ano avaliado serve de molde para o ano seguinte.
    """
    base = pd.read_parquet(DIR_GOLD / "aluno_features.parquet")
    if not amostra:
        return base
    partes = []
    for ano in (ANO_TREINO, ANO_TESTE):
        d = base[base.ano == ano]
        escolas = d[GRUPO].drop_duplicates()
        fracao = min(1.0, amostra / len(d))
        sorteadas = escolas.sample(frac=fracao, random_state=semente)
        partes.append(d[d[GRUPO].isin(set(sorteadas))])
    return pd.concat(partes, ignore_index=True)


def carregar(amostra: int | None = None, semente: int = 42) -> tuple[Conjunto, Conjunto]:
    """Devolve (treino de 2024, teste de 2025)."""
    base = ler_base(amostra, semente)
    return recortar(base, ANO_TREINO), recortar(base, ANO_TESTE)
