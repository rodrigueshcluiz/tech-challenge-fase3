"""Quadro de features no grão do município.

Mesma regra do quadro de aluno e do de projeção, e o mesmo modo de errar:
**resultado vem de t-1, meta vem do ano corrente**. Buscar o indicador do ano
corrente vazaria o alvo, e buscar a meta de t-1 compararia o município com um
alvo vencido. Nenhum dos dois mudaria o formato da saída.
"""
import numpy as np
import pandas as pd
import pytest

from src.config import REDE_META_MUNICIPIO, REDE_META_UF
from src.modeling.modelo_municipal import (
    CATEGORICAS, FEATURES, NUMERICAS, montar_quadro, prever, treinar,
)
from src.report import Relatorio


def gold_minimo():
    """Dois municípios e três anos, para que escolher o ano errado mude o valor."""
    linhas = []
    for ano, taxa_mun, taxa_pub, media in ((2024, 0.40, 0.42, 700.0),
                                           (2025, 0.50, 0.52, 710.0),
                                           (2026, 0.60, 0.62, 720.0)):
        for municipio, ajuste in (("1", 0.0), ("2", 0.05)):
            for rede, taxa in ((REDE_META_MUNICIPIO, taxa_mun), (REDE_META_UF, taxa_pub)):
                linhas.append({
                    "ano": ano, "id_municipio": municipio, "sigla_uf": "SP",
                    "regiao": "Sudeste", "capital": 0, "latitude": -23.5,
                    "longitude": -46.6, "rede": rede,
                    "taxa_alfabetizacao": taxa + ajuste,
                    "media_portugues": media, "nivel_alfabetizacao": 3,
                })
    resumo = pd.DataFrame([{"ano": a, "sigla_uf": "SP", "rede": REDE_META_UF,
                            "taxa_alfabetizacao": t}
                           for a, t in ((2024, 0.70), (2025, 0.75), (2026, 0.80))])
    metas_mun = pd.DataFrame([{"ano": a, "id_municipio": m, "meta_taxa": t}
                              for a, t in ((2025, 0.65), (2026, 0.72), (2027, 0.78))
                              for m in ("1", "2")])
    metas_uf = pd.DataFrame([{"ano": a, "sigla_uf": "SP", "meta_taxa": t}
                             for a, t in ((2025, 0.85), (2026, 0.88), (2027, 0.90))])
    return {"indicador_municipio": pd.DataFrame(linhas), "resumo_uf": resumo,
            "metas_municipio": metas_mun, "metas_uf": metas_uf}


@pytest.fixture
def quadro(monkeypatch, tmp_path):
    """Neutraliza INSE e taxas de rendimento: dependem de arquivos do INEP."""
    vazio_inse = pd.DataFrame(columns=["id_municipio", "rede", "mun_inse_media",
                                       "mun_inse_pct_vulneravel", "mun_inse_alunos"])
    vazio_taxas = pd.DataFrame(columns=["ano", "id_municipio", "rede",
                                        "mun_aprovacao_1ano_t1", "mun_aprovacao_2ano_t1",
                                        "mun_reprovacao_2ano_t1",
                                        "mun_abandono_iniciais_t1"])
    monkeypatch.setattr("src.modeling.modelo_municipal.ler_inse",
                        lambda raw, rel: vazio_inse)
    monkeypatch.setattr("src.modeling.modelo_municipal.ler_taxas_rendimento",
                        lambda raw, rel: vazio_taxas)
    return lambda ano: montar_quadro(gold_minimo(), tmp_path, ano, Relatorio())


class TestQuadroMunicipal:
    def test_o_resultado_vem_do_ano_anterior(self, quadro):
        d = quadro(2026).set_index("id_municipio")
        assert d.loc["1"].mun_taxa_rede_t1 == pytest.approx(0.50)
        assert d.loc["1"].mun_taxa_publica_t1 == pytest.approx(0.52)
        assert d.loc["1"].uf_taxa_publica_t1 == pytest.approx(0.75)

    def test_nao_usa_o_indicador_do_proprio_ano(self, quadro):
        """Se usasse, o alvo de 2026 estaria entre as features."""
        d = quadro(2026).set_index("id_municipio")
        assert d.loc["1"].mun_taxa_rede_t1 != pytest.approx(0.60)

    def test_a_meta_vem_do_ano_projetado(self, quadro):
        """A meta é a única que olha para a frente: é publicada antes da prova."""
        d = quadro(2026).set_index("id_municipio")
        assert d.loc["1"].mun_meta_ano == pytest.approx(0.72)
        assert d.loc["1"].uf_meta_ano == pytest.approx(0.88)

    def test_muda_junto_com_o_ano_pedido(self, quadro):
        d = quadro(2025).set_index("id_municipio")
        assert d.loc["1"].mun_taxa_rede_t1 == pytest.approx(0.40)
        assert d.loc["1"].mun_meta_ano == pytest.approx(0.65)

    def test_o_alvo_e_a_taxa_do_proprio_ano(self, quadro):
        d = quadro(2025).set_index("id_municipio")
        assert d.loc["1"].alvo == pytest.approx(0.50)
        assert d.loc["2"].alvo == pytest.approx(0.55)

    def test_um_registro_por_municipio(self, quadro):
        d = quadro(2025)
        assert len(d) == d.id_municipio.nunique() == 2

    def test_traz_todas_as_features_declaradas(self, quadro):
        assert not set(FEATURES) - set(quadro(2025).columns)

    def test_categoricas_saem_como_texto(self, quadro):
        d = quadro(2025)
        for c in CATEGORICAS:
            assert d[c].dtype == "string"

    def test_numericas_saem_sem_pd_na(self, quadro):
        """O Int64 do pandas carrega pd.NA, que o sklearn recusa no passthrough."""
        d = quadro(2025)
        for c in NUMERICAS:
            assert d[c].dtype == np.dtype("float64")


class TestAnoAindaNaoAvaliado:
    """2027 não existe no indicador: é o caso da projeção de um ano futuro."""

    def test_o_quadro_existe_mesmo_sem_indicador_do_ano(self, quadro):
        """A espinha cai para os municípios de t-1, que são os projetáveis."""
        d = quadro(2027)
        assert len(d) == 2
        assert d.alvo.isna().all()

    def test_o_contexto_vem_do_ultimo_ano_avaliado(self, quadro):
        d = quadro(2027).set_index("id_municipio")
        assert d.loc["1"].mun_taxa_rede_t1 == pytest.approx(0.60)
        assert d.loc["1"].mun_meta_ano == pytest.approx(0.78)


class TestTreinoEPrevisao:
    def test_ano_sem_alvo_nao_pode_virar_treino(self, quadro):
        with pytest.raises(ValueError):
            treinar([quadro(2027)], n_estimators=5)

    def test_previsao_fica_no_intervalo_valido(self, quadro):
        modelo = treinar([quadro(2025), quadro(2026)], n_estimators=5)
        p = prever(modelo, quadro(2027))
        assert p.between(0, 1).all()
        assert len(p) == 2
