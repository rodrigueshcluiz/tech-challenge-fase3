"""Agregação da predição do aluno para o grão em que a política pública decide.

O modelo prevê no grão do aluno e ali sua discriminação é modesta — AUC 0,64,
porque 86% da variância do alvo está entre alunos da mesma escola e nenhuma
variável disponível alcança esse nível. Mas a pergunta do gestor não é *"esta
criança será alfabetizada?"*: é *"meu município vai cumprir a meta?"*.

Essa mudança de grão muda o problema. A taxa municipal prevista é a média
ponderada das probabilidades individuais, e **o erro individual se cancela na
média**: o que sobra é o viés sistemático do modelo sobre aquele território, que
é justamente o que ele aprendeu. Um modelo fraco no indivíduo pode ser bom no
agregado — e é isso que este módulo mede, em vez de supor.

O recorte é município × **rede municipal**, e não por escolha estética: é o
único em que o INEP publica meta por município (`REDE_META_MUNICIPIO`). Comparar
a taxa da rede pública inteira com a meta da rede municipal compararia coisas
diferentes.

Nada do ano avaliado entra na predição: as features são contexto de t-1 e metas
publicadas antes da avaliação. A comparação com o resultado de 2025 é aferição,
não insumo.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.config import REDE_META_MUNICIPIO

# Quantos alunos avaliados um município precisa ter para entrar na avaliação do
# método. Abaixo disso a taxa observada é ela própria ruído amostral, e o erro
# medido diria mais sobre o tamanho da amostra do que sobre o modelo.
MINIMO_ALUNOS = 30

# A taxa publicada por município vem arredondada; reconstruí-la a partir dos
# microdados reproduz o valor até esse arredondamento, não além dele.
TOLERANCIA_MART = 0.001
FRACAO_MINIMA_CONFORME = 0.995


def _phi(z):
    """Normal padrão acumulada, sem trazer o SciPy só por uma função."""
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(z, dtype="float64")
                                               / math.sqrt(2.0)))


def agregar(contexto: pd.DataFrame, probabilidade, peso, alvo=None,
            rede: int = REDE_META_MUNICIPIO) -> pd.DataFrame:
    """Leva a predição do aluno para o grão município × rede municipal.

    Devolve, por município: a taxa prevista (média ponderada das probabilidades),
    a taxa do ano anterior, a meta do ano e o tamanho amostral.

    `alvo` é opcional porque a função serve aos dois usos: na aferição existe
    gabarito e saem também a taxa observada e o erro; numa projeção de ano futuro
    não existe, e as colunas simplesmente não aparecem — melhor que devolvê-las
    preenchidas com zero, que alguém acabaria lendo como resultado.

    A soma ponderada é feita por coluna auxiliar e não por `apply`: com quase dois
    milhões de linhas, uma função Python por grupo custaria minutos.
    """
    w = np.asarray(peso, dtype="float64")
    d = contexto.assign(_w=w, _w2=w ** 2,
                        _wp=w * np.asarray(probabilidade, dtype="float64"))
    if alvo is not None:
        d["_wy"] = w * np.asarray(alvo, dtype="float64")
    d = d[d.rede == rede]
    if d.empty:
        raise ValueError(f"nenhum aluno da rede {rede} no conjunto avaliado")

    somas = dict(
        sigla_uf=("sigla_uf", "first"),
        # Constantes dentro do grupo: vêm dos marts, no grão do município.
        taxa_t1=("mun_taxa_rede_t1", "first"),
        meta_taxa=("mun_meta_ano", "first"),
        alunos_avaliados=("_w", "size"),
        peso_total=("_w", "sum"), soma_peso2=("_w2", "sum"),
        soma_wp=("_wp", "sum"),
    )
    if alvo is not None:
        somas["soma_wy"] = ("_wy", "sum")
    agregado = d.groupby("id_municipio", dropna=False).agg(**somas).reset_index()

    agregado["taxa_prevista"] = agregado.soma_wp / agregado.peso_total
    # Tamanho efetivo de Kish: com pesos desiguais, n linhas não valem n
    # observações independentes. Serve para estratificar a incerteza.
    agregado["alunos_efetivos"] = agregado.peso_total ** 2 / agregado.soma_peso2
    agregado = agregado.drop(columns=["soma_peso2", "soma_wp"])

    if alvo is not None:
        agregado["taxa_observada"] = agregado.soma_wy / agregado.peso_total
        agregado["erro"] = agregado.taxa_prevista - agregado.taxa_observada
        agregado["erro_t1"] = agregado.taxa_t1 - agregado.taxa_observada
        agregado = agregado.drop(columns="soma_wy")
    return agregado.sort_values("id_municipio").reset_index(drop=True)


def conferir_contra_mart(agregado: pd.DataFrame, mart: pd.DataFrame,
                         ano: int, tolerancia: float = TOLERANCIA_MART) -> dict:
    """A taxa observada reconstruída tem de bater com o mart oficial.

    É a mesma prova que valida a Gold, aplicada aqui: se a média ponderada dos
    alunos não reproduz o indicador publicado, a agregação está errada e todo o
    resto do relatório é ficção.

    O critério é de conformidade em massa, não de igualdade exata, porque as duas
    quantidades têm origens diferentes: o mart vem da planilha divulgada, com
    arredondamento, e o agregado vem dos microdados ponderados. Exigir zero
    reprovaria o pipeline por causa da quarta casa decimal.
    """
    oficial = (mart[mart.ano == ano][["id_municipio", "taxa_alfabetizacao"]]
               .rename(columns={"taxa_alfabetizacao": "_oficial"}))
    conf = agregado.merge(oficial, on="id_municipio", how="inner")
    conf = conf[conf._oficial.notna()]
    if conf.empty:
        return {"conferidos": 0, "conformes": 0, "fracao": float("nan"),
                "mediana": float("nan"), "maxima": float("nan"), "ok": False,
                "divergentes": conf.head(0)}
    diferenca = (conf.taxa_observada - conf._oficial).abs()
    conformes = int((diferenca <= tolerancia).sum())
    fracao = conformes / len(conf)
    divergentes = (conf.assign(diferenca=diferenca)[diferenca > tolerancia]
                   .nlargest(10, "diferenca")
                   [["id_municipio", "sigla_uf", "alunos_avaliados",
                     "taxa_observada", "_oficial", "diferenca"]]
                   .rename(columns={"_oficial": "taxa_publicada"}))
    return {"conferidos": len(conf), "conformes": conformes, "fracao": fracao,
            "mediana": float(diferenca.median()), "maxima": float(diferenca.max()),
            "ok": fracao >= FRACAO_MINIMA_CONFORME, "divergentes": divergentes}


def metricas_de_taxa(d: pd.DataFrame, coluna: str) -> dict:
    """Erro da taxa municipal prevista, em pontos percentuais."""
    erro = d[coluna] - d.taxa_observada
    return {
        "erro_medio_absoluto": float(erro.abs().mean()),
        "raiz_erro_quadratico": float(np.sqrt((erro ** 2).mean())),
        "vies": float(erro.mean()),
        "correlacao": float(d[coluna].corr(d.taxa_observada)),
        "dentro_de_5pp": float((erro.abs() <= 0.05).mean()),
    }


def metricas_de_risco(d: pd.DataFrame, coluna: str) -> dict:
    """Acerto na pergunta binária: o município fica abaixo da meta?

    A classe positiva é **não atingir** a meta, porque é ela que dispara ação. O
    recall importa mais que a precisão: deixar de sinalizar um município em risco
    custa mais caro do que visitar um que ia cumprir sozinho.
    """
    real = (d.taxa_observada < d.meta_taxa).to_numpy()
    previsto = (d[coluna] < d.meta_taxa).to_numpy()
    vp = int((real & previsto).sum())
    fp = int((~real & previsto).sum())
    fn = int((real & ~previsto).sum())
    vn = int((~real & ~previsto).sum())
    precisao = vp / (vp + fp) if vp + fp else float("nan")
    recall = vp / (vp + fn) if vp + fn else float("nan")
    soma = precisao + recall
    f1 = 2 * precisao * recall / soma if soma and not math.isnan(soma) else float("nan")
    # O score contínuo é a distância até a meta: quanto mais abaixo, mais risco.
    score = (d.meta_taxa - d[coluna]).to_numpy()
    auc = roc_auc_score(real, score) if 0 < real.sum() < len(real) else float("nan")
    return {
        "acuracia": (vp + vn) / len(d),
        "precisao": precisao,
        "recall": recall,
        "f1": f1,
        "auc_roc": auc,
        "verdadeiros_positivos": vp, "falsos_positivos": fp,
        "falsos_negativos": fn, "verdadeiros_negativos": vn,
    }


def desvio_por_porte(d: pd.DataFrame, n_estratos: int = 4) -> pd.DataFrame:
    """Desvio do erro de predição por faixa de tamanho do município.

    O erro não é homocedástico: num município com 40 alunos avaliados a própria
    taxa observada oscila vários pontos por sorteio, enquanto numa capital com
    dezenas de milhares ela é estável. Usar um desvio único trataria os dois
    casos como se tivessem a mesma incerteza.
    """
    d = d.copy()
    d["estrato"] = pd.qcut(d.alunos_efetivos, n_estratos, labels=False, duplicates="drop")
    return (d.groupby("estrato", dropna=False)
            .agg(municipios=("id_municipio", "size"),
                 alunos_efetivos_medianos=("alunos_efetivos", "median"),
                 desvio_do_erro=("erro", "std"),
                 erro_medio_absoluto=("erro", lambda s: s.abs().mean()))
            .reset_index())


def probabilidade_de_descumprir(d: pd.DataFrame, desvios: pd.DataFrame,
                                n_estratos: int = 4,
                                sigma_padrao: float | None = None) -> pd.Series:
    """Converte a distância até a meta em probabilidade de não cumpri-la.

    Modelo simples e declarado: o erro de predição dentro de cada estrato de
    porte é aproximadamente normal com desvio medido, então a probabilidade de o
    resultado ficar abaixo da meta é `Φ((meta − prevista) / σ_estrato)`.

    A honestidade aqui é dizer de onde vem o σ: dos resíduos do próprio ano de
    aferição. Aplicado a um ano ainda não avaliado, o σ do último ano validado é
    a estimativa disponível — e provavelmente otimista, porque não inclui a
    mudança de regime entre um ano e outro.
    """
    d = d.copy()
    d["estrato"] = pd.qcut(d.alunos_efetivos, n_estratos, labels=False, duplicates="drop")
    sigma = d.estrato.map(desvios.set_index("estrato").desvio_do_erro)
    # Numa projeção não há resíduo para servir de reserva: o σ tem de vir de
    # fora, medido no último ano com gabarito.
    reserva = sigma_padrao if sigma_padrao is not None else (
        d.erro.std() if "erro" in d.columns else desvios.desvio_do_erro.max())
    sigma = sigma.fillna(reserva).clip(lower=1e-4)
    return pd.Series(_phi((d.meta_taxa - d.taxa_prevista) / sigma), index=d.index)


def diagnostico_de_deriva(d: pd.DataFrame) -> dict:
    """Separa o erro de nível do erro de ordenação.

    Um modelo treinado em t-1 não tem como antecipar que o país inteiro sobe no
    ano seguinte: essa parcela do erro é deslocamento de nível, e aparece como
    viés. O que sobra depois de descontar o viés é o erro que se pode atribuir ao
    modelo — se ele encolhe muito, o problema não era o modelo, era a deriva.

    Nada aqui é correção da predição: o viés só é conhecido depois da avaliação.
    É diagnóstico, e está separado do resto por isso.
    """
    peso = d.peso_total
    nacional_observado = float(np.average(d.taxa_observada, weights=peso))
    nacional_t1 = float(np.average(d.taxa_t1, weights=peso))
    nacional_previsto = float(np.average(d.taxa_prevista, weights=peso))
    vies = float((d.taxa_prevista - d.taxa_observada).mean())
    erro_bruto = float((d.taxa_prevista - d.taxa_observada).abs().mean())
    erro_sem_vies = float((d.taxa_prevista - vies - d.taxa_observada).abs().mean())
    return {
        "nacional_t1": nacional_t1,
        "nacional_previsto": nacional_previsto,
        "nacional_observado": nacional_observado,
        "salto_do_ano": nacional_observado - nacional_t1,
        "vies": vies,
        "erro_medio_absoluto": erro_bruto,
        "erro_sem_vies": erro_sem_vies,
        "parcela_de_nivel": 1 - erro_sem_vies / erro_bruto if erro_bruto else float("nan"),
    }


def erro_por_uf(d: pd.DataFrame) -> pd.DataFrame:
    """Viés e erro por UF — onde a deriva se concentra."""
    return (d.assign(_abs=lambda x: x.erro.abs())
            .groupby("sigla_uf")
            .agg(municipios=("id_municipio", "size"),
                 taxa_t1=("taxa_t1", "mean"),
                 taxa_observada=("taxa_observada", "mean"),
                 vies=("erro", "mean"),
                 erro_medio_absoluto=("_abs", "mean"))
            .sort_values("vies")
            .reset_index())


def calibracao_do_risco(d: pd.DataFrame, coluna: str = "probabilidade_descumprir",
                        cortes=(0, 0.2, 0.4, 0.6, 0.8, 1.0)) -> pd.DataFrame:
    """Confronta a probabilidade declarada com a frequência observada.

    Uma probabilidade só é útil se corresponder a alguma coisa: dizer "80% de
    risco" para um grupo em que 60% descumpre é ordenar bem e calibrar mal, e o
    gestor que dimensiona recurso pela probabilidade precisa saber disso. A tabela
    é a única forma honesta de publicar o número — melhor que omiti-lo.
    """
    # Rótulos explícitos em vez dos intervalos do pandas: "(-0.001, 0.2]" é
    # ruído de implementação num relatório que alguém vai ler.
    rotulos = [f"{a * 100:.0f}% a {b * 100:.0f}%"
               for a, b in zip(cortes, cortes[1:])]
    faixa = pd.cut(d[coluna], list(cortes), include_lowest=True, labels=rotulos)
    return (d.assign(_faixa=faixa, _descumpriu=d.taxa_observada < d.meta_taxa)
            .groupby("_faixa", observed=True)
            .agg(municipios=("id_municipio", "size"),
                 risco_medio_previsto=(coluna, "mean"),
                 descumpriram_de_fato=("_descumpriu", "mean"))
            .reset_index()
            .rename(columns={"_faixa": "faixa_de_risco"}))


def ranking_de_risco(d: pd.DataFrame, nomes: pd.DataFrame) -> pd.DataFrame:
    """Tabela final: um município por linha, ordenada por risco."""
    saida = d.merge(nomes, on="id_municipio", how="left")
    saida["gap_previsto"] = saida.taxa_prevista - saida.meta_taxa
    # Numa projeção de ano futuro não há observado, e a coluna fica de fora em vez
    # de aparecer vazia.
    if "taxa_observada" in saida.columns:
        saida["gap_observado"] = saida.taxa_observada - saida.meta_taxa
    colunas = ["id_municipio", "nome_municipio", "sigla_uf", "alunos_avaliados",
               "taxa_t1", "meta_taxa", "taxa_prevista", "gap_previsto",
               "probabilidade_descumprir", "taxa_observada", "gap_observado", "erro"]
    return (saida[[c for c in colunas if c in saida.columns]]
            .sort_values("probabilidade_descumprir", ascending=False)
            .reset_index(drop=True))
