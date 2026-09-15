# Modelagem — predição de alfabetização no grão do aluno

Treino em 2024 (59,647 alunos, 1,371 escolas), teste em 2025 (59,444 alunos). Divisão temporal, validação cruzada agrupada por escola, tudo ponderado pelo peso amostral.

## Resultados

| modelo | auc_roc | precisao_media | brier | log_loss | taxa_base |
|---|---:|---:|---:|---:|---:|
| persistencia_municipal | 0,6302 | 0,7618 | 0,2219 | 0,6335 | 0,6553 |
| floresta | 0,6270 | 0,7584 | 0,2183 | 0,6259 | 0,6553 |
| logistica | 0,6188 | 0,7500 | 0,2265 | 0,6452 | 0,6553 |
| boosting | 0,6133 | 0,7485 | 0,2265 | 0,6446 | 0,6553 |
| taxa_base | 0,5000 | 0,6553 | 0,2303 | 0,6534 | 0,6553 |

### Validação cruzada dentro do treino

| modelo | AUC média | desvio entre folds |
|---|---:|---:|
| logistica | 0.6468 | 0.0069 |
| floresta | 0.6532 | 0.0053 |
| boosting | 0.6386 | 0.0045 |

### Ganho sobre a persistência territorial

O baseline que importa não é a moeda: é prever, para cada aluno, a taxa do seu município no ano anterior. Ele não usa aprendizado nenhum.

- **taxa_base**: -100.0% de discriminação sobre a persistência
- **logistica**: -8.8% de discriminação sobre a persistência
- **floresta**: -2.5% de discriminação sobre a persistência
- **boosting**: -13.0% de discriminação sobre a persistência

## Interpretabilidade

### Importância por permutação (queda de AUC ao embaralhar)

| feature | queda_de_auc |
|---|---:|
| mun_taxa_rede_t1 | 0,0342 |
| sigla_uf | 0,0150 |
| mun_inse_alunos | 0,0041 |
| mun_taxa_publica_t1 | 0,0040 |
| longitude | 0,0019 |
| mun_meta_ano | 0,0016 |
| mun_abandono_iniciais_t1 | 0,0012 |
| mun_aprovacao_1ano_t1 | 0,0009 |
| mun_aprovacao_2ano_t1 | 0,0006 |
| mun_inse_media | 0,0004 |
| mun_alunos_avaliados | 0,0003 |
| regiao | 0,0000 |

**Features descartadas:** `mun_variacao_publica_t1`, `uf_variacao_publica_t1` — inteiramente nulas em 2024, porque a variação em t-1 exige t-2. Sob divisão temporal elas estariam presentes só no teste, e o modelo nunca teria visto um valor delas.
## Figuras

![desempenho](../images/06_desempenho_modelos.png)

![importância](../images/07_importancia_permutacao.png)
