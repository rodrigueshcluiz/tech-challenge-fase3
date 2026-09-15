"""Montagem do quadro de features de um ano ainda não avaliado.

A regra que sustenta a projeção é a mesma da `aluno_features`, e erra pelo mesmo
lugar: **resultado vem de t-1, meta vem do ano corrente**. Pegar o indicador do
ano projetado seria impossível (não existe) e pegar a meta de t-1 compararia o
município com um alvo vencido. Nenhum dos dois erros mudaria o formato da saída,
então só um teste os pega.
"""
import pandas as pd
import pytest

from src.config import REDE_META_UF
from src.modeling.projecao import _contexto_do_ano


def gold_minimo():
    """Três anos de série, para que escolher o ano errado dê resultado diferente."""
    ind = pd.DataFrame({
        "ano": [2024, 2025, 2026],
        "id_municipio": "1",
        "rede": REDE_META_UF,
        "taxa_alfabetizacao": [0.40, 0.50, 0.60],
        "nivel_alfabetizacao": [2, 3, 4],
    })
    # A mesma série na rede municipal, que é o recorte de `mun_taxa_rede_t1`.
    ind = pd.concat([ind, ind.assign(rede=3, taxa_alfabetizacao=[0.41, 0.51, 0.61])],
                    ignore_index=True)
    resumo = pd.DataFrame({
        "ano": [2024, 2025, 2026], "sigla_uf": "SP", "rede": REDE_META_UF,
        "taxa_alfabetizacao": [0.70, 0.75, 0.80],
    })
    evo_mun = pd.DataFrame({
        "ano": [2024, 2025, 2026], "id_municipio": "1", "rede": REDE_META_UF,
        "variacao_absoluta": [0.01, 0.02, 0.03],
    })
    evo_uf = pd.DataFrame({
        "ano": [2024, 2025, 2026], "sigla_uf": "SP", "rede": REDE_META_UF,
        "variacao_absoluta": [0.04, 0.05, 0.06],
    })
    metas_mun = pd.DataFrame({
        "ano": [2025, 2026], "id_municipio": "1", "meta_taxa": [0.65, 0.72]})
    metas_uf = pd.DataFrame({
        "ano": [2025, 2026], "sigla_uf": "SP", "meta_taxa": [0.85, 0.88]})
    return {"indicador_municipio": ind, "resumo_uf": resumo,
            "evolucao_municipio": evo_mun, "evolucao_uf": evo_uf,
            "metas_municipio": metas_mun, "metas_uf": metas_uf}


class TestContextoDoAnoProjetado:
    def test_o_resultado_vem_do_ano_anterior(self):
        """Para projetar 2026, o indicador é o de 2025."""
        ctx = _contexto_do_ano(gold_minimo(), 2026)
        assert ctx["mun_publica"].mun_taxa_publica_t1.iloc[0] == pytest.approx(0.50)
        assert ctx["mun_publica"].mun_nivel_t1.iloc[0] == 3
        assert ctx["uf_publica"].uf_taxa_publica_t1.iloc[0] == pytest.approx(0.75)

    def test_a_taxa_da_rede_respeita_a_rede_do_aluno(self):
        ctx = _contexto_do_ano(gold_minimo(), 2026)
        por_rede = ctx["mun_rede"].set_index("rede").mun_taxa_rede_t1
        assert por_rede.loc[3] == pytest.approx(0.51)
        assert por_rede.loc[REDE_META_UF] == pytest.approx(0.50)

    def test_a_meta_vem_do_ano_projetado_e_nao_de_t1(self):
        """A meta é publicada antes da avaliação: é a única que olha para a frente."""
        ctx = _contexto_do_ano(gold_minimo(), 2026)
        assert ctx["meta_mun"].mun_meta_ano.iloc[0] == pytest.approx(0.72)
        assert ctx["meta_uf"].uf_meta_ano.iloc[0] == pytest.approx(0.88)

    def test_nao_usa_o_indicador_do_proprio_ano_projetado(self):
        """Se usasse, a projeção leria o futuro — e 2026 nem existe na prática."""
        ctx = _contexto_do_ano(gold_minimo(), 2026)
        assert ctx["mun_publica"].mun_taxa_publica_t1.iloc[0] != pytest.approx(0.60)
        assert ctx["uf_publica"].uf_taxa_publica_t1.iloc[0] != pytest.approx(0.80)

    def test_muda_junto_com_o_ano_pedido(self):
        """Pedir 2025 tem de devolver o contexto de 2024, não o de 2025."""
        ctx = _contexto_do_ano(gold_minimo(), 2025)
        assert ctx["mun_publica"].mun_taxa_publica_t1.iloc[0] == pytest.approx(0.40)
        assert ctx["meta_mun"].mun_meta_ano.iloc[0] == pytest.approx(0.65)
