"""Leitura e consolidação das metas oficiais.

Duas armadilhas reais das planilhas do INEP: a meta de 2030 vem como texto
("> 80"), e o valor 0 marca território sem meta, não alvo zero. E as três
divulgações publicam a mesma meta com precisões diferentes — exceto quando a
meta foi de fato recalculada, caso em que a mais recente tem de prevalecer.
"""
import pandas as pd
import pytest

from src.preprocessing.bronze import TOLERANCIA_ARREDONDAMENTO, _consolidar, _despivotar
from src.report import Relatorio


def planilha(metas: dict[int, str]) -> pd.DataFrame:
    """Monta uma linha de planilha com as colunas META_FINAL_* pedidas."""
    return pd.DataFrame({"sigla_uf": ["SP"],
                         **{f"META_FINAL_{ano}": [v] for ano, v in metas.items()}})


class TestDespivotar:
    def test_converte_percentual_em_fracao(self):
        out = _despivotar(planilha({2024: "60.5"}), ["sigla_uf"], 2023)
        assert out.iloc[0].meta == pytest.approx(0.605)

    def test_meta_limiar_vira_piso_numerico_e_fica_marcada(self):
        for texto in ("> 80", ">80"):
            out = _despivotar(planilha({2030: texto}), ["sigla_uf"], 2023)
            assert out.iloc[0].meta == pytest.approx(0.80)
            assert bool(out.iloc[0].meta_limiar) is True

    def test_meta_numerica_nao_e_marcada_como_limiar(self):
        out = _despivotar(planilha({2024: "60"}), ["sigla_uf"], 2023)
        assert bool(out.iloc[0].meta_limiar) is False

    def test_traco_significa_ausencia_de_meta(self):
        assert len(_despivotar(planilha({2024: "- "}), ["sigla_uf"], 2023)) == 0

    def test_zero_significa_territorio_sem_meta_publicada(self):
        """Município de nível 0 traz meta 0 — é ausência, não alvo de 0%."""
        assert len(_despivotar(planilha({2024: "0"}), ["sigla_uf"], 2023)) == 0

    def test_extrai_o_ano_do_nome_da_coluna(self):
        out = _despivotar(planilha({2024: "60", 2030: "80"}), ["sigla_uf"], 2023)
        assert sorted(out.ano) == [2024, 2030]


class TestConsolidarDivulgacoes:
    @pytest.fixture
    def rel(self):
        return Relatorio()

    def _partes(self, valores):
        """valores: {ano_da_divulgacao: meta_em_percentual}, todas para 2025."""
        return [_despivotar(planilha({2025: v}), ["sigla_uf"], pub)
                for pub, v in valores.items()]

    def test_prevalece_a_mais_precisa_quando_so_ha_arredondamento(self, rel):
        # 2023 publica o float completo; 2025 arredonda para inteiro.
        out = _consolidar(self._partes({2023: "55.5047", 2025: "56"}),
                          ["sigla_uf"], rel, "teste")
        assert out.iloc[0].meta == pytest.approx(0.555047)
        assert out.iloc[0].meta_publicacao == 2023

    def test_prevalece_a_mais_recente_quando_a_meta_foi_recalculada(self, rel):
        # Caso real: municípios do Acre, que não participou da avaliação de 2023.
        out = _consolidar(self._partes({2023: "24", 2025: "50"}),
                          ["sigla_uf"], rel, "teste")
        assert out.iloc[0].meta == pytest.approx(0.50)
        assert out.iloc[0].meta_publicacao == 2025

    def test_meia_casa_percentual_conta_como_arredondamento(self, rel):
        """A divulgação mais grosseira arredonda para inteiro, então 0,5 p.p. de
        diferença é arredondamento — e ponto flutuante não pode transformar isso
        num falso positivo."""
        assert TOLERANCIA_ARREDONDAMENTO > 0.005
        out = _consolidar(self._partes({2023: "55.5", 2025: "56"}),
                          ["sigla_uf"], rel, "teste")
        assert out.iloc[0].meta_publicacao == 2023

    def test_uma_linha_por_territorio_e_ano(self, rel):
        out = _consolidar(self._partes({2023: "55.5", 2024: "55.5", 2025: "56"}),
                          ["sigla_uf"], rel, "teste")
        assert len(out) == 1
