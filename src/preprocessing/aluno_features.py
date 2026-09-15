"""Base de treino no grão do aluno, para a modelagem supervisionada.

Uma linha por aluno avaliado em 2024 e 2025, com o alvo `alfabetizado` e o
contexto territorial **defasado em um ano**. 2023 fica de fora como ano de
treino porque é o primeiro da série e não tem contexto anterior — mas alimenta
as features defasadas de 2024.

Duas decisões de projeto que existem para impedir vazamento do alvo:

1. **Nada do ano corrente que derive do resultado entra como feature.** A taxa
   de alfabetização do município em 2024 é calculada a partir dos próprios
   alunos que o modelo tenta prever. Todo indicador de resultado vem de t-1. As
   metas são exceção legítima: foram publicadas antes da avaliação e derivam do
   resultado anterior, não do corrente.

2. **A proficiência não entra.** Ela é o alvo antes do corte de 743 — incluí-la
   tornaria o problema trivial. Para análise da distribuição, use o mart
   `distribuicao_proficiencia`.

Sobre `id_escola_ano`: o INEP publica o código da escola **mascarado, com
códigos fictícios resorteados a cada ano** (dicionário da AEEB). O mesmo número
é outra escola em outro ano, e ele não joina com Censo Escolar nem INSE. Por
isso a coluna sai como par ano+código, válida apenas dentro do ano, e serve para
duas coisas: porte da escola e agrupamento na validação cruzada (GroupKFold),
para que colegas do mesmo aluno não fiquem divididos entre treino e teste.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    ALFABETIZACAO_CORTE, COLUNAS_ALUNO, MICRODADOS, REDE_MAP, REDE_META_UF,
)
from src.report import Relatorio
from src.utils import ler_do_zip, puro

# Dependência administrativa do aluno -> escopo de rede dos agregados oficiais.
DEP_PARA_REDE = {1: 1, 2: 2, 3: 3, 4: 4}

ANOS_TREINO = [2024, 2025]


def _contexto_defasado(gold: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Monta os quadros de contexto, já deslocados para o ano seguinte.

    Deslocar aqui, uma vez, evita repetir `ano - 1` em cada join e torna o
    vazamento difícil de introduzir por descuido: tudo que sai daqui já está
    endereçado ao ano em que será consumido.
    """
    ind = gold["indicador_municipio"]
    evo_mun = gold["evolucao_municipio"]
    resumo = gold["resumo_uf"]
    evo_uf = gold["evolucao_uf"]

    mun_rede = (ind[["ano", "id_municipio", "rede", "taxa_alfabetizacao"]]
                .rename(columns={"taxa_alfabetizacao": "mun_taxa_rede_t1"})
                .assign(ano=lambda d: d.ano + 1))

    mun_publica = (ind[ind.rede == REDE_META_UF]
                   [["ano", "id_municipio", "taxa_alfabetizacao", "nivel_alfabetizacao"]]
                   .rename(columns={"taxa_alfabetizacao": "mun_taxa_publica_t1",
                                    "nivel_alfabetizacao": "mun_nivel_t1"})
                   .assign(ano=lambda d: d.ano + 1))

    mun_variacao = (evo_mun[evo_mun.rede == REDE_META_UF]
                    [["ano", "id_municipio", "variacao_absoluta"]]
                    .rename(columns={"variacao_absoluta": "mun_variacao_publica_t1"})
                    .assign(ano=lambda d: d.ano + 1))

    uf_publica = (resumo[resumo.rede == REDE_META_UF][["ano", "sigla_uf", "taxa_alfabetizacao"]]
                  .rename(columns={"taxa_alfabetizacao": "uf_taxa_publica_t1"})
                  .assign(ano=lambda d: d.ano + 1))

    uf_variacao = (evo_uf[evo_uf.rede == REDE_META_UF][["ano", "sigla_uf", "variacao_absoluta"]]
                   .rename(columns={"variacao_absoluta": "uf_variacao_publica_t1"})
                   .assign(ano=lambda d: d.ano + 1))

    # Metas: do ano corrente, porque são conhecidas antes da avaliação.
    meta_mun = (gold["meta_vs_resultado_municipio"][["ano", "id_municipio", "meta_taxa"]]
                .rename(columns={"meta_taxa": "mun_meta_ano"}))
    meta_uf = (gold["meta_vs_resultado_uf"][["ano", "sigla_uf", "meta_taxa"]]
               .rename(columns={"meta_taxa": "uf_meta_ano"}))

    return {"mun_rede": mun_rede, "mun_publica": mun_publica, "mun_variacao": mun_variacao,
            "uf_publica": uf_publica, "uf_variacao": uf_variacao,
            "meta_mun": meta_mun, "meta_uf": meta_uf}


def construir_aluno_features(raw: Path, gold: dict[str, pd.DataFrame], dim_uf, dim_mun,
                             inse: pd.DataFrame, taxas: pd.DataFrame,
                             rel: Relatorio) -> pd.DataFrame:
    rel.etapa("ALUNO_FEATURES — base de treino no grão do aluno")
    ctx = _contexto_defasado(gold)
    partes = []

    for ano in ANOS_TREINO:
        d = ler_do_zip(raw / MICRODADOS[ano], "DADOS/TS_ALUNO.csv",
                       usecols=COLUNAS_ALUNO, dtype=str)
        prof = pd.to_numeric(d.VL_PROFICIENCIA_LP, errors="coerce")
        peso = pd.to_numeric(d.VL_PESO_ALUNO_LP, errors="coerce")
        avaliado = prof.notna() & peso.notna()
        # Filtrar antes de converter: fora dos avaliados há registros sem
        # identificador, e o cast para inteiro quebraria neles.
        total_avaliados = int(avaliado.sum())
        d, prof, peso = d[avaliado], prof[avaliado], peso[avaliado]

        base = pd.DataFrame({
            "ano": np.int16(ano),
            "id_aluno": pd.to_numeric(d.ID_ALUNO, errors="coerce").astype("Int64"),
            # O código é fictício e resorteado a cada ano: o par ano+código é a
            # única forma válida de identificar a escola.
            "id_escola_ano": ano.__str__() + "-" + d.ID_ESCOLA.str.strip(),
            "id_municipio": d.CO_MUNICIPIO.str.strip().str.zfill(7),
            "sigla_uf": d.SG_UF.str.strip().str.upper(),
            "rede": pd.to_numeric(d.TP_DEPENDENCIA, errors="coerce").map(DEP_PARA_REDE),
            "peso_amostral": peso.astype("float32"),
            "alfabetizado": (prof >= ALFABETIZACAO_CORTE).astype("int8"),
        }).reset_index(drop=True)
        # Int64 (anulável) e não int8: o tipo tem de casar com o `rede` dos marts
        # no join do contexto.
        base["rede"] = base.rede.astype("Int64")
        base["rede_label"] = base.rede.map(REDE_MAP).astype("string")

        # Uma fração mínima de alunos chega sem escola, sem município e sem
        # dependência administrativa. Têm alvo válido, mas nenhuma feature
        # territorial pode ser atribuída a eles — seriam linhas inteiramente
        # nulas. Saem da base, com a contagem registrada.
        sem_territorio = base.id_municipio.isna() | base.id_escola_ano.isna()
        base = base[~sem_territorio].reset_index(drop=True)

        # Porte: estrutural, não deriva do alvo.
        base["escola_alunos_avaliados"] = (
            base.groupby("id_escola_ano").id_aluno.transform("size").astype("int32"))
        base["mun_alunos_avaliados"] = (
            base.groupby("id_municipio").id_aluno.transform("size").astype("int32"))

        partes.append(base)
        descartados = int(sem_territorio.sum())
        rel.info(f"{ano}: {total_avaliados:,} alunos avaliados | "
                 f"{base.id_escola_ano.nunique():,} escolas | "
                 f"{base.id_municipio.nunique():,} municípios"
                 + (f" | {descartados:,} descartados sem escola/município na fonte"
                    if descartados else ""))
        del d, base

    alunos = pd.concat(partes, ignore_index=True)

    # --- território (estrutural, do ano corrente) --------------------------
    alunos = alunos.merge(
        dim_mun[["id_municipio", "capital", "latitude", "longitude"]],
        on="id_municipio", how="left")
    alunos = alunos.merge(dim_uf[["sigla_uf", "regiao"]], on="sigla_uf", how="left")

    # --- contexto defasado --------------------------------------------------
    alunos = (alunos
              .merge(ctx["mun_rede"], on=["ano", "id_municipio", "rede"], how="left")
              .merge(ctx["mun_publica"], on=["ano", "id_municipio"], how="left")
              .merge(ctx["mun_variacao"], on=["ano", "id_municipio"], how="left")
              .merge(ctx["uf_publica"], on=["ano", "sigla_uf"], how="left")
              .merge(ctx["uf_variacao"], on=["ano", "sigla_uf"], how="left")
              .merge(ctx["meta_mun"], on=["ano", "id_municipio"], how="left")
              .merge(ctx["meta_uf"], on=["ano", "sigla_uf"], how="left"))

    # --- enriquecimento municipal ------------------------------------------
    # INSE na rede do aluno, com a rede pública como alternativa quando a
    # específica não foi publicada para aquele município.
    alunos = alunos.merge(inse, on=["id_municipio", "rede"], how="left")
    reserva = (inse[inse.rede == REDE_META_UF]
               .drop(columns="rede")
               .rename(columns={c: c + "_pub" for c in
                                ("mun_inse_media", "mun_inse_pct_vulneravel",
                                 "mun_inse_alunos")}))
    alunos = alunos.merge(reserva, on="id_municipio", how="left")
    for c in ("mun_inse_media", "mun_inse_pct_vulneravel", "mun_inse_alunos"):
        alunos[c] = alunos[c].where(alunos[c].notna(), alunos[c + "_pub"])
    alunos = alunos.drop(columns=[c + "_pub" for c in
                                  ("mun_inse_media", "mun_inse_pct_vulneravel",
                                   "mun_inse_alunos")])
    # As taxas já chegam endereçadas ao ano de consumo (t-1 deslocado).
    alunos = alunos.merge(taxas, on=["ano", "id_municipio", "rede"], how="left")

    for c in ("capital",):
        alunos[c] = alunos[c].astype("Int8")
    for c in ("latitude", "longitude", "mun_taxa_rede_t1", "mun_taxa_publica_t1",
              "mun_variacao_publica_t1", "uf_taxa_publica_t1", "uf_variacao_publica_t1",
              "mun_meta_ano", "uf_meta_ano", "mun_inse_media", "mun_inse_pct_vulneravel",
              "mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1",
              "mun_reprovacao_2ano_t1", "mun_abandono_iniciais_t1"):
        alunos[c] = alunos[c].astype("float32")
    alunos["mun_nivel_t1"] = alunos.mun_nivel_t1.astype("Int8")

    colunas = ["ano", "id_aluno", "id_escola_ano", "id_municipio", "sigla_uf", "regiao",
               "capital", "latitude", "longitude", "rede", "rede_label",
               "escola_alunos_avaliados", "mun_alunos_avaliados",
               "mun_taxa_rede_t1", "mun_taxa_publica_t1", "mun_nivel_t1",
               "mun_variacao_publica_t1", "mun_meta_ano",
               "uf_taxa_publica_t1", "uf_variacao_publica_t1", "uf_meta_ano",
               "mun_inse_media", "mun_inse_pct_vulneravel", "mun_inse_alunos",
               "mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1",
               "mun_reprovacao_2ano_t1", "mun_abandono_iniciais_t1",
               "peso_amostral", "alfabetizado"]
    alunos = alunos[colunas].sort_values(["ano", "sigla_uf", "id_municipio", "id_aluno"]
                                         ).reset_index(drop=True)

    _validar(alunos, gold, rel)
    return alunos


def _validar(alunos: pd.DataFrame, gold: dict[str, pd.DataFrame], rel: Relatorio) -> None:
    rel.check("aluno_features — um registro por aluno e ano",
              not alunos.duplicated(["ano", "id_aluno"]).any(),
              f"{len(alunos):,} linhas, {alunos.groupby('ano').id_aluno.nunique().sum():,} "
              f"pares únicos")
    rel.check("aluno_features — alvo binário sem nulos",
              bool(alunos.alfabetizado.isin([0, 1]).all() and alunos.alfabetizado.notna().all()),
              f"distribuição {puro(alunos.alfabetizado.value_counts().to_dict())}")
    rel.check("aluno_features — cobre apenas os anos com contexto anterior",
              sorted(alunos.ano.unique()) == ANOS_TREINO,
              f"anos {puro(sorted(alunos.ano.unique()))}")
    rel.check("aluno_features — a proficiência não está na base",
              not any("proficiencia" in c for c in alunos.columns),
              "o alvo contínuo ficaria como feature e tornaria o problema trivial")

    # Prova de que o contexto é mesmo do ano anterior: para uma amostra de
    # municípios, o valor defasado tem de bater com o indicador de t-1.
    ind = gold["indicador_municipio"]
    amostra = (alunos[alunos.mun_taxa_publica_t1.notna()]
               .drop_duplicates(["ano", "id_municipio"]).head(2000)
               [["ano", "id_municipio", "mun_taxa_publica_t1"]])
    esperado = (ind[ind.rede == REDE_META_UF][["ano", "id_municipio", "taxa_alfabetizacao"]]
                .assign(ano=lambda d: d.ano + 1))
    conf = amostra.merge(esperado, on=["ano", "id_municipio"], how="inner")
    rel.check("aluno_features — o contexto municipal é o do ano anterior",
              bool(len(conf) > 0 and np.allclose(conf.mun_taxa_publica_t1,
                                                 conf.taxa_alfabetizacao, atol=1e-6)),
              f"{len(conf):,} municípios conferidos contra o indicador de t-1")

    # Contraprova: o contexto NÃO pode coincidir com o indicador do ano corrente.
    atual = (ind[ind.rede == REDE_META_UF][["ano", "id_municipio", "taxa_alfabetizacao"]]
             .rename(columns={"taxa_alfabetizacao": "taxa_corrente"}))
    c2 = amostra.merge(atual, on=["ano", "id_municipio"], how="inner")
    iguais = int(np.isclose(c2.mun_taxa_publica_t1, c2.taxa_corrente, atol=1e-9).sum())
    rel.check("aluno_features — o contexto não é o do ano corrente (sem vazamento)",
              iguais < max(1, int(0.02 * len(c2))),
              f"{iguais:,} de {len(c2):,} municípios coincidem com o ano corrente "
              f"(coincidência exata é possível quando a taxa não mudou)")

    faltantes = {c: f"{alunos[c].isna().mean():.1%}"
                 for c in alunos.columns if alunos[c].isna().any()}
    rel.info(f"aluno_features — features com valor faltante: {puro(faltantes)} "
             f"(a imputação é responsabilidade do pipeline de ML)")
    rel.info(f"aluno_features — taxa de alfabetizados na base: "
             f"{alunos.alfabetizado.mean():.1%} bruta | "
             f"{np.average(alunos.alfabetizado, weights=alunos.peso_amostral):.1%} ponderada")
    rel.info(f"aluno_features — {len(alunos):,} linhas x {len(alunos.columns)} colunas | "
             f"{alunos.id_escola_ano.nunique():,} grupos de escola para GroupKFold")
