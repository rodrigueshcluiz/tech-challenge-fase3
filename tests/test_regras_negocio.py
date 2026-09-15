"""Regras de negócio que, se mudarem em silêncio, invalidam a Gold inteira.

O caso mais importante aqui é o domínio de rede: a Fase 2 rotulava o código 5
como "privada" quando ele é a rede pública agregada, e o erro atravessou painel,
KPIs e vídeo sem nenhum alarme disparar. Os testes deste arquivo existem para que
isso não possa acontecer de novo sem quebrar a suíte.
"""
import pandas as pd
import pytest

from src.config import (
    ALFABETIZACAO_CORTE, FAIXAS_ALFABETIZADAS, REDE_COMPOSICAO, REDE_MAP,
    REDE_META_MUNICIPIO, REDE_META_UF,
)
from src.preprocessing.silver import compor_escopos
from src.utils import faixa_label


class TestDominioDeRede:
    def test_codigo_5_e_publica_e_4_e_privada(self):
        """Regressão do erro da Fase 2. Fonte: dicionário da AEEB, aba TS_ESTADO."""
        assert REDE_MAP[5] == "publica"
        assert REDE_MAP[4] == "privada"

    def test_publica_compoe_estadual_e_municipal(self):
        assert REDE_COMPOSICAO[5] == {2, 3}

    def test_total_inclui_privada(self):
        assert 4 in REDE_COMPOSICAO[0]

    def test_escopos_de_meta_apontam_para_o_recorte_publicado(self):
        """O INEP publica meta de rede pública por UF e municipal por município."""
        assert REDE_META_UF == 5 and REDE_MAP[REDE_META_UF] == "publica"
        assert REDE_META_MUNICIPIO == 3 and REDE_MAP[REDE_META_MUNICIPIO] == "municipal"


class TestComposicaoDeEscopos:
    @pytest.fixture
    def por_dependencia(self):
        # Dois pesos por dependência, para a soma ponderada ser verificável na mão.
        return pd.DataFrame({
            "ano": [2024] * 3, "sigla_uf": ["SP"] * 3,
            "dep": [2, 3, 4],
            "peso": [100.0, 300.0, 100.0],
            "w_alfab": [50.0, 90.0, 90.0],
            "w_prof": [70000.0, 210000.0, 80000.0],
            "alunos": [10, 30, 10], "alunos_alfab": [5.0, 9.0, 9.0],
        })

    def test_publica_soma_estadual_e_municipal_e_exclui_privada(self, por_dependencia):
        out = compor_escopos(por_dependencia, ["ano", "sigla_uf"])
        publica = out[out.rede == 5].iloc[0]
        assert publica.peso == 400.0
        assert publica.w_alfab == 140.0
        # 140/400 = 35%. Se a privada entrasse, daria 230/500 = 46%.
        assert publica.taxa_ponderada == pytest.approx(0.35)

    def test_total_inclui_todas_as_dependencias(self, por_dependencia):
        out = compor_escopos(por_dependencia, ["ano", "sigla_uf"])
        assert out[out.rede == 0].iloc[0].peso == 500.0

    def test_taxa_e_ponderada_nao_media_simples(self, por_dependencia):
        """O indicador oficial pondera pelo peso amostral."""
        out = compor_escopos(por_dependencia, ["ano", "sigla_uf"])
        publica = out[out.rede == 5].iloc[0]
        media_simples = (50 / 100 + 90 / 300) / 2  # 0,40
        assert publica.taxa_ponderada != pytest.approx(media_simples)


class TestCorteDeAlfabetizacao:
    def test_corte_e_743(self):
        """Validado contra IN_ALFABETIZADO do INEP em 3,8 milhões de alunos."""
        assert ALFABETIZACAO_CORTE == 743

    def test_faixa_separa_no_corte_dentro_do_bloco_de_25_pontos(self):
        """O corte de 743 cai dentro do bloco 725–749: a banda não é derivável
        da faixa de pontos, e por isso as duas compõem o grão do mart."""
        prof = pd.Series([724.9, 725.0, 742.9, 743.0, 749.9])
        rotulos = faixa_label(prof).tolist()
        assert rotulos[:3] == ["3 · 700 a 742"] * 3
        assert rotulos[3:] == ["4 · 743 a 799"] * 2

    def test_apenas_as_bandas_acima_do_corte_contam_alfabetizados(self):
        prof = pd.Series([600.0, 742.9, 743.0, 900.0])
        acima = faixa_label(prof).isin(FAIXAS_ALFABETIZADAS)
        assert acima.tolist() == [False, False, True, True]
        assert (prof >= ALFABETIZACAO_CORTE).tolist() == acima.tolist()
