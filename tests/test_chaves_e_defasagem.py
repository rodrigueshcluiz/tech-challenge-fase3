"""Chave determinística, arredondamento compatível com Spark e defasagem temporal.

A defasagem é o ponto mais delicado do projeto: se o contexto territorial vier do
ano corrente, ele deriva dos próprios alunos que o modelo prevê e o alvo vaza.
"""
import pandas as pd
import pytest

from src.preprocessing.aluno_features import _contexto_defasado
from src.utils import round_half_up, sha256_concat_ws, texto_int


class TestArredondamento:
    def test_meio_vai_para_longe_do_zero_como_no_spark(self):
        """O round do numpy é bancário e divergiria da Gold do Databricks."""
        assert round_half_up(pd.Series([0.12345]), 4).iloc[0] == pytest.approx(0.1235)
        assert round_half_up(pd.Series([0.12355]), 4).iloc[0] == pytest.approx(0.1236)

    def test_negativo_arredonda_simetricamente(self):
        assert round_half_up(pd.Series([-0.12345]), 4).iloc[0] == pytest.approx(-0.1235)


class TestChaveDeterministica:
    def test_inteiro_anulavel_vira_texto_sem_sufixo_decimal(self):
        """Um '2024.0' no lugar de '2024' mudaria todos os hashes."""
        s = pd.Series([2024, None], dtype="Int64")
        assert texto_int(s, "na").tolist() == ["2024", "na"]

    def test_mesma_entrada_gera_o_mesmo_hash(self):
        partes = [pd.Series(["2024"]), pd.Series(["SP"]), pd.Series(["3550308"])]
        assert sha256_concat_ws(partes).iloc[0] == sha256_concat_ws(partes).iloc[0]

    def test_campos_diferentes_geram_hashes_diferentes(self):
        a = sha256_concat_ws([pd.Series(["2024"]), pd.Series(["SP"])]).iloc[0]
        b = sha256_concat_ws([pd.Series(["2025"]), pd.Series(["SP"])]).iloc[0]
        assert a != b

    def test_separador_evita_colisao_entre_campos_concatenados(self):
        """Sem separador, ('ab','c') e ('a','bc') colidiriam."""
        a = sha256_concat_ws([pd.Series(["ab"]), pd.Series(["c"])]).iloc[0]
        b = sha256_concat_ws([pd.Series(["a"]), pd.Series(["bc"])]).iloc[0]
        assert a != b


class TestDefasagemTemporal:
    @pytest.fixture
    def gold(self):
        def mun(ano, taxa):
            return {"ano": ano, "id_municipio": "3550308", "rede": 5,
                    "taxa_alfabetizacao": taxa, "nivel_alfabetizacao": 4,
                    "variacao_absoluta": 0.02}

        def uf(ano, taxa):
            return {"ano": ano, "sigla_uf": "SP", "rede": 5,
                    "taxa_alfabetizacao": taxa, "variacao_absoluta": 0.02}

        return {
            "indicador_municipio": pd.DataFrame([mun(2023, 0.50), mun(2024, 0.60)]),
            "evolucao_municipio": pd.DataFrame([mun(2023, 0.50), mun(2024, 0.60)]),
            "resumo_uf": pd.DataFrame([uf(2023, 0.55), uf(2024, 0.65)]),
            "evolucao_uf": pd.DataFrame([uf(2023, 0.55), uf(2024, 0.65)]),
            "meta_vs_resultado_municipio": pd.DataFrame(
                [{"ano": 2024, "id_municipio": "3550308", "meta_taxa": 0.62}]),
            "meta_vs_resultado_uf": pd.DataFrame(
                [{"ano": 2024, "sigla_uf": "SP", "meta_taxa": 0.60}]),
        }

    def test_contexto_municipal_e_endereçado_ao_ano_seguinte(self, gold):
        ctx = _contexto_defasado(gold)
        linha = ctx["mun_publica"].set_index("ano").loc[2024]
        # O valor entregue para 2024 é o resultado de 2023.
        assert linha.mun_taxa_publica_t1 == pytest.approx(0.50)

    def test_contexto_nao_entrega_o_resultado_do_proprio_ano(self, gold):
        ctx = _contexto_defasado(gold)
        linha = ctx["mun_publica"].set_index("ano").loc[2024]
        assert linha.mun_taxa_publica_t1 != pytest.approx(0.60)

    def test_contexto_estadual_tambem_e_defasado(self, gold):
        ctx = _contexto_defasado(gold)
        assert (ctx["uf_publica"].set_index("ano").loc[2024].uf_taxa_publica_t1
                == pytest.approx(0.55))

    def test_metas_nao_sao_defasadas(self, gold):
        """A meta é conhecida antes da avaliação e não deriva do resultado
        corrente: entra no ano a que se refere."""
        ctx = _contexto_defasado(gold)
        assert ctx["meta_mun"].iloc[0].ano == 2024
        assert ctx["meta_mun"].iloc[0].mun_meta_ano == pytest.approx(0.62)

    def test_primeiro_ano_da_serie_nao_gera_contexto(self, gold):
        """2023 é o ano-base: não há 2022 para alimentar sua defasagem."""
        ctx = _contexto_defasado(gold)
        assert 2023 not in set(ctx["mun_publica"].ano)
