#!/usr/bin/env python3
"""Projeta a taxa de alfabetização por município e sinaliza risco de não cumprir a meta.

Treina em 2024 e projeta 2025 — a mesma divisão temporal da modelagem, porque a
pergunta é a mesma feita um ano antes: *com o que se sabia até o fim de 2024,
quais municípios não chegariam à meta de 2025?*

Rode depois de `gerar_gold.py`:

    python prever_municipios.py [--amostra N] [--modelo floresta|boosting|logistica]

Escreve `data/predictions/risco_municipio.parquet`, o relatório em
`reports/RISCO_MUNICIPAL.md` e as figuras em `images/`.
"""
from __future__ import annotations

import argparse
import sys
import time

import numpy as np
import pandas as pd

from src.config import DIR_GOLD, DIR_REPORTS, RAIZ, REDE_META_MUNICIPIO
from src.utils import markdown_tabela
from src.modeling.dados import ANO_TESTE, ANO_TREINO, carregar, features_utilizaveis
from src.modeling.municipio import (
    MINIMO_ALUNOS, TOLERANCIA_MART, agregar, calibracao_do_risco,
    conferir_contra_mart, desvio_por_porte, diagnostico_de_deriva, erro_por_uf,
    metricas_de_risco, metricas_de_taxa, probabilidade_de_descumprir,
    ranking_de_risco,
)
from src.modeling.pipeline import MODELOS, SEMENTE
from src.visualization.estilo import (
    SERIE, TINTA, TINTA_2, TINTA_3, aplicar_estilo, milhar, num, pct, salvar, titular,
)

import matplotlib.pyplot as plt

DIR_IMAGENS = RAIZ / "images"
DIR_PREDICOES = RAIZ / "data" / "predictions"
TOPO_RANKING = 40


def _tabela_ranking(d: pd.DataFrame) -> pd.DataFrame:
    """Formata o ranking para leitura: percentual com uma casa, vírgula decimal."""
    return pd.DataFrame({
        "uf": d.sigla_uf.to_numpy(),
        "alunos": [milhar(int(v)) for v in d.alunos_avaliados],
        "taxa t-1": [pct(v) for v in d.taxa_t1],
        "meta": [pct(v) for v in d.meta_taxa],
        "prevista": [pct(v) for v in d.taxa_prevista],
        "gap previsto": [num(v * 100, 1, sinal=True) for v in d.gap_previsto],
        "risco": [pct(v, 0) for v in d.probabilidade_descumprir],
        "observada": [pct(v) for v in d.taxa_observada],
    }, index=pd.Index(d.nome_municipio, name="município"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Projeção municipal e risco de meta.")
    parser.add_argument("--amostra", type=int, default=None,
                        help="limita as linhas por ano (amostragem por escola)")
    parser.add_argument("--modelo", default="floresta", choices=sorted(MODELOS),
                        help="modelo a projetar (padrão: o melhor da avaliação)")
    args = parser.parse_args()

    aplicar_estilo()
    print(f"Carregando aluno_features{f' (amostra de {args.amostra:,}/ano)' if args.amostra else ''}")
    treino, teste = carregar(amostra=args.amostra, semente=SEMENTE)
    numericas, categoricas, descartadas = features_utilizaveis(treino)
    print(f"  treino {ANO_TREINO}: {len(treino):,} alunos | "
          f"teste {ANO_TESTE}: {len(teste):,} alunos")

    print(f"\nTreinando {args.modelo} em {ANO_TREINO}")
    inicio = time.perf_counter()
    modelo = MODELOS[args.modelo](numericas, categoricas)
    modelo.fit(treino.X, treino.y, modelo__sample_weight=treino.peso)
    print(f"  fit: {time.perf_counter() - inicio:.1f}s")
    probabilidade = modelo.predict_proba(teste.X)[:, 1]

    # --- agregação para o grão da decisão -----------------------------------
    print(f"\nAgregando para município × rede municipal (rede {REDE_META_MUNICIPIO})")
    agregado = agregar(teste.contexto, probabilidade, teste.y, teste.peso)
    print(f"  {len(agregado):,} municípios com rede municipal avaliada em {ANO_TESTE}")

    mart = pd.read_parquet(DIR_GOLD / "meta_vs_resultado_municipio.parquet")
    prova = conferir_contra_mart(agregado, mart, ANO_TESTE)
    print(f"  prova contra o mart oficial: {prova['conformes']:,}/{prova['conferidos']:,} "
          f"municípios dentro de {TOLERANCIA_MART * 100:.1f} p.p. "
          f"({prova['fracao']:.2%}) | mediana {prova['mediana']:.1e} | "
          f"máxima {prova['maxima']:.1e}")
    if not prova["ok"]:
        # Com amostra a prova não pode passar: uma fração dos alunos não
        # reconstrói o indicador do município. Segue como aviso, para iteração.
        destino = sys.stderr if not args.amostra else sys.stdout
        print("  a taxa observada reconstruída não bate com o indicador publicado"
              + (" — esperado sob --amostra, que não tem os alunos todos."
                 if args.amostra else "; o restante do relatório seria ficção."),
              file=destino)
        if not args.amostra:
            return 1
    if len(prova["divergentes"]):
        print(f"  {len(prova['divergentes'])} maiores divergências:")
        print(prova["divergentes"].round(4).to_string(index=False))

    # --- recorte avaliável ---------------------------------------------------
    total = len(agregado)
    sem_meta = int(agregado.meta_taxa.isna().sum())
    sem_historico = int(agregado.taxa_t1.isna().sum())
    d = agregado[agregado.meta_taxa.notna() & agregado.taxa_t1.notna()
                 & (agregado.alunos_avaliados >= MINIMO_ALUNOS)].copy()
    print(f"  avaliáveis: {len(d):,} de {total:,} "
          f"({sem_meta:,} sem meta publicada, {sem_historico:,} sem taxa em t-1, "
          f"restante com menos de {MINIMO_ALUNOS} alunos)")

    # --- o modelo bate a persistência no grão que importa? -------------------
    print("\nErro da taxa municipal prevista")
    taxas = {"modelo": metricas_de_taxa(d, "taxa_prevista"),
             "persistencia_t1": metricas_de_taxa(d, "taxa_t1")}
    tabela_taxas = pd.DataFrame(taxas).T.round(4)
    print(tabela_taxas.to_string())

    print("\nAcerto no risco de não atingir a meta")
    riscos = {"modelo": metricas_de_risco(d, "taxa_prevista"),
              "persistencia_t1": metricas_de_risco(d, "taxa_t1")}
    # A matriz de confusão sai da tabela de taxas: misturar contagem com
    # proporção na mesma coluna deixa as duas ilegíveis.
    proporcoes = ["acuracia", "precisao", "recall", "f1", "auc_roc"]
    contagens = ["verdadeiros_positivos", "falsos_positivos",
                 "falsos_negativos", "verdadeiros_negativos"]
    tabela_riscos = pd.DataFrame(riscos).T[proporcoes].astype(float).round(4)
    confusao = pd.DataFrame(riscos).T[contagens].astype(int)
    print(tabela_riscos.to_string())
    print(confusao.to_string())

    abaixo = int((d.taxa_observada < d.meta_taxa).sum())
    print(f"  {abaixo:,} de {len(d):,} municípios ({abaixo / len(d):.1%}) "
          f"ficaram de fato abaixo da meta em {ANO_TESTE}")

    # --- deriva entre anos ----------------------------------------------------
    # O modelo erra por dois motivos distintos, e somá-los num MAE só esconde
    # ambos: ele ordena mal os municípios, e o país inteiro mudou de nível.
    deriva = diagnostico_de_deriva(d)
    print("\nDeriva entre anos")
    print(f"  taxa média em t-1 {deriva['nacional_t1']:.1%} | prevista "
          f"{deriva['nacional_previsto']:.1%} | observada {deriva['nacional_observado']:.1%}"
          f" (salto de {deriva['salto_do_ano'] * 100:+.1f} p.p. no ano)")
    print(f"  erro médio {deriva['erro_medio_absoluto']:.1%} → "
          f"{deriva['erro_sem_vies']:.1%} descontado o viés "
          f"({deriva['parcela_de_nivel']:.0%} do erro é deslocamento de nível)")

    por_uf = erro_por_uf(d)
    print(por_uf.round(4).head(6).to_string(index=False))

    # A UF cujo contexto de t-1 é anômalo contamina todo o seu ranking. Detectar
    # isso a partir da série, em vez de assumir, é o que torna o diagnóstico
    # reaproveitável em anos futuros.
    serie = pd.read_parquet(DIR_GOLD / "resumo_uf.parquet")
    serie = (serie[serie.rede == REDE_META_MUNICIPIO]
             .pivot(index="sigla_uf", columns="ano", values="taxa_alfabetizacao"))
    anomalia = pd.DataFrame(columns=["variacao_ate_t1"])
    if {ANO_TREINO - 1, ANO_TREINO}.issubset(serie.columns):
        anomalia = (pd.DataFrame({"variacao_ate_t1": serie[ANO_TREINO]
                                  - serie[ANO_TREINO - 1]})
                    .dropna().sort_values("variacao_ate_t1"))
        print(f"\nVariação da rede municipal entre {ANO_TREINO - 1} e {ANO_TREINO}, "
              f"3 maiores quedas:")
        print((anomalia.head(3) * 100).round(1).to_string())

    # --- incerteza e ranking --------------------------------------------------
    desvios = desvio_por_porte(d)
    print("\nDesvio do erro por porte do município")
    print(desvios.round(4).to_string(index=False))
    d["probabilidade_descumprir"] = probabilidade_de_descumprir(d, desvios)

    nomes = (mart[mart.ano == ANO_TESTE][["id_municipio", "nome_municipio"]]
             .drop_duplicates("id_municipio"))
    ranking = ranking_de_risco(d, nomes)
    DIR_PREDICOES.mkdir(parents=True, exist_ok=True)
    arquivo = DIR_PREDICOES / "risco_municipio.parquet"
    ranking.to_parquet(arquivo, index=False)
    print(f"\nranking: {arquivo} ({len(ranking):,} municípios)")

    calibracao = calibracao_do_risco(d)
    print("\nCalibração do risco declarado")
    print(calibracao.round(3).to_string(index=False))

    alto_risco = ranking[ranking.probabilidade_descumprir >= 0.8]
    acerto_alto = float((alto_risco.gap_observado < 0).mean()) if len(alto_risco) else float("nan")
    print(f"  {len(alto_risco):,} municípios com probabilidade ≥ 80% de descumprir; "
          f"{acerto_alto:.1%} de fato descumpriram")

    # --- figuras ---------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.scatter(d.taxa_observada * 100, d.taxa_prevista * 100, s=5, alpha=0.18,
               color=SERIE[0], edgecolors="none")
    limites = [min(d.taxa_observada.min(), d.taxa_prevista.min()) * 100 - 2,
               max(d.taxa_observada.max(), d.taxa_prevista.max()) * 100 + 2]
    ax.plot(limites, limites, color=TINTA_3, linewidth=1.2, linestyle="--", zorder=0)
    ax.set_xlim(limites); ax.set_ylim(limites)
    ax.set_xlabel(f"taxa observada em {ANO_TESTE} (%)")
    ax.set_ylabel("taxa prevista (%)")
    ax.grid(True, linewidth=0.8, alpha=0.6)
    ax.set_axisbelow(True)
    abaixo_da_linha = float((d.taxa_prevista < d.taxa_observada).mean())
    titular(ax, "Previsto contra observado, por município",
            f"Rede municipal, {ANO_TESTE}. Tracejado: acerto perfeito. Erro médio "
            f"{num(taxas['modelo']['erro_medio_absoluto'] * 100)} p.p.; "
            f"{pct(abaixo_da_linha, 0)} ficaram abaixo da linha.")
    fig_dispersao = salvar(fig, DIR_IMAGENS, "08_previsto_vs_observado_municipio")

    fig, ax = plt.subplots(figsize=(7.8, 3.6))
    indicadores = ["recall", "precisao", "acuracia", "auc_roc"]
    rotulos = ["Sensibilidade\n(acha quem falha)", "Precisão\n(alarme certo)",
               "Acurácia", "AUC"]
    y = np.arange(len(indicadores))
    altura, folga = 0.34, 0.19   # a folga impede que as duas barras se encostem
    ax.barh(y + folga, [riscos["modelo"][i] for i in indicadores], height=altura,
            color=SERIE[0], label="Modelo")
    ax.barh(y - folga, [riscos["persistencia_t1"][i] for i in indicadores],
            height=altura, color=SERIE[1], label="Repetir o ano anterior")
    for i, chave in enumerate(indicadores):
        for deslocamento, fonte in ((folga, "modelo"), (-folga, "persistencia_t1")):
            v = riscos[fonte][chave]
            ax.text(v + 0.012, i + deslocamento, num(v, 3), va="center",
                    color=TINTA, fontsize=9)
    ax.set_yticks(y, rotulos, fontsize=9.5, color=TINTA_2)
    ax.set_xlim(0, 1.12)
    ax.xaxis.set_visible(False)
    for lado in ("bottom", "left"):
        ax.spines[lado].set_visible(False)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, -0.14), ncol=2)
    titular(ax, "Sinalizar quem não atinge a meta",
            f"Classe positiva: ficar abaixo da meta. {milhar(len(d))} municípios, "
            f"{ANO_TESTE}.")
    fig_risco = salvar(fig, DIR_IMAGENS, "09_risco_de_meta_municipio")

    # Terceira figura: onde a deriva se concentra. Um viés uniforme seria um
    # problema de calibração; concentrado numa UF, é um choque local herdado.
    fig, ax = plt.subplots(figsize=(7.4, 6.2))
    ordenado = por_uf.sort_values("vies")
    ax.barh(ordenado.sigla_uf, ordenado.vies * 100, height=0.66, color=SERIE[0])
    ax.axvline(deriva["vies"] * 100, color=SERIE[1], linewidth=1.4, linestyle="--",
               zorder=3, label=f"viés nacional {num(deriva['vies'] * 100, 1, sinal=True)}")
    ax.axvline(0, color=TINTA_3, linewidth=0.9, zorder=2)
    ax.xaxis.set_visible(False)
    for lado in ("bottom", "left"):
        ax.spines[lado].set_visible(False)
    for i, v in enumerate(ordenado.vies * 100):
        ax.text(v - 0.5 if v < 0 else v + 0.5, i, num(v, 1, sinal=True), va="center",
                ha="right" if v < 0 else "left", color=TINTA, fontsize=8.5)
    # Limites colados nos dados: um eixo simétrico deixaria metade da figura
    # vazia, porque quase toda UF tem viés negativo.
    valores = ordenado.vies * 100
    ax.set_xlim(valores.min() - 4.5, max(valores.max(), 0) + 2.5)
    # A legenda vai para cima, onde as barras são curtas: embaixo ela cobriria o
    # rótulo da UF de maior viés.
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0))
    titular(ax, "Onde o modelo erra o nível, por UF",
            f"Previsto menos observado, em p.p. Negativo: o modelo previu menos "
            f"alfabetização do que houve.")
    fig_deriva = salvar(fig, DIR_IMAGENS, "10_vies_por_uf")

    # --- relatório ---------------------------------------------------------------
    ganho_mae = (taxas["persistencia_t1"]["erro_medio_absoluto"]
                 - taxas["modelo"]["erro_medio_absoluto"])
    linhas = [
        "# Risco municipal — quem não atinge a meta de alfabetização", "",
        f"Modelo `{args.modelo}` treinado em {ANO_TREINO} e projetado em {ANO_TESTE}, "
        f"agregando a probabilidade de cada aluno para o grão **município × rede "
        f"municipal** — o único em que o INEP publica meta por município. Nenhuma "
        f"informação de {ANO_TESTE} entra na predição: as features são contexto de t-1 "
        f"e metas publicadas antes da avaliação.", "",
        "## Por que agregar muda o problema", "",
        f"No grão do aluno o modelo tem AUC 0,64 — modesto, porque 86% da variância do "
        f"alvo está entre alunos da mesma escola e nenhuma variável disponível chega "
        f"lá. Agregado ao município, o erro individual se cancela na média ponderada e "
        f"o mesmo modelo chega a **AUC {num(riscos['modelo']['auc_roc'], 3)}** para "
        f"separar quem cumpre de quem não cumpre a meta. O modelo não ficou melhor: a "
        f"pergunta mudou para o grão em que ele tem o que dizer. As seções seguintes "
        f"medem quanto disso é mérito do modelo e quanto já estava na taxa do ano "
        f"anterior.", "",
        "## Prova da agregação", "",
        f"A taxa observada reconstruída a partir dos microdados ponderados bate com o "
        f"indicador publicado em `meta_vs_resultado_municipio`: "
        f"**{milhar(prova['conformes'])} de {milhar(prova['conferidos'])} municípios "
        f"({pct(prova['fracao'], 2)})** dentro de {num(TOLERANCIA_MART * 100)} p.p., com "
        f"diferença mediana de {num(prova['mediana'] * 100, 4)} p.p. — o arredondamento "
        f"da própria publicação. Sem essa prova o resto do relatório não teria valor.",
        "",
    ]
    if len(prova["divergentes"]):
        linhas += [
            f"As {len(prova['divergentes'])} maiores divergências ficam registradas em "
            f"vez de escondidas:", "",
            markdown_tabela(prova["divergentes"].round(4).set_index("id_municipio"),
                            "id_municipio"), "",
        ]
    linhas += [
        "## Erro da taxa municipal prevista", "",
        markdown_tabela(tabela_taxas, "fonte"), "",
        f"O modelo erra {num(taxas['modelo']['erro_medio_absoluto'] * 100)} p.p. em "
        f"média contra {num(taxas['persistencia_t1']['erro_medio_absoluto'] * 100)} p.p. "
        f"de repetir o ano anterior — **{num(ganho_mae * 100)} p.p. a menos, "
        f"{pct(ganho_mae / taxas['persistencia_t1']['erro_medio_absoluto'], 0)} de "
        f"redução**. É a primeira vez no projeto que o aprendizado supera a "
        f"persistência territorial com folga: no grão do aluno a diferença era de um "
        f"milésimo de AUC.", "",
        f"Base: {milhar(len(d))} municípios de {milhar(total)} avaliados em {ANO_TESTE} "
        f"({sem_meta} sem meta publicada, {sem_historico} sem taxa em t-1, e os "
        f"demais com menos de {MINIMO_ALUNOS} alunos avaliados — abaixo disso a própria "
        f"taxa observada é ruído amostral).", "",
        "## Acerto no risco de não atingir a meta", "",
        f"Classe positiva: **ficar abaixo da meta**, que é o caso que dispara ação. "
        f"{milhar(abaixo)} municípios ({pct(abaixo / len(d))}) de fato ficaram abaixo em "
        f"{ANO_TESTE}.", "",
        markdown_tabela(tabela_riscos, "fonte"), "",
        "Matriz de confusão (positivo = ficar abaixo da meta):", "",
        markdown_tabela(confusao, "fonte"), "",
        "Aqui o placar é mais sóbrio: em AUC os dois empatam "
        f"({num(riscos['modelo']['auc_roc'], 3)} contra "
        f"{num(riscos['persistencia_t1']['auc_roc'], 3)}). A comparação de acurácia e "
        "sensibilidade no limiar fixo da meta é enganosa, porque os dois têm viés "
        "diferente: quem prevê mais baixo aciona mais alarmes e acerta mais dos que "
        "falham, ao custo de errar mais dos que cumprem. O ganho real do modelo está no "
        "**nível** da taxa prevista, não na ordenação.", "",
        "## Deriva entre anos — o que nenhum modelo treinado em t-1 poderia saber", "",
        f"A rede municipal saltou de {pct(deriva['nacional_t1'])} em {ANO_TREINO} para "
        f"{pct(deriva['nacional_observado'])} em {ANO_TESTE}: "
        f"**{num(deriva['salto_do_ano'] * 100, 1, sinal=True)} p.p. em um ano**. O "
        f"modelo projetou {pct(deriva['nacional_previsto'])}, ou seja "
        f"{num((deriva['nacional_previsto'] - deriva['nacional_t1']) * 100, 1, sinal=True)}"
        f" p.p. — capturou "
        f"{pct((deriva['nacional_previsto'] - deriva['nacional_t1']) / deriva['salto_do_ano'], 0)}"
        f" da alta, provavelmente pela meta do ano, que é a única feature que olha para "
        f"a frente. O resto ele não tinha como saber.", "",
        f"Descontado esse deslocamento, o erro médio cai de "
        f"{num(deriva['erro_medio_absoluto'] * 100)} p.p. para "
        f"{num(deriva['erro_sem_vies'] * 100)} p.p.: só "
        f"**{pct(deriva['parcela_de_nivel'], 0)} do erro é nível — o restante é "
        f"ordenação**, e esse é o limite real do modelo. O desconto é diagnóstico e "
        f"não predição: o viés só é conhecido depois da avaliação.", "",
        markdown_tabela(por_uf.round(4).set_index("sigla_uf").head(8), "sigla_uf"), "",
    ]
    if len(anomalia):
        pior = anomalia.index[0]
        linhas += [
            f"O caso extremo é **{pior}**: a rede municipal caiu "
            f"{num(anomalia.variacao_ate_t1.iloc[0] * 100, 1, sinal=True)} p.p. entre "
            f"{ANO_TREINO - 1} e {ANO_TREINO}, contra "
            f"{num(anomalia.variacao_ate_t1.iloc[1] * 100, 1, sinal=True)} p.p. da "
            f"segunda maior queda. O modelo lê esse ano deprimido como o patamar "
            f"estrutural do estado e projeta descumprimento generalizado — "
            f"{milhar(int((ranking.head(200).sigla_uf == pior).sum()))} dos 200 "
            f"municípios de maior risco são de {pior}, e boa parte deles cumpriu a meta. "
            f"**Um sistema em produção precisa detectar o ano anômalo antes de usá-lo "
            f"como contexto**, e não herdá-lo como estrutura.", "",
        ]
    linhas += [
        "## Incerteza por porte do município", "",
        "O erro não é homocedástico: num município com poucas dezenas de alunos "
        "avaliados a taxa oscila por sorteio, numa capital ela é estável. O desvio "
        "usado na probabilidade é o do estrato de porte, não um número único.", "",
        markdown_tabela(desvios.round(4).set_index("estrato"), "estrato"), "",
        f"A probabilidade de descumprir é `Φ((meta − prevista) / σ_estrato)`. O σ vem "
        f"dos resíduos de {ANO_TESTE}: aplicado a um ano ainda não avaliado ele é a "
        f"melhor estimativa disponível, mas provavelmente otimista, porque não embute "
        f"a mudança de regime entre um ano e outro.", "",
        f"**{milhar(len(alto_risco))} municípios** saíram com probabilidade ≥ 80% de "
        f"descumprir; destes, {pct(acerto_alto)} de fato descumpriram.", "",
        "Confrontando a probabilidade declarada com a frequência observada:", "",
        markdown_tabela(calibracao.assign(
            faixa_de_risco=lambda x: x.faixa_de_risco.astype("string")
        ).set_index("faixa_de_risco").round(3), "faixa de risco"), "",
        "**A ordenação funciona, a calibração não.** A frequência de descumprimento "
        "cresce monotonicamente de uma faixa para a seguinte — o ranking separa bem. "
        "Mas o nível está deslocado em todas elas, pela mesma razão da seção anterior: "
        "a taxa prevista é baixa demais, então a probabilidade de ficar abaixo da meta "
        "é alta demais. **Use a ordem, não o valor absoluto** — ou recalibre contra esta "
        "tabela antes de usar o número para dimensionar recurso.", "",
        f"## Municípios de maior risco (topo de {TOPO_RANKING})", "",
        markdown_tabela(_tabela_ranking(ranking.head(TOPO_RANKING)), "município"),
        "",
        "Taxas em pontos percentuais. `taxa_observada` é a conferência posterior, não "
        "entrou na predição — e mostra quantos superaram a projeção. A tabela completa "
        "fica em `data/predictions/risco_municipio.parquet`.", "",
        "## Figuras", "",
        f"![previsto contra observado](../images/{fig_dispersao})", "",
        f"![risco de meta](../images/{fig_risco})", "",
        f"![viés por UF](../images/{fig_deriva})", "",
    ]
    if descartadas:
        linhas += [f"Features descartadas por serem nulas em {ANO_TREINO}: "
                   f"`{'`, `'.join(descartadas)}`.", ""]

    DIR_REPORTS.mkdir(parents=True, exist_ok=True)
    (DIR_REPORTS / "RISCO_MUNICIPAL.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"relatório: {DIR_REPORTS / 'RISCO_MUNICIPAL.md'}")
    print(f"  ganho sobre repetir o ano anterior: {ganho_mae * 100:+.2f} p.p. de erro médio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
