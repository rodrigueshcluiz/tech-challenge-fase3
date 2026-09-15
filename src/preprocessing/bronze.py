"""Bronze — ingestão fiel das fontes oficiais do INEP.

Três origens, todas oficiais:
- agregados por UF e município (TS_ESTADO / TS_MUNICIPIO dos microdados);
- microdados de aluno, com peso amostral (TS_ALUNO);
- metas do Compromisso Nacional Criança Alfabetizada (planilhas do INEP).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (
    ABA_MUNICIPIO, ABA_UF, ALFABETIZACAO_CORTE, ANO_META_MAX, ANO_META_MIN,
    COLUNAS_ALUNO, DIM_MUNICIPIO, DIM_UF, MICRODADOS, PRECEDENCIA_META,
    PUBLICACOES_META, REDE_MAP,
)
from src.report import Relatorio
from src.utils import faixa_label, ler_do_zip, numero, puro

COLUNAS_META = [f"META_FINAL_{a}" for a in range(ANO_META_MIN, ANO_META_MAX + 1)]


# ---------------------------------------------------------------------------
# Metas oficiais
# ---------------------------------------------------------------------------
def _despivotar(df: pd.DataFrame, chaves: list[str], publicacao: int) -> pd.DataFrame:
    """Passa META_FINAL_2024..2030 de colunas para linhas."""
    presentes = [c for c in COLUNAS_META if c in df.columns]
    longo = df.melt(id_vars=chaves, value_vars=presentes,
                    var_name="coluna", value_name="bruto")
    longo["ano"] = longo.coluna.str.extract(r"(\d{4})").astype(int)
    # "> 80" é piso mínimo, não alvo pontual.
    longo["meta_limiar"] = longo.bruto.astype("string").str.contains(">", na=False)
    longo["meta"] = numero(longo.bruto) / 100.0
    # Meta 0 marca território sem meta publicada (nível 0), não alvo zero.
    longo.loc[longo.meta.fillna(-1) <= 0, "meta"] = np.nan
    longo["meta_publicacao"] = publicacao
    return longo.drop(columns=["coluna", "bruto"]).dropna(subset=["meta"])


# A divulgação mais grosseira arredonda para ponto percentual inteiro, então uma
# diferença de até 0,5 p.p. entre divulgações é arredondamento, não revisão.
# Acima disso, a meta foi de fato recalculada.
TOLERANCIA_ARREDONDAMENTO = 0.0051


def _consolidar(partes: list[pd.DataFrame], chaves: list[str],
                rel: Relatorio, rotulo: str) -> pd.DataFrame:
    """Une as divulgações: a mais recente manda, a mais antiga refina a precisão.

    As três divulgam a mesma meta com precisões diferentes — 2023 traz o float
    completo, 2024 arredonda para duas casas, 2025 para inteiro. Mas algumas
    metas foram de fato **recalculadas** entre divulgações (o Acre, por exemplo,
    não participou da avaliação de 2023 e teve as metas dos seus municípios
    revisadas depois).

    Por isso o valor vigente é sempre o da divulgação mais recente. A mais antiga
    só é usada no lugar dela quando as duas concordam dentro da tolerância de
    arredondamento — aí ela é o mesmo alvo, com mais casas decimais.
    """
    chave_ano = chaves + ["ano"]
    todas = pd.concat(partes, ignore_index=True)

    vigente = (todas.sort_values(chave_ano + ["meta_publicacao"], kind="stable")
               .drop_duplicates(chave_ano, keep="last")
               .rename(columns={"meta": "meta_vigente"})[chave_ano + ["meta_vigente"]])
    candidatas = todas.merge(vigente, on=chave_ano, how="left")
    candidatas["_revisada"] = ((candidatas.meta - candidatas.meta_vigente).abs()
                               > TOLERANCIA_ARREDONDAMENTO)

    # Entre as que concordam com a vigente, fica a de maior precisão.
    ordem = {ano: i for i, ano in enumerate(PRECEDENCIA_META)}
    escolhida = (candidatas[~candidatas._revisada]
                 .assign(_prioridade=lambda d: d.meta_publicacao.map(ordem))
                 .sort_values(chave_ano + ["_prioridade"], kind="stable")
                 .drop_duplicates(chave_ano, keep="first")
                 .drop(columns=["_prioridade", "_revisada", "meta_vigente"])
                 .reset_index(drop=True))

    revisadas = candidatas[candidatas._revisada]
    n_revisadas = len(revisadas.drop_duplicates(chave_ano))
    rel.check(f"metas de {rotulo} recalculadas entre divulgações", n_revisadas == 0,
              f"{n_revisadas:,} chaves revisadas acima de 0,5 p.p. (maior diferença "
              f"{(revisadas.meta - revisadas.meta_vigente).abs().max() * 100:.2f} p.p.) — "
              f"prevalece a divulgação mais recente" if n_revisadas else "nenhuma",
              bloqueante=False)
    origem = escolhida.meta_publicacao.value_counts().sort_index().to_dict()
    rel.info(f"metas de {rotulo}: {len(escolhida):,} valores | divulgação que forneceu o "
             f"valor {puro(origem)}")
    return escolhida


def ler_metas(raw: Path, rel: Relatorio):
    """Devolve (meta_uf, meta_municipio, meta_brasil, nivel_municipio)."""
    partes_uf, partes_mun, partes_br, niveis = [], [], [], []

    for publicacao in PRECEDENCIA_META:
        arquivos = PUBLICACOES_META[publicacao]

        uf = pd.read_excel(raw / arquivos["uf"], sheet_name=ABA_UF, header=1, dtype=str)
        # A divulgação de 2025 marca Santa Catarina como "SC*" (nota de rodapé).
        uf["sigla_uf"] = uf.SIGLA_UF.str.replace("*", "", regex=False).str.strip().str.upper()
        partes_uf.append(_despivotar(uf[uf.sigla_uf.notna()], ["sigla_uf"], publicacao))

        brasil = uf[uf.SIGLA_UF.isna()
                    & uf.NOME_UF.astype("string").str.strip().eq("Brasil")].copy()
        brasil["chave"] = "BR"
        partes_br.append(_despivotar(brasil, ["chave"], publicacao))

        mun = pd.read_excel(raw / arquivos["municipio"], sheet_name=ABA_MUNICIPIO,
                            header=1, dtype=str)
        mun = mun[mun.CO_MUNICIPIO.notna()].copy()
        mun["id_municipio"] = mun.CO_MUNICIPIO.str.strip().str.zfill(7)
        partes_mun.append(_despivotar(mun, ["id_municipio"], publicacao))

        # Nível de alfabetização do município (1 a 5) no ano da divulgação.
        coluna_nivel = next((c for c in mun.columns
                             if "NIVEL" in c.upper() or "NIVEIS" in c.upper()), None)
        if coluna_nivel:
            niveis.append(pd.DataFrame({
                "id_municipio": mun.id_municipio,
                "ano": publicacao,
                "nivel_alfabetizacao": pd.to_numeric(mun[coluna_nivel],
                                                     errors="coerce").astype("Int64"),
            }).dropna(subset=["nivel_alfabetizacao"]))

    meta_uf = _consolidar(partes_uf, ["sigla_uf"], rel, "UF")
    meta_mun = _consolidar(partes_mun, ["id_municipio"], rel, "município")
    meta_br = (_consolidar(partes_br, ["chave"], rel, "Brasil")
               .rename(columns={"meta": "meta_brasil"})[["ano", "meta_brasil"]])
    nivel = (pd.concat(niveis, ignore_index=True).drop_duplicates(["id_municipio", "ano"])
             if niveis else pd.DataFrame(columns=["id_municipio", "ano", "nivel_alfabetizacao"]))

    rel.check("metas oficiais de UF carregadas", len(meta_uf) > 0,
              f"{len(meta_uf):,} metas | {meta_uf.sigla_uf.nunique()} UFs | "
              f"anos {puro(sorted(meta_uf.ano.unique()))}")
    rel.check("metas oficiais de município carregadas", len(meta_mun) > 0,
              f"{len(meta_mun):,} metas | {meta_mun.id_municipio.nunique():,} municípios")
    rel.check("metas nacionais carregadas", len(meta_br) == 7,
              ", ".join(f"{int(r.ano)}={r.meta_brasil:.1%}" for r in meta_br.itertuples()))
    rel.check("metas dentro do domínio 0–1",
              bool(meta_uf.meta.between(0, 1).all() and meta_mun.meta.between(0, 1).all()),
              f"UF: {meta_uf.meta.min():.4f}–{meta_uf.meta.max():.4f} | "
              f"município: {meta_mun.meta.min():.4f}–{meta_mun.meta.max():.4f}")
    rel.info(f"{int(meta_uf.meta_limiar.sum())} metas de UF são limiar ('> 80', "
             f"tratadas como piso de 80%)")
    rel.info(f"nível de alfabetização por município: {len(nivel):,} registros, "
             f"anos {puro(sorted(nivel.ano.unique())) if len(nivel) else []}")
    return meta_uf, meta_mun, meta_br, nivel


# ---------------------------------------------------------------------------
# Agregados oficiais por UF e município
# ---------------------------------------------------------------------------
def ler_fatos(raw: Path, rel: Relatorio) -> tuple[pd.DataFrame, pd.DataFrame]:
    def do_zip(ano: int, interno: str, com_municipio: bool) -> pd.DataFrame:
        d = ler_do_zip(raw / MICRODADOS[ano], interno, dtype=str)
        saida = pd.DataFrame({
            "ano": pd.to_numeric(d.NU_ANO_AVALIACAO, errors="coerce").astype("Int64"),
            "sigla_uf": d.SG_UF.str.strip().str.upper(),
            "serie": pd.to_numeric(d.TP_SERIE, errors="coerce").astype("Int64"),
            "rede": pd.to_numeric(d.ID_TIPO_REDE, errors="coerce").astype("Int64"),
            "taxa_alfabetizacao": pd.to_numeric(d.PC_ALUNO_ALFABETIZADO, errors="coerce"),
            "media_portugues": pd.to_numeric(d.VL_MEDIA_LP, errors="coerce"),
        })
        if com_municipio:
            saida["id_municipio"] = d.CO_MUNICIPIO.str.strip().str.zfill(7)
        return saida

    fatos_uf = pd.concat([do_zip(a, "DADOS/TS_ESTADO.csv", False) for a in MICRODADOS],
                         ignore_index=True)
    fatos_mun = pd.concat([do_zip(a, "DADOS/TS_MUNICIPIO.csv", True) for a in MICRODADOS],
                          ignore_index=True)

    for nome, df, chave in (("UF", fatos_uf, ["ano", "sigla_uf", "serie", "rede"]),
                            ("município", fatos_mun,
                             ["ano", "id_municipio", "serie", "rede"])):
        rel.info(f"agregados oficiais no grão {nome}: {len(df):,} linhas | "
                 f"por ano {puro(df.groupby('ano', dropna=False).size().to_dict())}")
        rel.check(f"agregados de {nome} sem duplicidade no grão",
                  not df.duplicated(chave).any(),
                  f"{int(df.duplicated(chave).sum()):,} duplicadas")
        rel.check(f"redes de {nome} no domínio oficial",
                  bool(df.rede.dropna().isin(REDE_MAP).all()),
                  f"presentes: {puro(sorted(df.rede.dropna().unique()))}")
        rel.check(f"taxa de {nome} em escala 0–100",
                  bool(df.taxa_alfabetizacao.dropna().between(0, 100).all()),
                  f"min={df.taxa_alfabetizacao.min():.2f} max={df.taxa_alfabetizacao.max():.2f}")
    return fatos_uf, fatos_mun


def ler_dimensoes(external: Path, rel: Relatorio) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dimensões territoriais do IBGE, versionadas em data/external."""
    dim_uf = pd.read_csv(external / DIM_UF, dtype=str)
    dim_uf = (dim_uf.assign(sigla_uf=dim_uf.sigla_uf.str.strip().str.upper())
              .rename(columns={"nome": "nome_uf"})[["sigla_uf", "nome_uf", "regiao"]]
              .drop_duplicates("sigla_uf"))
    dim_mun = pd.read_csv(external / DIM_MUNICIPIO, dtype=str)
    dim_mun = (dim_mun.assign(
        id_municipio=dim_mun.id_municipio.str.zfill(7),
        capital=pd.to_numeric(dim_mun.capital, errors="coerce").astype("Int64"),
        latitude=pd.to_numeric(dim_mun.latitude, errors="coerce"),
        longitude=pd.to_numeric(dim_mun.longitude, errors="coerce"))
        .rename(columns={"nome": "nome_municipio", "sigla_uf": "sigla_uf_dim"})
        [["id_municipio", "nome_municipio", "sigla_uf_dim", "capital",
          "latitude", "longitude"]]
        .drop_duplicates("id_municipio"))
    rel.check("dimensão de UF completa", len(dim_uf) == 27, f"{len(dim_uf)} UFs")
    rel.check("dimensão de município sem id duplicado",
              not dim_mun.id_municipio.duplicated().any(), f"{len(dim_mun):,} municípios")
    return dim_uf, dim_mun


# ---------------------------------------------------------------------------
# Microdados de aluno
# ---------------------------------------------------------------------------
def processar_alunos(raw: Path, rel: Relatorio) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lê TS_ALUNO de cada ano e agrega por dependência administrativa.

    O indicador oficial é ponderado por `VL_PESO_ALUNO_LP`. Agregamos primeiro
    por dependência (grão pequeno) e depois compomos os escopos de rede somando
    as dependências que cada um abrange, em vez de varrer os microdados uma vez
    por escopo.
    """
    rel.etapa("MICRODADOS DE ALUNO — leitura e agregação ponderada")
    por_dep_uf, por_dep_faixa = [], []

    for ano, arquivo in MICRODADOS.items():
        d = ler_do_zip(raw / arquivo, "DADOS/TS_ALUNO.csv", usecols=COLUNAS_ALUNO, dtype=str)
        total = len(d)
        prof = pd.to_numeric(d.VL_PROFICIENCIA_LP, errors="coerce")
        peso = pd.to_numeric(d.VL_PESO_ALUNO_LP, errors="coerce")
        dep = pd.to_numeric(d.TP_DEPENDENCIA, errors="coerce").astype("Int64")
        oficial = pd.to_numeric(d.IN_ALFABETIZADO, errors="coerce")
        avaliado = prof.notna() & peso.notna()

        coerente = (oficial[avaliado] == (prof[avaliado] >= ALFABETIZACAO_CORTE).astype(float))
        rel.check(f"{ano} — o corte de {ALFABETIZACAO_CORTE} reproduz IN_ALFABETIZADO do INEP",
                  bool(coerente.all()),
                  f"{int(coerente.sum()):,} de {int(avaliado.sum()):,} alunos avaliados")
        rel.check(f"{ano} — id de aluno único", not d.ID_ALUNO.duplicated().any(),
                  f"{total:,} alunos lidos")
        rel.check(f"{ano} — dependência administrativa no domínio oficial",
                  bool(dep.dropna().isin({1, 2, 3, 4}).all()),
                  f"presentes: {puro(sorted(dep.dropna().unique()))}"
                  + (f" | {int(dep.isna().sum()):,} registros sem dependência"
                     if dep.isna().any() else ""))
        rel.check(f"{ano} — proficiência na escala Saeb",
                  bool(prof.dropna().between(0, 1000).all()),
                  f"min={prof.min():.1f} max={prof.max():.1f}")

        base = pd.DataFrame({
            "ano": pd.to_numeric(d.NU_ANO_AVALIACAO, errors="coerce").astype("Int64"),
            "sigla_uf": d.SG_UF.str.strip().str.upper(),
            "dep": dep, "peso": peso, "prof": prof,
        })[avaliado].copy()
        rel.info(f"{ano}: {total:,} alunos | {len(base):,} com proficiência válida | "
                 f"{total - len(base):,} sem medição")

        base["alfab"] = (base.prof >= ALFABETIZACAO_CORTE).astype("float64")
        base["w_alfab"] = base.peso * base.alfab
        base["w_prof"] = base.peso * base.prof
        agregacoes = {"peso": ("peso", "sum"), "w_alfab": ("w_alfab", "sum"),
                      "w_prof": ("w_prof", "sum"), "alunos": ("prof", "size"),
                      "alunos_alfab": ("alfab", "sum")}
        por_dep_uf.append(base.groupby(["ano", "sigla_uf", "dep"], dropna=False,
                                       as_index=False).agg(**agregacoes))

        base["faixa_pontos"] = (np.floor(base.prof / 25) * 25).astype("int64")
        base["faixa_label"] = faixa_label(base.prof)
        por_dep_faixa.append(base.groupby(
            ["ano", "sigla_uf", "dep", "faixa_pontos", "faixa_label"],
            dropna=False, as_index=False).agg(**agregacoes))
        del d, base

    return (pd.concat(por_dep_uf, ignore_index=True),
            pd.concat(por_dep_faixa, ignore_index=True))
