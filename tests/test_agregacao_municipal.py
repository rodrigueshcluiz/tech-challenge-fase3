"""Agregação da predição do aluno para o grão do município.

A agregação é o passo que converte um modelo fraco no indivíduo em um instrumento
utilizável pela política pública. Se ela estiver errada — peso ignorado, rede
errada, meta comparada com o escopo errado — o ranking de risco aponta municípios
que não estão em risco, e ninguém percebe olhando o número final.
"""
import numpy as np
import pandas as pd
import pytest

from src.config import REDE_META_MUNICIPIO
from src.modeling.municipio import (
    agregar, calibracao_do_risco, conferir_contra_mart, desvio_por_porte,
    metricas_de_risco, metricas_de_taxa, probabilidade_de_descumprir,
)


def contexto(redes, municipios, pesos, t1=0.5, meta=0.6, uf="SP"):
    return pd.DataFrame({
        "id_municipio": municipios,
        "sigla_uf": uf,
        "rede": pd.array(redes, dtype="Int64"),
        "mun_taxa_publica_t1": t1,
        "mun_taxa_rede_t1": t1,
        "mun_meta_ano": meta,
        "peso_amostral": pesos,
    })


class TestAgregacao:
    def test_taxa_prevista_e_a_media_ponderada_e_nao_a_simples(self):
        """O indicador oficial é ponderado; ignorar o peso muda o resultado."""
        d = contexto([3, 3], ["1", "1"], [1.0, 9.0])
        saida = agregar(d, probabilidade=[0.0, 1.0], alvo=[0, 1], peso=d.peso_amostral)
        assert saida.taxa_prevista.iloc[0] == pytest.approx(0.9)

    def test_so_a_rede_municipal_entra(self):
        """A meta por município é publicada para a rede municipal, e só para ela."""
        d = contexto([3, 2, 4], ["1", "1", "1"], [1.0, 1.0, 1.0])
        saida = agregar(d, probabilidade=[0.2, 1.0, 1.0], alvo=[0, 1, 1],
                        peso=d.peso_amostral)
        assert len(saida) == 1
        assert saida.taxa_prevista.iloc[0] == pytest.approx(0.2)

    def test_um_municipio_por_linha(self):
        d = contexto([3] * 4, ["1", "1", "2", "2"], [1.0] * 4)
        saida = agregar(d, [0.1, 0.3, 0.7, 0.9], [0, 0, 1, 1], d.peso_amostral)
        assert saida.id_municipio.tolist() == ["1", "2"]
        assert saida.taxa_prevista.tolist() == pytest.approx([0.2, 0.8])

    def test_sem_a_rede_municipal_falha_em_vez_de_devolver_vazio(self):
        """Devolver um quadro vazio faria o relatório sair com zero municípios."""
        d = contexto([2, 4], ["1", "1"], [1.0, 1.0])
        with pytest.raises(ValueError):
            agregar(d, [0.5, 0.5], [1, 0], d.peso_amostral)

    def test_tamanho_efetivo_cai_quando_os_pesos_sao_desiguais(self):
        """Com pesos muito desiguais, n linhas não valem n observações."""
        iguais = contexto([3] * 4, ["1"] * 4, [1.0] * 4)
        desiguais = contexto([3] * 4, ["1"] * 4, [1.0, 1.0, 1.0, 97.0])
        n_iguais = agregar(iguais, [0.5] * 4, [1] * 4, iguais.peso_amostral)
        n_desiguais = agregar(desiguais, [0.5] * 4, [1] * 4, desiguais.peso_amostral)
        assert n_iguais.alunos_efetivos.iloc[0] == pytest.approx(4.0)
        assert n_desiguais.alunos_efetivos.iloc[0] < 1.5


class TestProvaContraOMart:
    def test_reprova_quando_a_reconstrucao_nao_bate(self):
        agregado = pd.DataFrame({"id_municipio": ["1", "2"], "sigla_uf": "SP",
                                 "alunos_avaliados": [100, 100],
                                 "taxa_observada": [0.50, 0.90]})
        mart = pd.DataFrame({"ano": [2025, 2025], "id_municipio": ["1", "2"],
                             "taxa_alfabetizacao": [0.50, 0.50]})
        prova = conferir_contra_mart(agregado, mart, 2025)
        assert not prova["ok"]
        assert prova["maxima"] == pytest.approx(0.40)

    def test_aceita_a_diferenca_de_arredondamento_da_publicacao(self):
        """A planilha divulga arredondado; exigir zero reprovaria a quarta casa."""
        agregado = pd.DataFrame({"id_municipio": [str(i) for i in range(200)],
                                 "sigla_uf": "SP", "alunos_avaliados": 100,
                                 "taxa_observada": np.full(200, 0.500049)})
        mart = pd.DataFrame({"ano": 2025, "id_municipio": [str(i) for i in range(200)],
                             "taxa_alfabetizacao": 0.5})
        assert conferir_contra_mart(agregado, mart, 2025)["ok"]


class TestRisco:
    def base(self):
        # Dois abaixo da meta (0,6) e dois acima, na observação.
        return pd.DataFrame({
            "id_municipio": ["1", "2", "3", "4"],
            "meta_taxa": 0.6,
            "taxa_observada": [0.50, 0.55, 0.70, 0.75],
            "taxa_prevista": [0.50, 0.65, 0.65, 0.70],
            "taxa_t1": [0.50, 0.55, 0.70, 0.75],
        })

    def test_a_classe_positiva_e_ficar_abaixo_da_meta(self):
        """Inverter a classe positiva trocaria precisão por recall em silêncio."""
        m = metricas_de_risco(self.base(), "taxa_prevista")
        assert m["verdadeiros_positivos"] == 1   # município 1
        assert m["falsos_negativos"] == 1        # município 2, previsto acima
        assert m["falsos_positivos"] == 0
        assert m["verdadeiros_negativos"] == 2
        assert m["recall"] == pytest.approx(0.5)

    def test_previsao_perfeita_acerta_tudo(self):
        m = metricas_de_risco(self.base(), "taxa_t1")
        assert m["acuracia"] == pytest.approx(1.0)
        assert m["recall"] == pytest.approx(1.0)

    def test_erro_de_taxa_em_fracao_e_nao_em_pontos(self):
        """Erros de 0; +0,10; -0,05 e -0,05: média absoluta 0,05 e viés nulo.

        O viés zero com erro médio de 5 p.p. é o caso que um número só esconderia.
        """
        m = metricas_de_taxa(self.base(), "taxa_prevista")
        assert m["erro_medio_absoluto"] == pytest.approx(0.05)
        assert m["vies"] == pytest.approx(0.0)
        assert m["raiz_erro_quadratico"] > m["erro_medio_absoluto"]


class TestProbabilidade:
    def quadro(self):
        n = 40
        return pd.DataFrame({
            "id_municipio": [str(i) for i in range(n)],
            "meta_taxa": 0.60,
            "taxa_prevista": np.linspace(0.40, 0.80, n),
            "taxa_observada": np.linspace(0.40, 0.80, n),
            "erro": np.linspace(-0.05, 0.05, n),
            "alunos_efetivos": np.linspace(20, 2000, n),
        })

    def test_probabilidade_cai_conforme_a_previsao_sobe(self):
        d = self.quadro()
        p = probabilidade_de_descumprir(d, desvio_por_porte(d))
        assert p.iloc[0] > 0.9 and p.iloc[-1] < 0.1
        assert (p.diff().dropna() <= 1e-9).all()

    def test_fica_entre_zero_e_um(self):
        d = self.quadro()
        p = probabilidade_de_descumprir(d, desvio_por_porte(d))
        assert p.between(0, 1).all()

    def test_previsao_na_meta_da_meio_a_meio(self):
        d = self.quadro().assign(taxa_prevista=0.60)
        p = probabilidade_de_descumprir(d, desvio_por_porte(d))
        assert p.round(6).eq(0.5).all()


class TestCalibracao:
    def test_confronta_o_declarado_com_o_observado(self):
        """Uma probabilidade sem esta tabela é um número sem lastro."""
        d = pd.DataFrame({
            "id_municipio": [str(i) for i in range(4)],
            "probabilidade_descumprir": [0.1, 0.1, 0.9, 0.9],
            "meta_taxa": 0.60,
            # Só um dos dois "alto risco" descumpriu: 50% contra 90% declarados.
            "taxa_observada": [0.70, 0.70, 0.50, 0.70],
        })
        c = calibracao_do_risco(d, cortes=(0, 0.5, 1.0))
        assert c.municipios.tolist() == [2, 2]
        assert c.risco_medio_previsto.tolist() == pytest.approx([0.1, 0.9])
        assert c.descumpriram_de_fato.tolist() == pytest.approx([0.0, 0.5])
