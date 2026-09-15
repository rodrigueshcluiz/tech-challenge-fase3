"""Quality Gate — validação bloqueante entre a Silver e a Gold.

Reprovar aqui impede a publicação da Gold. Os registros reprovados saem com o
motivo, para que a perda seja observável e não silenciosa.
"""
from __future__ import annotations

import pandas as pd

from src.config import COBERTURA_MIN, REDE_MAP, UFS_VALIDAS
from src.report import Relatorio


def quality_gate(silver: pd.DataFrame, dim_uf, dim_mun, rel: Relatorio) -> pd.DataFrame:
    rel.etapa("QUALITY GATE — validação bloqueante antes da Gold")
    s = silver
    motivo = pd.Series(pd.NA, index=s.index, dtype="string")

    def marcar(cond, razao: str) -> None:
        """A primeira regra violada define o motivo da rejeição."""
        motivo.loc[motivo.isna() & cond.fillna(False)] = razao

    marcar(s.ano.isna() | s.sigla_uf.isna() | s.rede.isna() | s.record_id.isna(),
           "campo_critico_nulo")
    marcar((s.grao == "municipio") & s.id_municipio.isna(), "municipio_nulo_no_grao_municipal")
    marcar(~s.sigla_uf.isin(UFS_VALIDAS), "sigla_uf_invalida")
    marcar(s.id_municipio.notna()
           & ~s.id_municipio.fillna("").str.fullmatch(r"\d{7}").fillna(False),
           "id_municipio_invalido")
    marcar(~s.rede.isin(list(REDE_MAP)), "rede_fora_do_dominio")
    marcar(s.taxa_alfabetizacao.notna() & ~s.taxa_alfabetizacao.between(0, 1),
           "taxa_fora_do_dominio")
    marcar(s.meta_taxa.notna() & ~s.meta_taxa.between(0, 1), "meta_fora_do_dominio")
    marcar(s.grao.isna() | ~s.grao.isin(["uf", "municipio"]), "grao_invalido")
    marcar(s.id_municipio.notna() & ~s.id_municipio.isin(set(dim_mun.id_municipio)),
           "municipio_inexistente_na_dimensao")
    marcar(~s.sigla_uf.isin(set(dim_uf.sigla_uf)), "uf_inexistente_na_dimensao")
    marcar(s.uf_consistente == False, "uf_incompativel_com_municipio")  # noqa: E712
    # Governança da meta: nenhuma meta entra na Gold sem dizer de onde veio.
    marcar(s.meta_taxa.notna() & (s.meta_origem.isna() | s.meta_escopo.isna()),
           "meta_sem_procedencia")
    marcar(s.meta_status.isna(), "meta_status_ausente")

    aprovados = s[motivo.isna()].reset_index(drop=True)
    lidos, escritos = len(s), len(aprovados)
    if motivo.notna().any():
        for razao, n in motivo.dropna().value_counts().items():
            rel.info(f"quarentena — {razao}: {n:,}")
    cobertura = escritos / lidos if lidos else 0.0

    rel.check("Silver não vazia", lidos > 0, f"{lidos:,} medições")
    rel.check("aprovados maior que zero", escritos > 0, f"{escritos:,} aprovados")
    rel.check("record_id único nos aprovados", escritos == aprovados.record_id.nunique())
    rel.check(f"cobertura mínima de {COBERTURA_MIN:.0%}", cobertura >= COBERTURA_MIN,
              f"{cobertura:.1%} ({escritos:,}/{lidos:,})")
    rel.check("toda meta aprovada declara origem e escopo",
              bool(aprovados[aprovados.meta_taxa.notna()].meta_origem.notna().all()))
    return aprovados
