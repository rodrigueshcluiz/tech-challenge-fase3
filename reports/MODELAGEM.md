# Modelagem — predição de alfabetização no grão do aluno

Treino em 2024 (1.851.852 alunos, 42.328 escolas), teste em 2025 (1.966.095 alunos). Divisão temporal, validação cruzada agrupada por escola, tudo ponderado pelo peso amostral.

## Resultados

| modelo | auc_roc | precisao_media | brier | log_loss | acuracia | f1 | taxa_base |
|---|---:|---:|---:|---:|---:|---:|---:|
| persistencia_rede | 0,6433 | 0,7741 | 0,2190 | 0,6278 | 0,6431 | 0,7390 | 0,6565 |
| floresta | 0,6407 | 0,7727 | 0,2146 | 0,6170 | 0,6576 | 0,7687 | 0,6565 |
| persistencia_publica | 0,6397 | 0,7724 | 0,2193 | 0,6282 | 0,6428 | 0,7441 | 0,6565 |
| boosting | 0,6394 | 0,7709 | 0,2166 | 0,6211 | 0,6504 | 0,7551 | 0,6565 |
| logistica | 0,6322 | 0,7631 | 0,2209 | 0,6319 | 0,6464 | 0,7523 | 0,6565 |
| taxa_base | 0,5000 | 0,6565 | 0,2297 | 0,6521 | 0,6565 | 0,7926 | 0,6565 |

### Validação cruzada dentro do treino

| modelo | AUC média | desvio entre folds |
|---|---:|---:|
| logistica | 0.6620 | 0.0013 |
| floresta | 0.6670 | 0.0011 |
| boosting | 0.6688 | 0.0013 |

### Ganho sobre a persistência territorial

O baseline que importa não é a moeda: é prever, para cada aluno, a taxa da sua rede no seu município no ano anterior (`persistencia_rede`). Ele não usa aprendizado nenhum, e é a feature mais forte do modelo lida sozinha. `persistencia_publica` usa a rede pública agregada e era o baseline publicado antes da revisão final; fica registrado porque a escolha da coluna decide o sinal da comparação em AUC.

- **taxa_base**: -100.0% de discriminação sobre a persistência
- **persistencia_publica**: -2.5% de discriminação sobre a persistência
- **logistica**: -7.8% de discriminação sobre a persistência
- **floresta**: -1.9% de discriminação sobre a persistência
- **boosting**: -2.7% de discriminação sobre a persistência

## Interpretabilidade

### Importância por permutação (queda de AUC ao embaralhar)

| feature | queda_de_auc |
|---|---:|
| mun_taxa_rede_t1 | 0,0644 |
| sigla_uf | 0,0174 |
| mun_alunos_avaliados | 0,0026 |
| mun_inse_media | 0,0026 |
| longitude | 0,0020 |
| mun_taxa_publica_t1 | 0,0016 |
| mun_abandono_iniciais_t1 | 0,0015 |
| mun_meta_ano | 0,0015 |
| mun_inse_alunos | 0,0013 |
| escola_alunos_avaliados | 0,0012 |
| latitude | 0,0012 |
| mun_aprovacao_1ano_t1 | 0,0011 |

### SHAP (magnitude média)

| feature | shap_medio |
|---|---:|
| categoricas__regiao | 0,2249 |
| numericas__uf_taxa_publica_t1 | 0,2148 |
| numericas__mun_taxa_rede_t1 | 0,1888 |
| categoricas__capital | 0,1328 |
| numericas__escola_alunos_avaliados | 0,1269 |
| numericas__mun_taxa_publica_t1 | 0,1080 |
| numericas__mun_meta_ano | 0,0856 |
| numericas__mun_abandono_iniciais_t1 | 0,0723 |
| numericas__mun_reprovacao_2ano_t1 | 0,0496 |
| numericas__mun_aprovacao_2ano_t1 | 0,0465 |
| numericas__mun_inse_pct_vulneravel | 0,0438 |
| categoricas__sigla_uf | 0,0401 |

**Features descartadas:** `mun_variacao_publica_t1`, `uf_variacao_publica_t1` — inteiramente nulas em 2024, porque a variação em t-1 exige t-2. Sob divisão temporal elas estariam presentes só no teste, e o modelo nunca teria visto um valor delas.
## Figuras

![desempenho](../images/06_desempenho_modelos.png)

![importância](../images/07_importancia_permutacao.png)
