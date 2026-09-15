"""Critério de adoção da configuração ajustada.

A busca sempre devolve um vencedor — é o máximo de uma lista, existe mesmo quando
todos os candidatos empatam. Adotar esse vencedor sem critério é como escolher a
face mais frequente de vinte lançamentos de moeda: o número sobe na validação e
não sobrevive fora do tempo. A regra aqui é a que separa ajuste de barulho.
"""
import pandas as pd
import pytest

from src.modeling.otimizacao import ESPACOS, Busca, _limpar, adotar
from src.modeling.pipeline import MODELOS


def busca(score_melhor, score_padrao, desvio, config=None):
    return Busca(modelo="floresta", melhor_config=config or {"max_depth": 10},
                 score_melhor=score_melhor, score_padrao=score_padrao,
                 desvio_melhor=desvio, n_candidatos=15, segundos=1.0,
                 tabela=pd.DataFrame())


class TestAdocao:
    def test_adota_quando_o_ganho_supera_o_ruido_entre_folds(self):
        assert adotar(busca(0.680, 0.660, 0.002)) == {"max_depth": 10}

    def test_mantem_o_padrao_quando_o_ganho_cabe_dentro_do_desvio(self):
        """0,002 de ganho com 0,004 de desvio entre folds não é ganho."""
        assert adotar(busca(0.662, 0.660, 0.004)) == {}

    def test_mantem_o_padrao_quando_a_busca_piora(self):
        assert adotar(busca(0.650, 0.660, 0.001)) == {}

    def test_empate_exato_nao_troca(self):
        """Na dúvida fica o padrão, que tem justificativa estrutural."""
        assert adotar(busca(0.660, 0.660, 0.0)) == {}

    def test_ganho_minimo_pode_ser_mais_exigente_que_o_desvio(self):
        b = busca(0.670, 0.660, 0.001)
        assert adotar(b) == {"max_depth": 10}
        assert adotar(b, ganho_minimo=0.05) == {}


class TestGanho:
    def test_o_ganho_e_medido_sobre_a_discriminacao_e_nao_sobre_o_auc_bruto(self):
        """AUC 0,5 é a moeda: 0,60 para 0,70 é +50% de discriminação, não +17%."""
        assert busca(0.70, 0.60, 0.001).ganho == pytest.approx(1.0)


class TestEspacos:
    def test_todo_modelo_registrado_tem_espaco_de_busca(self):
        assert set(ESPACOS) == set(MODELOS)

    def test_as_chaves_enderecam_o_passo_do_pipeline(self):
        """Sem o prefixo `modelo__`, o sklearn não sabe a quem aplicar o parâmetro."""
        for espaco in ESPACOS.values():
            assert all(c.startswith("modelo__") for c in espaco)

    def test_os_parametros_sao_aceitos_pelo_construtor(self):
        """Pega erro de digitação no espaço antes de gastar uma hora de busca."""
        for nome, espaco in ESPACOS.items():
            config = {c.removeprefix("modelo__"): v[0] for c, v in espaco.items()}
            pipeline = MODELOS[nome](["mun_meta_ano"], ["sigla_uf"], **config)
            atuais = pipeline.named_steps["modelo"].get_params()
            for chave, valor in config.items():
                assert atuais[chave] == valor

    def test_limpar_devolve_configuracao_reutilizavel(self):
        assert _limpar({"modelo__max_depth": 8}) == {"max_depth": 8}
