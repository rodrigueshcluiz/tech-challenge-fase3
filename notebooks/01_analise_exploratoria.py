"""Análise exploratória da base de alfabetização.

Script no formato de células (`# %%`): abre como notebook no VS Code ou no
Jupyter e roda como script comum. Fica versionável em texto, sem saída embutida.

    python notebooks/01_analise_exploratoria.py

Gera as figuras em `images/` e o relatório em `reports/EDA.md`.

A pergunta que organiza tudo aqui é uma só: **onde vive a variação do
alfabetizado?** A resposta determina o que o modelo pode e não pode aprender, e
por isso vem antes de qualquer decisão de modelagem.
"""
# %%
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DIR_GOLD, DIR_REPORTS, RAIZ, REDE_META_UF
from src.visualization.estilo import (
    AZUL_ESCURO, SERIE, TINTA, TINTA_3, aplicar_estilo, eixo_decimal, milhar, num, pct, salvar, titular,
)

import matplotlib.pyplot as plt

aplicar_estilo()
DIR_IMAGENS = RAIZ / "images"
MIN_ALUNOS_MUNICIPIO = 30   # abaixo disso a taxa do município é ruído amostral
MIN_ALUNOS_ESCOLA = 20

alunos = pd.read_parquet(DIR_GOLD / "aluno_features.parquet")
resumo_uf = pd.read_parquet(DIR_GOLD / "resumo_uf.parquet")
ANO = int(alunos.ano.max())
achados: list[str] = []


def ponderada(g: pd.DataFrame) -> float:
    """Taxa oficial: ponderada pelo peso amostral, nunca média simples."""
    return float(np.average(g.alfabetizado, weights=g.peso_amostral))


# %% [markdown]
# ## 1. O alvo
#
# Distribuição do alvo por ano e rede, sempre ponderada pelo peso amostral —
# média simples dos alunos não reproduz o indicador oficial.

# %%
por_ano_rede = (alunos.groupby(["ano", "rede_label"])
                .apply(lambda g: pd.Series({"alunos": len(g), "taxa": ponderada(g)}),
                       include_groups=False))
print(por_ano_rede.round(4).to_string())

taxa_24, taxa_25 = (ponderada(alunos[alunos.ano == a]) for a in (2024, 2025))
achados.append(
    f"O alvo é razoavelmente equilibrado: {pct(ponderada(alunos))} de alfabetizados "
    f"na base inteira, sem necessidade de reamostragem.")

# %% [markdown]
# ## 2. O salto de 2024 para 2025 é real ou composição?
#
# A cobertura da avaliação cresce a cada ano (24 UFs em 2023, 25 em 2024, 27 em
# 2025). Um salto no indicador nacional pode ser entrada de território novo em
# vez de melhora. Fixar o conjunto de UFs separa uma coisa da outra.

# %%
ufs_comuns = set(alunos[alunos.ano == 2024].sigla_uf) & set(alunos[alunos.ano == 2025].sigla_uf)
fixo = alunos[alunos.sigla_uf.isin(ufs_comuns)]
fixo_24, fixo_25 = (ponderada(fixo[fixo.ano == a]) for a in (2024, 2025))
print(f"todas as UFs : {taxa_24:.2%} -> {taxa_25:.2%}")
print(f"UFs comuns   : {fixo_24:.2%} -> {fixo_25:.2%}  ({len(ufs_comuns)} UFs)")
achados.append(
    f"O salto de {pct(fixo_24)} para {pct(fixo_25)} entre 2024 e 2025 é **real**, não "
    f"efeito de composição: com o conjunto de UFs fixo em {len(ufs_comuns)}, a diferença "
    f"se mantém em {num((fixo_25 - fixo_24) * 100, 1, sinal=True)} p.p.")

# %% [markdown]
# ## 3. Onde vive a variação — a pergunta central
#
# Decompor a variância do alvo pelos níveis territoriais aninhados diz quanto
# de tudo que acontece é explicável por cada nível. É o teto do modelo, medido
# antes de treinar qualquer coisa.

# %%
ano_atual = alunos[alunos.ano == ANO]
variancia_total = float(ano_atual.alfabetizado.var())


def variancia_entre(chave: str, minimo: int) -> float:
    """Variância da média do grupo em torno da média geral, ponderada pelo tamanho."""
    grupos = ano_atual.groupby(chave).alfabetizado.agg(["mean", "size"])
    grupos = grupos[grupos["size"] >= minimo]
    return float(np.average((grupos["mean"] - ano_atual.alfabetizado.mean()) ** 2,
                            weights=grupos["size"]))


niveis = {
    "UF": variancia_entre("sigla_uf", 100),
    "Município": variancia_entre("id_municipio", MIN_ALUNOS_MUNICIPIO),
    "Escola": variancia_entre("id_escola_ano", MIN_ALUNOS_ESCOLA),
}
proporcoes = {k: v / variancia_total for k, v in niveis.items()}
for nome, p in proporcoes.items():
    print(f"{nome:10s} explica {p:6.1%} da variância do alvo")

fig, ax = plt.subplots(figsize=(7.2, 2.9))
nomes = list(proporcoes)
valores = [proporcoes[n] * 100 for n in nomes]
barras = ax.barh(nomes, valores, height=0.58, color=SERIE[0])
for nome, valor in zip(nomes, valores):
    ax.text(valor + 0.5, nome, f"{num(valor)}%", va="center", color=TINTA, fontsize=10.5)
ax.set_xlim(0, max(valores) * 1.35)
ax.invert_yaxis()
ax.set_xlabel("% da variância do alfabetizado explicada")
ax.xaxis.set_visible(False)
ax.spines["bottom"].set_visible(False)
titular(ax, "A escola explica mais que o município e a UF somados",
        f"Decomposição da variância do alvo, {ANO}.")
fig_variancia = salvar(fig, DIR_IMAGENS, "01_variancia_por_nivel")

achados.append(
    f"**A escola é o nível territorial mais informativo**: explica {pct(proporcoes['Escola'])} "
    f"da variância do alvo, contra {pct(proporcoes['Município'])} do município e "
    f"{pct(proporcoes['UF'])} da UF. E é exatamente o nível que não podemos enriquecer — "
    f"o código de escola do INEP é mascarado e resorteado a cada ano.")
achados.append(
    f"Mesmo assim, **{pct(1 - proporcoes['Escola'], 0)} da variação está entre alunos da mesma "
    f"escola**, e sobre isso não há nenhuma variável na fonte: os microdados não trazem "
    f"sexo, idade, raça nem dados do domicílio. Esse é o teto do modelo, e ele vem da "
    f"fonte, não da modelagem.")

# %% [markdown]
# ## 4. Quanto duas escolas do mesmo município diferem
#
# Se o município fosse uma boa aproximação, escolas dentro dele seriam parecidas.

# %%
escolas = (ano_atual.groupby(["id_municipio", "id_escola_ano"])
           .alfabetizado.agg(["mean", "size"]).reset_index())
escolas = escolas[escolas["size"] >= MIN_ALUNOS_ESCOLA]
com_varias = escolas.groupby("id_municipio").filter(lambda x: len(x) >= 5)
amplitude = (com_varias.groupby("id_municipio")["mean"]
             .agg(["min", "max"]).eval("max - min") * 100)
print(f"{len(amplitude):,} municípios com 5+ escolas | amplitude mediana "
      f"{amplitude.median():.1f} p.p.")

fig, ax = plt.subplots(figsize=(7.2, 3.4))
ax.hist(amplitude, bins=40, color=SERIE[0], edgecolor="none")
ax.axvline(amplitude.median(), color=AZUL_ESCURO, linewidth=2)
ax.text(amplitude.median() + 1.5, ax.get_ylim()[1] * 0.9,
        f"mediana {num(amplitude.median(), 0)} p.p.", color=TINTA, fontsize=10)
ax.set_xlabel("diferença entre a melhor e a pior escola do município (p.p.)")
ax.set_ylabel("municípios")
ax.grid(axis="y")
ax.set_axisbelow(True)
titular(ax, "Dentro do mesmo município, escolas são muito diferentes",
        f"{milhar(len(amplitude))} municípios com 5 ou mais escolas avaliadas, {ANO}.")
fig_escolas = salvar(fig, DIR_IMAGENS, "02_amplitude_entre_escolas")

achados.append(
    f"No município mediano, a melhor e a pior escola diferem **{num(amplitude.median(), 0)} "
    f"pontos percentuais**. Tratar o município como unidade homogênea apaga essa diferença.")

# %% [markdown]
# ## 5. O paradoxo do INSE
#
# O nível socioeconômico é a variável que a literatura aponta como mais
# associada a desempenho. Na base, a correlação com o alvo é quase nula. A
# explicação não é que o INSE não importa — é o grão em que ele existe.

# %%
com_inse = ano_atual.dropna(subset=["mun_inse_media"])
cor_aluno = float(com_inse.mun_inse_media.corr(com_inse.alfabetizado))

municipios = (com_inse.groupby(["sigla_uf", "id_municipio"])
              .agg(taxa=("alfabetizado", "mean"), inse=("mun_inse_media", "first"),
                   n=("alfabetizado", "size")))
municipios = municipios[municipios.n >= MIN_ALUNOS_MUNICIPIO]
cor_municipio = float(municipios.inse.corr(municipios.taxa))
dentro_uf = (municipios.groupby("sigla_uf")
             .apply(lambda g: g.inse.corr(g.taxa) if len(g) >= 20 else np.nan,
                    include_groups=False).dropna())
print(f"aluno {cor_aluno:+.3f} | município {cor_municipio:+.3f} | "
      f"dentro da UF (mediana) {dentro_uf.median():+.3f}")

fig, ax = plt.subplots(figsize=(7.2, 4.4))
ax.scatter(municipios.inse, municipios.taxa * 100, s=9, alpha=0.25,
           color=SERIE[0], linewidths=0)
coef = np.polyfit(municipios.inse, municipios.taxa * 100, 1)
eixo = np.linspace(municipios.inse.min(), municipios.inse.max(), 50)
ax.plot(eixo, np.polyval(coef, eixo), color=AZUL_ESCURO, linewidth=2)
ax.set_xlabel("INSE médio do município (2023)")
eixo_decimal(ax, 1, "x")
ax.set_ylabel("% de alunos alfabetizados")
ax.grid(axis="y")
ax.set_axisbelow(True)
titular(ax, "O INSE importa — no grão em que ele existe",
        f"{milhar(len(municipios))} municípios com 30+ alunos, {ANO}. Correlação "
        f"{num(cor_municipio, 2, sinal=True)} aqui, contra {num(cor_aluno, 2, sinal=True)} "
        f"no grão do aluno.")
fig_inse = salvar(fig, DIR_IMAGENS, "03_inse_municipio")

achados.append(
    f"**O INSE parece irrelevante e não é.** No grão do aluno a correlação é "
    f"{num(cor_aluno, 2, sinal=True)}; no grão do município sobe para "
    f"{num(cor_municipio, 2, sinal=True)}, e dentro da mesma UF fica em "
    f"{num(dentro_uf.median(), 2, sinal=True)}. A diluição é consequência direta da "
    f"decomposição acima: uma variável constante dentro do município não consegue explicar "
    f"a variação que acontece dentro dele.")

# %% [markdown]
# ## 6. Quais variáveis discriminam, no grão em que vivem
#
# Correlacionar feature municipal com alvo de aluno subestima tudo. A leitura
# honesta é no grão do município.

# %%
features = ["mun_taxa_publica_t1", "mun_nivel_t1", "mun_meta_ano",
            "mun_abandono_iniciais_t1", "mun_inse_pct_vulneravel", "mun_inse_media",
            "mun_alunos_avaliados", "mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1",
            "mun_reprovacao_2ano_t1"]
por_municipio = ano_atual.groupby("id_municipio").agg(
    taxa=("alfabetizado", "mean"), n=("alfabetizado", "size"),
    **{c: (c, "first") for c in features})
por_municipio = por_municipio[por_municipio.n >= MIN_ALUNOS_MUNICIPIO]
correlacoes = por_municipio[features].corrwith(por_municipio.taxa).sort_values()
print(correlacoes.round(3).to_string())

rotulos = {
    "mun_taxa_publica_t1": "Taxa do município em t-1",
    "mun_nivel_t1": "Nível de alfabetização em t-1",
    "mun_meta_ano": "Meta oficial do ano",
    "mun_abandono_iniciais_t1": "Abandono nos anos iniciais (t-1)",
    "mun_inse_pct_vulneravel": "% em estrato socioeconômico baixo",
    "mun_inse_media": "INSE médio",
    "mun_alunos_avaliados": "Alunos avaliados no município",
    "mun_aprovacao_1ano_t1": "Aprovação no 1º ano (t-1)",
    "mun_aprovacao_2ano_t1": "Aprovação no 2º ano (t-1)",
    "mun_reprovacao_2ano_t1": "Reprovação no 2º ano (t-1)",
}
fig, ax = plt.subplots(figsize=(7.6, 4.6))
cores = [SERIE[1] if v < 0 else SERIE[0] for v in correlacoes]
ax.barh([rotulos[i] for i in correlacoes.index], correlacoes.values,
        height=0.62, color=cores)
for i, v in enumerate(correlacoes.values):
    ax.text(v + (0.02 if v >= 0 else -0.02), i, num(v, 2, sinal=True), va="center",
            ha="left" if v >= 0 else "right", color=TINTA, fontsize=9.5)
ax.axvline(0, color=TINTA_3, linewidth=0.8)
ax.spines["left"].set_visible(False)
ax.set_xlim(-0.45, 0.9)
ax.xaxis.set_visible(False)
ax.spines["bottom"].set_visible(False)
titular(ax, "Correlação com a taxa do município",
        f"Grão de município, {ANO}. Azul, associação positiva; laranja, negativa.")
fig_correlacoes = salvar(fig, DIR_IMAGENS, "04_correlacoes_municipio")

achados.append(
    f"No grão certo as features funcionam: a taxa do ano anterior correlaciona "
    f"{num(correlacoes['mun_taxa_publica_t1'], 2, sinal=True)} e o abandono nos anos "
    f"iniciais {num(correlacoes['mun_abandono_iniciais_t1'], 2, sinal=True)}. "
    f"**Persistência territorial é o sinal "
    f"dominante** — o melhor preditor de onde um município estará é onde ele estava.")
achados.append(
    f"A reprovação no 2º ano é inútil como feature: a aprovação média no município é "
    f"{num(por_municipio.mun_aprovacao_2ano_t1.mean())}% e a correlação com o alvo é "
    f"{num(correlacoes['mun_reprovacao_2ano_t1'], 2, sinal=True)}. Progressão continuada faz "
    f"a variável quase não variar.")

# %% [markdown]
# ## 7. Trajetória e desigualdade regional

# %%
serie_uf = (resumo_uf[resumo_uf.rede == REDE_META_UF]
            .groupby("ano", as_index=False).taxa_alfabetizacao.mean())
por_regiao = (ano_atual.groupby("regiao")
              .apply(lambda g: ponderada(g), include_groups=False)
              .sort_values() * 100)
print(por_regiao.round(1).to_string())

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 3.8))
ax1.plot(serie_uf.ano, serie_uf.taxa_alfabetizacao * 100, color=SERIE[0], marker="o")
for _, r in serie_uf.iterrows():
    # O primeiro ponto encosta na borda: alinha à esquerda em vez de centralizar.
    ax1.text(r.ano, r.taxa_alfabetizacao * 100 + 1.8, f"{num(r.taxa_alfabetizacao * 100)}%",
             ha="left" if r.ano == serie_uf.ano.min() else "center", color=TINTA, fontsize=10)
ax1.set_xticks(serie_uf.ano.tolist())
ax1.set_ylim(45, 75)
ax1.grid(axis="y")
ax1.set_axisbelow(True)
ax1.yaxis.set_visible(False)
titular(ax1, "Rede pública, média das UFs", "Meta oficial para 2030: 80%.")

barras = ax2.barh(por_regiao.index.tolist(), por_regiao.values, height=0.6, color=SERIE[0])
for nome, valor in zip(por_regiao.index, por_regiao.values):
    ax2.text(valor + 0.8, nome, f"{num(valor)}%", va="center", color=TINTA, fontsize=10)
ax2.set_xlim(0, por_regiao.max() * 1.22)
ax2.xaxis.set_visible(False)
for lado in ("bottom", "left"):
    ax2.spines[lado].set_visible(False)
titular(ax2, f"Alfabetizados por região, {ANO}", "Ponderado pelo peso amostral.")
fig_trajetoria = salvar(fig, DIR_IMAGENS, "05_trajetoria_e_regiao")

achados.append(
    f"A desigualdade regional não segue o eixo econômico esperado: o Sudeste "
    f"({num(por_regiao['Sudeste'])}%) fica **abaixo** do Nordeste "
    f"({num(por_regiao['Nordeste'])}%), e o Centro-Oeste lidera com "
    f"{num(por_regiao['Centro-Oeste'])}%.")

# %% [markdown]
# ## 8. Hipóteses que a exploração sustenta
#
# Cada uma é testável na modelagem.

# %%
hipoteses = [
    ("H1", "Persistência territorial domina",
     "A taxa do município em t-1 é o preditor mais forte disponível "
     f"({num(correlacoes['mun_taxa_publica_t1'], 2, sinal=True)} no grão municipal). Um modelo que só "
     "reproduza a taxa anterior já é um baseline difícil de superar — e é contra ele, "
     "não contra a moeda, que o modelo precisa ser comparado."),
    ("H2", "O teto do modelo é estrutural, não metodológico",
     f"Com {pct(1 - proporcoes['Escola'], 0)} da variância entre alunos da mesma escola e "
     "nenhuma variável de aluno na fonte, nenhum algoritmo alcança discriminação alta. "
     "Métrica alta seria indício de vazamento, não de qualidade."),
    ("H3", "O sinal socioeconômico existe mas está no grão errado",
     f"O INSE correlaciona {num(cor_municipio, 2, sinal=True)} no município e {num(cor_aluno, 2, sinal=True)} no aluno. "
     "Se houvesse INSE por escola, a contribuição seria substancialmente maior — "
     "hipótese não testável com a fonte atual, por causa do código mascarado."),
    ("H4", "Fluxo escolar prediz alfabetização",
     f"Abandono nos anos iniciais em t-1 correlaciona "
     f"{num(correlacoes['mun_abandono_iniciais_t1'], 2, sinal=True)}, enquanto reprovação no 2º ano não "
     "diz nada. A hipótese é que abandono capta fragilidade da rede, e reprovação apenas "
     "reflete política de progressão continuada."),
    ("H5", "A validação precisa ser temporal e agrupada por escola",
     "Treinar em 2024 e testar em 2025 mede generalização de verdade. Dentro do treino, "
     "GroupKFold por escola evita que colegas do mesmo aluno fiquem dos dois lados da "
     "divisão e inflem a métrica."),
]
for codigo, titulo, _ in hipoteses:
    print(f"{codigo}: {titulo}")

# %% [markdown]
# ## 9. Relatório

# %%
figuras = [
    (fig_variancia, "Variância do alvo por nível territorial"),
    (fig_escolas, "Amplitude entre escolas do mesmo município"),
    (fig_inse, "INSE municipal versus taxa de alfabetização"),
    (fig_correlacoes, "Correlação das features no grão do município"),
    (fig_trajetoria, "Trajetória da rede pública e recorte regional"),
]
linhas = [
    "# Análise exploratória — alfabetização no grão do aluno", "",
    f"Base: `aluno_features`, {milhar(len(alunos))} alunos avaliados em 2024 e 2025.",
    f"Gerado por `notebooks/01_analise_exploratoria.py`.", "",
    "## Achados", "",
]
linhas += [f"{i}. {a}" for i, a in enumerate(achados, 1)]
linhas += ["", "## Hipóteses para a modelagem", ""]
for codigo, titulo, corpo in hipoteses:
    linhas += [f"**{codigo} — {titulo}.** {corpo}", ""]
linhas += ["## Figuras", ""]
linhas += [f"![{legenda}](../images/{nome})\n\n*{legenda}*\n" for nome, legenda in figuras]

destino = DIR_REPORTS / "EDA.md"
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text("\n".join(linhas), encoding="utf-8")
print(f"\nrelatório: {destino}")
print(f"figuras:   {DIR_IMAGENS} ({len(figuras)})")
