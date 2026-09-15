"""Verificação da Gold e diagnósticos de leitura.

A checagem decisiva é a de equivalência: recalcular o indicador a partir dos
microdados ponderados e reencontrar o número que o INEP publicou. Se isso bate,
a regra de negócio e toda a cadeia de transformação estão corretas.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    ABA_UF, FAIXAS_ALFABETIZADAS, PUBLICACOES_META, REDE_COMPOSICAO, REDE_MAP,
    REDE_META_UF,
)
from src.preprocessing.silver import compor_escopos
from src.report import Relatorio
from src.utils import puro

GRAOS = {
    "indicador_municipio": ["ano", "id_municipio", "rede"],
    "resumo_uf": ["ano", "sigla_uf", "rede"],
    "meta_vs_resultado_uf": ["ano", "sigla_uf"],
    "meta_vs_resultado_municipio": ["ano", "id_municipio"],
    "metas_uf": ["ano", "sigla_uf"],
    "metas_municipio": ["ano", "id_municipio"],
    "evolucao_uf": ["ano", "sigla_uf", "rede"],
    "evolucao_municipio": ["ano", "id_municipio", "rede"],
    "distribuicao_proficiencia": ["ano", "sigla_uf", "rede", "faixa_pontos", "faixa_label"],
}


def validar_gold(gold, aprovados, alunos_por_dep, raw: Path, rel: Relatorio) -> None:
    rel.etapa("VERIFICAÇÃO — grão, domínios e equivalência com o INEP")

    for mart, chave in GRAOS.items():
        dup = int(gold[mart].duplicated(chave).sum())
        rel.check(f"gold.{mart} — grão único em {' + '.join(chave)}", dup == 0,
                  f"{dup:,} duplicadas")

    # A trajetória de metas e a interseção meta×resultado saem da mesma fonte por
    # caminhos diferentes. Se divergirem, uma das duas está errada — e como a
    # projeção usa a trajetória e o relatório usa a interseção, o projeto passaria
    # a publicar dois números oficiais incompatíveis.
    for trajetoria, interseccao, chave in (
            ("metas_uf", "meta_vs_resultado_uf", "sigla_uf"),
            ("metas_municipio", "meta_vs_resultado_municipio", "id_municipio")):
        conf = (gold[trajetoria][["ano", chave, "meta_taxa"]]
                .merge(gold[interseccao][["ano", chave, "meta_taxa"]],
                       on=["ano", chave], how="inner", suffixes=("_traj", "_inter")))
        conf = conf.dropna(subset=["meta_taxa_traj", "meta_taxa_inter"])
        diverge = int((conf.meta_taxa_traj - conf.meta_taxa_inter).abs().gt(1e-9).sum())
        rel.check(f"{trajetoria} concorda com {interseccao} nos anos em comum",
                  diverge == 0,
                  f"{len(conf):,} chaves conferidas, {diverge:,} divergentes")

    for mart, anos_exigidos in (("metas_uf", {2026}), ("metas_municipio", {2026})):
        anos = set(gold[mart].ano.unique())
        rel.check(f"{mart} cobre anos ainda não avaliados",
                  anos_exigidos.issubset(anos),
                  f"anos {puro(sorted(anos))} — a projeção precisa da meta do ano "
                  f"seguinte ao último avaliado")

    rel.check("meta_vs_resultado_uf não contém grão municipal",
              "id_municipio" not in gold["meta_vs_resultado_uf"].columns)
    rel.check("cada mart de meta usa um único escopo de rede",
              gold["meta_vs_resultado_uf"].rede.nunique() == 1
              and gold["meta_vs_resultado_municipio"].rede.nunique() == 1,
              f"UF: rede {puro(gold['meta_vs_resultado_uf'].rede.unique())} | município: "
              f"rede {puro(gold['meta_vs_resultado_municipio'].rede.unique())}")

    for grao, mart, chave in (("municipio", "indicador_municipio",
                               ["ano", "id_municipio", "rede"]),
                              ("uf", "resumo_uf", ["ano", "sigla_uf", "rede"])):
        esperado = aprovados[aprovados.grao == grao][chave].drop_duplicates()
        rel.check(f"{mart} cobre toda medição aprovada no grão {grao}",
                  len(esperado) == len(gold[mart]),
                  f"{len(esperado):,} chaves na Silver, {len(gold[mart]):,} na Gold")

    for mart in ("indicador_municipio", "resumo_uf", "evolucao_uf", "evolucao_municipio"):
        col = gold[mart].taxa_alfabetizacao.dropna()
        rel.check(f"gold.{mart}.taxa_alfabetizacao em fração 0–1",
                  bool(col.between(0, 1).all()), f"min={col.min():.4f} max={col.max():.4f}")

    for mart in ("meta_vs_resultado_uf", "meta_vs_resultado_municipio"):
        d = gold[mart]
        com = d[d.meta_taxa.notna()]
        rel.check(f"gold.{mart} — gap coerente com taxa menos meta",
                  bool(np.allclose(com.gap_meta, com.taxa_alfabetizacao - com.meta_taxa,
                                   atol=5e-5)), f"{len(com):,} linhas com meta")
        rel.check(f"gold.{mart} — atingiu_meta coerente",
                  bool((com.atingiu_meta == (com.taxa_alfabetizacao >= com.meta_taxa)).all()))
        rel.check(f"gold.{mart} — toda meta declara origem e escopo",
                  bool(com.meta_origem.notna().all() and com.meta_escopo.notna().all()),
                  f"origens: {puro(sorted(com.meta_origem.dropna().unique()))}")
        rel.check(f"gold.{mart} — sem meta implica atingiu_meta nulo",
                  bool(d[d.meta_taxa.isna()].atingiu_meta.isna().all()),
                  f"{int(d.meta_taxa.isna().sum()):,} linhas sem meta")

    for mart in ("evolucao_uf", "evolucao_municipio"):
        d = gold[mart]
        rel.check(f"gold.{mart} — variação confere com a diferença entre anos",
                  bool(np.allclose(d.variacao_absoluta.dropna(),
                                   (d.taxa_alfabetizacao - d.taxa_ano_anterior).dropna(),
                                   atol=5e-5)),
                  f"{int(d.taxa_ano_anterior.notna().sum()):,} linhas com ano anterior")

    d7 = gold["distribuicao_proficiencia"]
    acima = d7.faixa_label.isin(FAIXAS_ALFABETIZADAS)
    rel.check("distribuicao_proficiencia — alfabetizados só acima do corte",
              bool((d7[acima].alunos_alfabetizados == d7[acima].alunos_avaliados).all()
                   and (d7[~acima].alunos_alfabetizados == 0).all()))

    # --- equivalência com o indicador publicado pelo INEP ------------------
    # A concordância não é exata: o INEP aplica critérios de publicação (amostra
    # mínima, por exemplo) que os microdados não carregam. Por isso a checagem
    # olha a distribuição das diferenças, não o pior caso.
    escopos = compor_escopos(alunos_por_dep, ["ano", "sigla_uf"])
    conf = (gold["resumo_uf"][["ano", "sigla_uf", "rede", "taxa_alfabetizacao"]]
            .merge(escopos[["ano", "sigla_uf", "rede", "taxa_ponderada", "alunos"]],
                   on=["ano", "sigla_uf", "rede"], how="inner"))
    conf["dif"] = (conf.taxa_alfabetizacao - conf.taxa_ponderada).abs() * 100
    dentro = float((conf.dif <= 0.05).mean())
    rel.check("o indicador recalculado dos microdados reproduz o agregado do INEP",
              bool(conf.dif.median() < 0.01 and dentro >= 0.95),
              f"{len(conf):,} pares | mediana {conf.dif.median():.4f} p.p. | "
              f"{dentro:.1%} dentro de 0,05 p.p.")
    fora = conf[conf.dif > 0.1]
    rel.check("nenhum recorte diverge do agregado publicado acima de 0,1 p.p.",
              len(fora) == 0,
              "; ".join(f"{int(r.ano)} {r.sigla_uf} rede {int(r.rede)}: {r.dif:.2f} p.p. "
                        f"em {int(r.alunos):,} alunos" for r in fora.itertuples()) or "nenhum",
              bloqueante=False)

    # O número nacional é ponderado pela população avaliada, não é a média das UFs.
    nac = (alunos_por_dep[alunos_por_dep.dep.isin(REDE_COMPOSICAO[REDE_META_UF])]
           .groupby("ano", as_index=False).agg(peso=("peso", "sum"),
                                               w_alfab=("w_alfab", "sum")))
    nac["indicador"] = nac.w_alfab / nac.peso

    uf = pd.read_excel(raw / PUBLICACOES_META[2024]["uf"], sheet_name=ABA_UF,
                       header=1, dtype=str)
    brasil = uf[uf.SIGLA_UF.isna() & uf.NOME_UF.astype("string").str.strip().eq("Brasil")]
    # Só 2024 é exigível: é o ano com cobertura completa e precisão de duas casas
    # na divulgação. Em 2023 a avaliação alcançou 24 UFs, e o número nacional
    # publicado tem abrangência maior que a soma dos estados divulgados — não é
    # reproduzível a partir do microdado estadual, e isso não indica erro aqui.
    publicado = pd.to_numeric(brasil["PC_ALUNO_ALFABETIZADO_2024"], errors="coerce").iloc[0] / 100
    nosso = float(nac[nac.ano == 2024].indicador.iloc[0])
    rel.check("indicador nacional de 2024 reproduz o publicado pelo INEP",
              abs(nosso - publicado) * 100 < 0.05,
              f"recalculado {nosso:.4%} x publicado {publicado:.4%}")

    publicado_2023 = pd.to_numeric(brasil["PC_ALUNO_ALFABETIZADO_2023"],
                                   errors="coerce").iloc[0] / 100
    nosso_2023 = float(nac[nac.ano == 2023].indicador.iloc[0])
    rel.check("indicador nacional de 2023 confere com o publicado",
              abs(nosso_2023 - publicado_2023) * 100 < 0.05,
              f"recalculado {nosso_2023:.2%} x publicado {publicado_2023:.2%} — a avaliação "
              f"de 2023 cobriu 24 UFs e o nacional publicado abrange mais que a soma dos "
              f"estados divulgados; use o valor por UF, que confere",
              bloqueante=False)
    for r in nac.itertuples():
        rel.info(f"indicador nacional da rede pública em {int(r.ano)}: {r.indicador:.1%} "
                 f"(ponderado por {r.peso:,.0f} alunos avaliados)")

    # Resultado por UF contra a planilha oficial.
    uf2 = uf[uf.SIGLA_UF.notna()].copy()
    uf2["sigla_uf"] = uf2.SIGLA_UF.str.replace("*", "", regex=False).str.strip().str.upper()
    oficial = uf2.assign(
        oficial=pd.to_numeric(uf2.PC_ALUNO_ALFABETIZADO_2024, errors="coerce") / 100.0
    )[["sigla_uf", "oficial"]]
    nosso = gold["meta_vs_resultado_uf"].query("ano == 2024")[["sigla_uf", "taxa_alfabetizacao"]]
    c = oficial.merge(nosso, on="sigla_uf", how="inner")
    dif = (c.oficial - c.taxa_alfabetizacao).abs() * 100
    rel.check("meta_vs_resultado_uf reproduz o resultado publicado na planilha do INEP",
              bool(len(c) >= 25 and dif.max() < 0.01),
              f"{len(c)} UFs conferidas | diferença máxima {dif.max():.4f} p.p.")


def diagnosticos(gold, rel: Relatorio) -> None:
    rel.etapa("DIAGNÓSTICO — leitura destes dados na Fase 3")
    resumo, mu = gold["resumo_uf"], gold["meta_vs_resultado_uf"]
    rel.info(f"anos cobertos: {puro(sorted(resumo.ano.dropna().unique()))}")
    rel.info("escopos de rede disponíveis: "
             f"{puro({int(k): REDE_MAP[int(k)] for k in sorted(resumo.rede.dropna().unique())})}")
    rel.info("UFs com medição por ano: "
             f"{puro(resumo.groupby('ano', dropna=False).sigla_uf.nunique().to_dict())}")

    for ano in sorted(mu.ano.dropna().unique()):
        d = mu[mu.ano == ano]
        # Melhor e pior consideram todas as UFs medidas: as que já superam 80%
        # não têm meta intermediária e sairiam do ranking se o recorte fosse só
        # "com meta" — justamente as melhores.
        melhor, pior = d.loc[d.taxa_alfabetizacao.idxmax()], d.loc[d.taxa_alfabetizacao.idxmin()]
        com = d[d.meta_taxa.notna()]
        meta_br = d.meta_brasil.mean()
        texto_meta = ("sem meta nacional (ano-base)" if pd.isna(meta_br)
                      else f"meta nacional {meta_br * 100:.0f}%")
        atingiram = (f"{int(com.atingiu_meta.sum())} de {len(com)} UFs com meta a atingiram"
                     if len(com) else "nenhuma UF tinha meta publicada")
        rel.info(f"{int(ano)} (rede pública): {len(d)} UFs medidas | média simples "
                 f"{d.taxa_alfabetizacao.mean() * 100:.1f}% | {texto_meta} | {atingiram} | "
                 f"melhor {melhor.sigla_uf} {melhor.taxa_alfabetizacao * 100:.1f}%, "
                 f"pior {pior.sigla_uf} {pior.taxa_alfabetizacao * 100:.1f}%")

    mm = gold["meta_vs_resultado_municipio"]
    com = mm[mm.meta_taxa.notna()]
    rel.info(f"municípios com meta oficial: {com.id_municipio.nunique():,} | metas distintas "
             f"em SP num ano: {com[(com.sigla_uf == 'SP') & (com.ano == com.ano.max())].meta_taxa.nunique()}")

    serie = (resumo[resumo.rede == REDE_META_UF].groupby("ano", as_index=False)
             .agg(taxa=("taxa_alfabetizacao", "mean")).sort_values("ano"))
    if len(serie) >= 2:
        p, u = serie.iloc[0], serie.iloc[-1]
        ritmo = (u.taxa - p.taxa) / (u.ano - p.ano)
        restantes = 2030 - int(u.ano)
        rel.info(f"trajetória da rede pública (média simples das UFs): {p.taxa * 100:.1f}% em "
                 f"{int(p.ano)} -> {u.taxa * 100:.1f}% em {int(u.ano)} | ritmo "
                 f"{ritmo * 100:+.1f} p.p./ano | a meta oficial de 2030 é 80%, exigindo "
                 f"{(0.80 - u.taxa) / restantes * 100:+.1f} p.p./ano")
