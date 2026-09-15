"""Silver — modelo canônico, integração das dimensões e das metas oficiais."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    ALFABETIZACAO_CORTE, ALFABETIZACAO_RULE_VERSION, ANO_META_MIN, REDE_COMPOSICAO,
    REDE_MAP, REDE_META_MUNICIPIO, REDE_META_UF, SCHEMA_VERSION,
)
from src.report import Relatorio
from src.utils import puro, sha256_concat_ws, texto_int


def compor_escopos(por_dep: pd.DataFrame, chaves: list[str]) -> pd.DataFrame:
    """Soma as dependências administrativas que compõem cada escopo de rede."""
    partes = []
    for rede, deps in REDE_COMPOSICAO.items():
        p = por_dep[por_dep.dep.isin(deps)]
        if p.empty:
            continue
        agregado = (p.assign(rede=rede)
                    .groupby(chaves + ["rede"], dropna=False, as_index=False)
                    .agg({c: "sum" for c in ("peso", "w_alfab", "w_prof",
                                             "alunos", "alunos_alfab")}))
        partes.append(agregado)
    out = pd.concat(partes, ignore_index=True)
    out["rede"] = out.rede.astype("Int64")
    out["taxa_ponderada"] = out.w_alfab / out.peso
    out["proficiencia_ponderada"] = out.w_prof / out.peso
    return out


def construir_silver(fatos_uf, fatos_mun, dim_uf, dim_mun, meta_uf, meta_mun, meta_br,
                     nivel, alunos_uf, rel: Relatorio, processed_at) -> pd.DataFrame:
    rel.etapa("SILVER — modelo canônico e integração das metas oficiais")

    fatos = pd.concat([
        fatos_uf.assign(grao="uf", id_municipio=pd.NA, source="inep_agregado_uf"),
        fatos_mun.assign(grao="municipio", source="inep_agregado_municipio"),
    ], ignore_index=True)
    fatos["id_municipio"] = fatos.id_municipio.astype("string")
    fatos["rede_label"] = fatos.rede.map(REDE_MAP).astype("string")
    fatos["taxa_alfabetizacao"] = fatos.taxa_alfabetizacao / 100.0
    fatos["alfabetizado"] = (fatos.media_portugues >= ALFABETIZACAO_CORTE).astype("boolean")
    fatos.loc[fatos.media_portugues.isna(), "alfabetizado"] = pd.NA
    fatos["fonte_dados"] = "oficial_inep"
    fatos["schema_version"] = SCHEMA_VERSION
    fatos["alfabetizacao_rule_version"] = ALFABETIZACAO_RULE_VERSION

    rel.check("toda medição tem rótulo de rede", not fatos.rede_label.isna().any(),
              f"{int(fatos.rede_label.isna().sum()):,} sem rótulo")
    rel.check("taxa normalizada para fração 0–1",
              bool(fatos.taxa_alfabetizacao.dropna().between(0, 1).all()),
              f"min={fatos.taxa_alfabetizacao.min():.4f} "
              f"max={fatos.taxa_alfabetizacao.max():.4f}")

    # --- dimensões territoriais --------------------------------------------
    fatos = fatos.merge(dim_mun, on="id_municipio", how="left")
    fatos["sigla_uf"] = fatos.sigla_uf.where(fatos.sigla_uf.notna(), fatos.sigla_uf_dim)
    fatos["uf_consistente"] = pd.Series(
        np.where(fatos.id_municipio.isna(), pd.NA, fatos.sigla_uf == fatos.sigla_uf_dim),
        index=fatos.index, dtype="boolean")
    fatos = fatos.drop(columns="sigla_uf_dim").merge(dim_uf, on="sigla_uf", how="left")

    orfaos = int((fatos.id_municipio.notna() & fatos.nome_municipio.isna()).sum())
    rel.check("todo fato municipal existe na dimensão do IBGE", orfaos == 0,
              f"{orfaos:,} sem correspondência")
    rel.check("toda UF existe na dimensão", not fatos.nome_uf.isna().any(),
              f"{int(fatos.nome_uf.isna().sum()):,} sem correspondência")
    rel.check("UF do fato compatível com a UF do município na dimensão",
              not (fatos.uf_consistente == False).any(),  # noqa: E712
              f"{int((fatos.uf_consistente == False).sum()):,} incompatíveis")  # noqa: E712

    fatos = fatos.merge(nivel, on=["id_municipio", "ano"], how="left")

    # --- metas oficiais, no escopo em que foram publicadas -----------------
    fatos = fatos.merge(
        meta_uf[["sigla_uf", "ano", "meta", "meta_limiar", "meta_publicacao"]].rename(
            columns={"meta": "_meta_uf", "meta_limiar": "_lim_uf",
                     "meta_publicacao": "_pub_uf"}),
        on=["sigla_uf", "ano"], how="left")
    fatos = fatos.merge(
        meta_mun[["id_municipio", "ano", "meta", "meta_limiar", "meta_publicacao"]].rename(
            columns={"meta": "_meta_mun", "meta_limiar": "_lim_mun",
                     "meta_publicacao": "_pub_mun"}),
        on=["id_municipio", "ano"], how="left")
    fatos = fatos.merge(meta_br, on="ano", how="left")

    escopo_uf = (fatos.grao == "uf") & (fatos.rede == REDE_META_UF)
    escopo_mun = (fatos.grao == "municipio") & (fatos.rede == REDE_META_MUNICIPIO)
    fatos["meta_taxa"] = np.where(escopo_uf, fatos._meta_uf,
                                  np.where(escopo_mun, fatos._meta_mun, np.nan))
    fatos["meta_limiar"] = pd.Series(
        np.where(escopo_uf, fatos._lim_uf, np.where(escopo_mun, fatos._lim_mun, False)),
        index=fatos.index).astype("boolean")
    fatos["meta_publicacao"] = pd.Series(
        np.where(escopo_uf, fatos._pub_uf, np.where(escopo_mun, fatos._pub_mun, np.nan)),
        index=fatos.index).astype("Int64")
    tem_meta = fatos.meta_taxa.notna()
    fatos["meta_escopo"] = pd.Series(
        np.where(escopo_uf & tem_meta, "rede_publica",
                 np.where(escopo_mun & tem_meta, "rede_municipal", pd.NA)),
        index=fatos.index, dtype="string")
    fatos["meta_origem"] = pd.Series(
        np.where(tem_meta, "inep_compromisso_nacional", pd.NA),
        index=fatos.index, dtype="string")
    # Por que não há meta — o oposto do buraco de rastreabilidade da Fase 2,
    # em que a coluna `metodologia` era descartada no join.
    fatos["meta_status"] = pd.Series(
        np.select([tem_meta, fatos.ano < ANO_META_MIN, ~(escopo_uf | escopo_mun)],
                  ["oficial", "ano_anterior_a_meta", "escopo_de_rede_sem_meta_oficial"],
                  default="territorio_sem_meta_publicada"),
        index=fatos.index, dtype="string")
    fatos = fatos.drop(columns=[c for c in fatos.columns if c.startswith("_")])

    rel.info("situação da meta em cada medição: "
             f"{puro(fatos.groupby('meta_status', dropna=False).size().to_dict())}")

    # Contrapartida: toda meta aplicável a um território avaliado foi aplicada?
    aplicaveis_uf = meta_uf.merge(fatos[escopo_uf][["ano", "sigla_uf"]].drop_duplicates(),
                                  on=["ano", "sigla_uf"], how="inner")
    rel.check("nenhuma meta de UF perdida no join",
              len(aplicaveis_uf) == int((escopo_uf & tem_meta).sum()),
              f"{len(aplicaveis_uf):,} aplicáveis, {int((escopo_uf & tem_meta).sum()):,} aplicadas")
    aplicaveis_mun = meta_mun.merge(
        fatos[escopo_mun][["ano", "id_municipio"]].drop_duplicates(),
        on=["ano", "id_municipio"], how="inner")
    rel.check("nenhuma meta de município perdida no join",
              len(aplicaveis_mun) == int((escopo_mun & tem_meta).sum()),
              f"{len(aplicaveis_mun):,} aplicáveis, "
              f"{int((escopo_mun & tem_meta).sum()):,} aplicadas")
    rel.check("meta em fração 0–1", bool(fatos.meta_taxa.dropna().between(0, 1).all()),
              f"min={fatos.meta_taxa.min():.4f} max={fatos.meta_taxa.max():.4f}")

    # --- enriquecimento com os microdados de aluno -------------------------
    fatos = fatos.merge(
        alunos_uf.rename(columns={"taxa_ponderada": "alunos_taxa_ponderada",
                                  "proficiencia_ponderada": "alunos_proficiencia_media",
                                  "alunos": "alunos_amostra",
                                  "peso": "alunos_peso_total"})
        [["ano", "sigla_uf", "rede", "alunos_taxa_ponderada", "alunos_proficiencia_media",
          "alunos_amostra", "alunos_peso_total"]],
        on=["ano", "sigla_uf", "rede"], how="left")

    # --- chave determinística ----------------------------------------------
    fatos["record_id"] = sha256_concat_ws([
        texto_int(fatos.ano, ""), fatos.sigla_uf, fatos.id_municipio.fillna("uf"),
        texto_int(fatos.serie, "na"), texto_int(fatos.rede, ""), fatos.source,
    ])
    fatos["processed_at"] = processed_at
    antes = len(fatos)
    silver = fatos.drop_duplicates("record_id").reset_index(drop=True)
    rel.check("record_id único — nenhuma medição perdida", len(silver) == antes,
              f"{antes:,} medições, {len(silver):,} chaves distintas")
    rel.info(f"silver: {len(silver):,} medições | "
             f"{int(silver.meta_taxa.notna().sum()):,} com meta oficial")
    return silver
