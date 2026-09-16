# Predição e Inteligência Analítica para Alfabetização no Brasil

Tech Challenge, Fase 3. Modelo supervisionado que prevê se um aluno do 2º ano
será considerado alfabetizado, construído sobre a camada Gold e usado para
estimar o risco de cada município não cumprir a meta de alfabetização.

Para gestores: painel em `reports/dashboard_executivo.html`. A parte técnica
está neste README e em `reports/`.

## Contexto do problema

O Compromisso Nacional Criança Alfabetizada estabelece que toda criança deve
estar alfabetizada até o fim do 2º ano do ensino fundamental. O INEP mede isso
com o Indicador Criança Alfabetizada: é alfabetizado o aluno que atinge 743
pontos na escala de Língua Portuguesa da Avaliação da Alfabetização. A meta
nacional para 2030 é 80%.

O resultado de um ano sai meses depois da prova. Gestores precisam saber antes
disso quais municípios tendem a ficar abaixo da meta e quais fatores pesam no
indicador.

## Objetivo analítico

Prever se um aluno será alfabetizado ou não a partir de variáveis educacionais,
territoriais e socioeconômicas, e agregar essa previsão ao grão do município
para estimar o risco de descumprimento da meta.

## Descrição da base

Todas as fontes são oficiais do INEP e cobrem 2023, 2024 e 2025.

| Fonte | Conteúdo |
|---|---|
| Microdados da Avaliação da Alfabetização | 4,3 milhões de alunos com proficiência e peso amostral; agregados por UF e município |
| Planilhas de resultados e metas (3 divulgações) | metas do Compromisso Nacional por UF (rede pública) e por município (rede municipal), 2024 a 2030 |
| INSE 2023 | nível socioeconômico médio por município e rede |
| Taxas de rendimento 2023 a 2025 | aprovação, reprovação e abandono por município e rede |
| IBGE (`data/external`) | UF, região, município, capital, coordenadas |

Os arquivos não são versionados (cerca de 190 MB). `data/raw/README.md` tem a
URL de cada um.

### Camada Gold

Dez marts em Parquet, um grão por mart, gerados por `gerar_gold.py`:

| Mart | Linhas | Grão |
|---|---:|---|
| `indicador_municipio` | 36.411 | ano + município + rede |
| `resumo_uf` | 225 | ano + UF + rede |
| `meta_vs_resultado_uf` | 76 | ano + UF (rede pública) |
| `meta_vs_resultado_municipio` | 16.396 | ano + município (rede municipal) |
| `metas_uf` | 187 | ano + UF, 2024 a 2030 |
| `metas_municipio` | 38.334 | ano + município, 2024 a 2030 |
| `evolucao_uf` | 225 | ano + UF + rede |
| `evolucao_municipio` | 36.411 | ano + município + rede |
| `distribuicao_proficiencia` | 4.837 | ano + UF + rede + faixa |
| `aluno_features` | 3.817.947 | ano + aluno |

O contrato de cada tabela está em [`CONTRACT.md`](CONTRACT.md). As metas por
município valem para a rede municipal; as metas por UF, para a rede pública.

### Base de treino (`aluno_features`)

Uma linha por aluno avaliado em 2024 e 2025. O ano de 2023 não entra como
treino porque não tem ano anterior para fornecer contexto.

| Grupo | Colunas |
|---|---|
| Alvo | `alfabetizado` (0/1) |
| Identificação | `ano`, `id_aluno`, `id_escola_ano`, `id_municipio`, `sigla_uf` |
| Aluno e escola | `rede`, `rede_label`, `escola_alunos_avaliados`, `mun_alunos_avaliados` |
| Território | `regiao`, `capital`, `latitude`, `longitude` |
| Contexto municipal, ano anterior | `mun_taxa_rede_t1`, `mun_taxa_publica_t1`, `mun_nivel_t1`, `mun_variacao_publica_t1` |
| Contexto estadual, ano anterior | `uf_taxa_publica_t1`, `uf_variacao_publica_t1` |
| Metas do ano | `mun_meta_ano`, `uf_meta_ano` |
| Socioeconômico | `mun_inse_media`, `mun_inse_pct_vulneravel`, `mun_inse_alunos` |
| Rendimento escolar, ano anterior | `mun_aprovacao_1ano_t1`, `mun_aprovacao_2ano_t1`, `mun_reprovacao_2ano_t1`, `mun_abandono_iniciais_t1` |
| Peso amostral | `peso_amostral` |

Alvo: 63,1% de alfabetizados (62,5% ponderado pelo peso amostral).

Duas dessas colunas não chegam ao modelo. `mun_variacao_publica_t1` e
`uf_variacao_publica_t1` são a variação da taxa medida em t-1, ou seja, exigem
t-2: para um aluno de 2024, a taxa de 2023 menos a de 2022, que não existe.
Ficam 100% nulas no ano de treino, e `features_utilizaveis()` as descarta em
vez de imputar um valor inventado. Permanecem na Gold porque passam a ser
utilizáveis quando o treino incluir 2025.

Tratamento de vazamento, feito na construção da base:

- Todo indicador de resultado entra defasado em um ano. A taxa do município no
  ano corrente é calculada a partir dos próprios alunos que o modelo prevê.
  Duas verificações automáticas conferem que o contexto é o do ano anterior e
  que não coincide com o do ano corrente.
- As metas entram no ano a que se referem: são publicadas antes da avaliação e
  derivadas do resultado anterior.
- A proficiência não está na base. Uma verificação falha se ela aparecer.
- O peso amostral entra como `sample_weight`, nunca como feature.

O código da escola nos microdados é mascarado e sorteado de novo a cada ano.
Por isso a coluna `id_escola_ano` só vale dentro do ano e serve para duas
coisas: porte da escola e agrupamento da validação cruzada. Não permite cruzar
com Censo Escolar nem montar histórico por escola.

Os microdados não trazem nenhuma variável do aluno (sexo, idade, raça,
domicílio). Entre alunos do mesmo município e da mesma rede, só a escola varia.

## Como reproduzir

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python gerar_gold.py
./.venv/bin/python treinar_modelo.py
./.venv/bin/python prever_municipios.py
```

| comando | o que faz | tempo |
|---|---|---|
| `gerar_gold.py` | Bronze, Silver, Quality Gate e Gold; grava `data/gold`, `reports/RELATORIO_VALIDACAO.md` e `reports/manifest.json` | ~40 s |
| `otimizar_modelo.py` | busca de hiperparâmetros dentro de 2024; `reports/OTIMIZACAO.md` | ~1 h |
| `treinar_modelo.py` | treina e compara os modelos no grão do aluno; `reports/MODELAGEM.md` | ~12 min (`--sem-shap`: ~2 min) |
| `prever_municipios.py` | afere o método contra 2025 e projeta 2026 por município; `reports/RISCO_MUNICIPAL.md` | ~2 min |

Se uma verificação bloqueante falhar em `gerar_gold.py`, nenhum Parquet é
gravado. Os scripts de modelagem aceitam `--amostra N` para iteração rápida, com
amostragem por escola.

```bash
./.venv/bin/pytest
```

63 testes cobrem as regras que invalidariam o resultado se mudassem: domínio de
rede, corte de alfabetização, consolidação das metas, chave determinística,
defasagem temporal, agregação municipal e montagem do quadro de projeção.

## Estrutura

```
tech-challenge-fase3
├── data
│   ├── raw/            fontes do INEP (não versionadas)
│   ├── external/       dimensões do IBGE
│   ├── gold/           saída do pipeline (.parquet)
│   └── predictions/    risco municipal aferido e projetado (.parquet)
├── notebooks/          análise exploratória (script em células)
├── src
│   ├── config.py       caminhos, domínios, constantes
│   ├── preprocessing/  bronze, silver, quality_gate, gold, aluno_features
│   ├── modeling/       dados, pipeline, otimização, agregação municipal, projeção
│   ├── evaluation/     validação da Gold e métricas
│   └── visualization/
├── tests/
├── reports/            validação, EDA, modelagem, otimização, risco, auditoria, painel
├── images/
├── CONTRACT.md
├── gerar_gold.py · otimizar_modelo.py · treinar_modelo.py · prever_municipios.py
└── requirements.txt
```

## Validação da camada de dados

100 verificações, 0 falhas, 3 avisos na última execução. As principais:

- O indicador nacional de 2024 recalculado dos microdados dá 59,1996% contra
  59,1973% publicado pelo INEP. Nos 222 recortes por UF e rede, a mediana da
  diferença é 0,0033 p.p.
- O corte de 743 pontos reproduz a flag `IN_ALFABETIZADO` do INEP em 100% dos
  alunos.
- Os resultados por UF batem com a planilha oficial (diferença máxima 0,0000 p.p.).
- As três divulgações de metas publicam os mesmos valores com precisões
  diferentes. Prevalece a mais recente; a mais antiga substitui quando concorda
  dentro de 0,5 p.p., por ter mais casas decimais. A coluna `meta_publicacao`
  registra a origem de cada valor.

## Etapas de modelagem

1. Análise exploratória: `notebooks/01_analise_exploratoria.py`, `reports/EDA.md`.
2. Engenharia de atributos: contexto territorial defasado, metas do ano, INSE e
   rendimento escolar, em `aluno_features`.
3. Pipeline scikit-learn com imputação, padronização e encoding dentro do
   `Pipeline`: `src/modeling/pipeline.py`.
4. Validação temporal (treino em 2024, teste em 2025) com `GroupKFold` por
   escola dentro do treino.
5. Busca de hiperparâmetros com `RandomizedSearchCV` dentro de 2024:
   `otimizar_modelo.py`.
6. Interpretabilidade por permutação e SHAP.
7. Agregação ao grão do município e ranking de risco: `prever_municipios.py`.

## Escolha do algoritmo

| Modelo | Papel |
|---|---|
| Taxa média | Piso. AUC 0,5 por construção. |
| Persistência (rede do aluno) | Taxa da rede do aluno no município no ano anterior, sem modelo. É a feature mais forte lida sozinha e o baseline de referência. |
| Persistência (rede pública) | Mesma ideia com a taxa da rede pública. Mantido para comparação. |
| Regressão logística | Referência linear. Imputação por mediana, padronização e one-hot. |
| Random forest | 200 árvores, profundidade 18, folha mínima 100. Imputação e one-hot. |
| Gradient boosting (histograma) | Árvores rasas encadeadas, early stopping. Trata nulos e categóricas nativamente. |

Floresta e boosting atacam o erro por caminhos diferentes (variância e viés).
Se os dois chegam ao mesmo resultado, o limite está nos dados.

O pré-processamento fica dentro do `Pipeline` para que cada fold da validação
ajuste imputador e scaler só com os próprios dados de treino.

Hiperparâmetros: 15 configurações por modelo, avaliadas por `GroupKFold` dentro
de 2024. Nenhuma foi adotada. O ganho em validação cruzada ficou entre 0,0000 e
0,0017 de AUC, e a única configuração com ganho aparente (floresta) piorou em
2025, de 0,6407 para 0,6381. O critério de adoção passou a exigir dois desvios
entre folds. Detalhes em `reports/OTIMIZACAO.md`, incluindo dois testes feitos
depois: profundidade de 6 a sem limite não muda AUC nem Brier (12 dá o mesmo
modelo que 18 com um terço do tamanho), e remover features por importância
piora em todo subconjunto.

## Métricas de avaliação

Todas ponderadas pelo peso amostral.

- AUC-ROC e precisão média: discriminação.
- Brier e log loss: calibração das probabilidades.
- Acurácia e F1 no corte de 0,5: acerto por classe.

Acurácia e F1 estão na tabela, mas não decidem nada aqui. O baseline que prevê
a taxa média para todos classifica todo aluno como alfabetizado e assim obtém o
maior F1 do conjunto (0,7926) e acurácia igual à taxa base (0,6565), com AUC
0,5. Como 66% dos alunos são alfabetizados, responder sempre a classe
majoritária já acerta dois terços das vezes.

Além disso, o modelo não é usado como classificador: a saída é a probabilidade,
que depois é somada por município. No grão do município, onde existe uma decisão
binária de verdade (cumprir ou não a meta), acurácia, precisão, recall e F1 são
reportados em `reports/RISCO_MUNICIPAL.md`.

Validação temporal: treino em 2024, teste em 2025. Dentro do treino, `GroupKFold`
por escola, para que alunos da mesma escola não fiquem dos dois lados da divisão.

## Interpretação dos resultados

Grão do aluno, teste em 2025:

| modelo | AUC | Brier | log loss | acurácia | F1 |
|---|---:|---:|---:|---:|---:|
| Persistência (rede do aluno) | 0,6433 | 0,2190 | 0,6278 | 0,6431 | 0,7390 |
| Random forest | 0,6407 | 0,2146 | 0,6170 | 0,6576 | 0,7687 |
| Persistência (rede pública) | 0,6397 | 0,2193 | 0,6282 | 0,6428 | 0,7441 |
| Gradient boosting | 0,6394 | 0,2166 | 0,6211 | 0,6504 | 0,7551 |
| Regressão logística | 0,6322 | 0,2209 | 0,6319 | 0,6464 | 0,7523 |
| Taxa média | 0,5000 | 0,2297 | 0,6521 | 0,6565 | 0,7926 |

Em discriminação, nenhum modelo supera a taxa da rede do aluno no ano anterior
lida sozinha. Os três algoritmos ficam entre 0,632 e 0,641. O ganho do modelo
está na calibração: a floresta reduz o Brier em 2,0% e o log loss em 1,7% em
relação à persistência.

A última linha mostra por que acurácia e F1 não servem de critério neste
problema. A taxa média classifica todo aluno como alfabetizado e obtém o melhor
F1 da tabela e acurácia igual à taxa base, sem discriminar nada (AUC 0,5).

Overfit e underfit, medidos numa amostra de 300 mil alunos por ano: a floresta
faz AUC 0,698 no treino, 0,653 em validação cruzada e 0,638 em 2025. Sem limite
de profundidade e folha, 0,731 no treino e 0,633 em 2025. A curva de aprendizado
é plana: de 30 mil para 1,85 milhão de alunos de treino, o AUC em 2025 vai de
0,635 para 0,641. A validação cruzada agrupada por município dá o mesmo que
agrupada por escola (0,654 contra 0,653).

A queda de cerca de 0,03 entre a validação cruzada dentro de 2024 (0,662 a 0,669)
e o teste em 2025 (0,632 a 0,641) é o custo de prever o ano seguinte. Uma divisão
aleatória esconderia essa diferença.

Importância por permutação na floresta: `mun_taxa_rede_t1` (0,0120),
`mun_meta_ano` (0,0058), `mun_taxa_publica_t1` (0,0041), `mun_nivel_t1` (0,0018).
O SHAP ordena da mesma forma. As quatro medem o mesmo território no passado.
INSE e rendimento escolar aparecem com contribuição pequena.

### Grão do município

A pergunta do gestor é se o município vai cumprir a meta. Somando as
probabilidades dos alunos por município e rede municipal (`prever_municipios.py`):

| | erro médio da taxa | AUC do risco de meta |
|---|---:|---:|
| Modelo agregado | 10,2 p.p. | 0,750 |
| Repetir o ano anterior | 12,4 p.p. | 0,752 |

No grão do município o modelo reduz o erro da taxa em 2,2 p.p. (18%). A
ordenação empata com a persistência; o ganho está no nível da taxa prevista. A
taxa observada reconstruída dos microdados reproduz o indicador publicado em
99,89% dos 5.500 municípios dentro de 0,1 p.p.

`prever_municipios.py` ajusta dois modelos. O de aferição treina só em 2024 e
mede o erro contra 2025. O de produção treina em 2024 e 2025 e projeta 2026,
usando o roteiro de alunos de 2025 como molde e trocando todo o contexto pelo
de 2026. A projeção supõe que a composição dos municípios (escolas e pesos)
não muda de um ano para o outro.

## Insights encontrados

1. A escola explica de 13,5% a 14,5% da variância do alvo, mais que município
   (8,1% a 8,3%) e UF (3,7% a 4,0%) somados. No município mediano, a melhor e
   a pior escola diferem 41 p.p.
2. 86% da variação está entre alunos da mesma escola, e a fonte não traz
   nenhuma variável de aluno. Esse é o teto do modelo.
3. O INSE correlaciona +0,02 com o alvo no grão do aluno e +0,14 no grão do
   município. A variável é constante dentro do município, onde a variação
   acontece.
4. A taxa do município no ano anterior correlaciona +0,71 com o resultado. É o
   preditor dominante.
5. O salto de 59,2% para 65,6% na rede pública entre 2024 e 2025 se mantém com
   o conjunto de UFs fixo. Não é efeito de cobertura.
6. Centro-Oeste (73,8%) lidera; o Nordeste (66,0%) está acima do Sudeste
   (64,7%).
7. Agregar ao município leva o AUC de 0,64 para 0,75 e reduz em 18% o erro de
   repetir o ano anterior.
8. As metas de 2025 exigiam do município mediano +2,3 p.p.; o avanço realizado
   foi +7,9 p.p.
9. O Rio Grande do Sul caiu 19,3 p.p. entre 2023 e 2024. O modelo de aferição
   herdou esse ano como patamar e projetou descumprimento para 129 dos 200
   municípios de maior risco; a maioria cumpriu.
10. O erro por município é maior nos pequenos: 12,4 p.p. no quartil de menor
    porte contra 7,8 p.p. no de maior. 13,4% do erro é ruído amostral da própria
    taxa observada.
11. Há 8 pares de features com correlação acima de 0,80. A importância é de
    grupos de variáveis, não de variáveis isoladas; podar piora o resultado.

## Perguntas de negócio

### Quais fatores mais impactam a alfabetização?

A decomposição da variância do alvo aponta para a escola, que responde por 13,5%
a 14,5% da variação, enquanto o município explica 8,1% a 8,3% e a UF fica entre
3,7% e 4,0%. No município mediano existem 41 pontos percentuais entre a melhor e
a pior escola. O problema é que a fonte não traz nenhuma variável de escola nem
de aluno, então esse fator aparece na medição mas não pode ser usado.

Entre as variáveis que existem, a mais forte é o histórico do próprio território:
a taxa do município no ano anterior correlaciona +0,71 com o resultado. Depois
vêm o nível socioeconômico municipal e o fluxo escolar dos anos iniciais,
principalmente o abandono.

### Quais municípios apresentam maior risco?

A lista completa está em `data/predictions/risco_2026_projetado.parquet` e no
painel executivo, com a probabilidade estimada para cada município e o porte da
rede ao lado, porque a margem de erro depende dele.

Para saber quanto confiar nessa lista, aferimos o mesmo procedimento contra
2025: 815 municípios receberam probabilidade de 80% ou mais de descumprir a meta,
e 60% deles descumpriram de fato. A ordenação funciona; o valor absoluto da
probabilidade é pessimista.

### Quais regiões possuem padrões semelhantes?

Por nível de alfabetização, as regiões não se separam como se esperaria: em 2025
o Centro-Oeste lidera com 73,8%, o Nordeste aparece em 66,0% e o Sudeste fica
atrás, com 64,7%.

O recorte que revela grupos consistentes é a velocidade de avanço. Entre 2024 e
2025, na rede municipal, Bahia subiu 19,4 pontos percentuais, Acre 17,5, Piauí
17,1, Alagoas 15,3 e Paraíba 15,1, e foram esses estados que puxaram o salto
nacional. Ceará e Santa Catarina praticamente não se moveram (-1,5 e +1,9), mas
por razões opostas: Santa Catarina está em 64,7% e o Ceará já alcançou 83,9%,
acima da meta nacional de 2030.

### É possível prever quais municípios não atingirão as metas?

Sim, dentro de uma margem conhecida. Treinando apenas com 2024 e prevendo 2025,
o erro médio da taxa municipal é de 10,2 pontos percentuais e o AUC para separar
quem cumpre de quem não cumpre a meta é 0,750.

A projeção para 2026 aponta 1.039 de 4.972 municípios abaixo da meta, ou 20,9%,
contra os 27,9% que ficaram abaixo em 2025. Esse número deve ser lido como teto.
O modelo subestimou 2025 em 6,4 pontos percentuais porque não tem como antecipar
saltos de nível como o que aconteceu naquele ano, e a mesma limitação vale para
2026.

### Quais variáveis mais influenciam o modelo?

Permutação e SHAP produzem a mesma ordem, e as quatro primeiras colocadas medem
o mesmo território no ano anterior: a taxa da rede do aluno no município, a meta
do ano, a taxa da rede pública e o nível de alfabetização do município. INSE e
taxas de rendimento aparecem depois, com contribuição pequena.

Vale ler esse ranking como ordem de grupos, não de variáveis isoladas. Há oito
pares de features com correlação acima de 0,80, e as quatro primeiras são
praticamente a mesma informação medida de quatro maneiras.

## Limitações do projeto

- Os microdados não têm variáveis de aluno. Nenhum algoritmo alcança
  discriminação alta com o que existe.
- O código de escola é mascarado e muda a cada ano. Não é possível enriquecer
  o nível que mais explica o resultado.
- Todo enriquecimento é municipal e, por isso, constante dentro do município.
- Só há dois anos treináveis. Não dá para estimar a dispersão do erro entre
  anos nem validar em mais de um ponto no tempo.
- A projeção de 2026 não pode ser validada até o INEP publicar o resultado.
- O modelo não antecipa mudança de nível. Capturou 45% do salto de 2025 e
  herda choques do ano anterior, como o do Rio Grande do Sul, como se fossem
  estrutura.
- A probabilidade de descumprir é calibrada nos resíduos de 2025 e tende a ser
  otimista em um ano ainda não avaliado.
- `escola_alunos_avaliados` e `mun_alunos_avaliados` são contados no próprio
  ano. Servem como proxy de porte; a alternativa é a matrícula do Censo Escolar
  do ano anterior, ainda não ingerida.
- As metas sobem todo ano, então `mun_meta_ano` também carrega o tempo. Para
  horizontes além de 2026, árvores não extrapolam.
- O indicador nacional de 2023 não é reproduzível a partir dos microdados por
  UF (24 UFs avaliadas). Um recorte de 2024 (PB, rede estadual) diverge 0,70 p.p.
  do agregado publicado.

## Aplicação prática para políticas públicas

O projeto entrega uma lista de priorização por município, com margem de erro
declarada, disponível assim que o ano anterior fecha.

1. **Priorização antes do resultado.** O ranking de 2026 permite decidir onde
   colocar formação continuada e material estruturado no início do ano letivo.
2. **Margem por porte.** Municípios pequenos têm erro maior; o relatório
   estratifica a incerteza para que um município de 40 alunos não seja lido com
   a mesma confiança que um de 3.000.
3. **Calibração das metas.** As metas de 2025 pediram menos do que o sistema
   entregou. Isso é insumo para a negociação do próximo ciclo.
4. **Meta descalibrada após choque.** As metas do Rio Grande do Sul foram
   calculadas sobre o patamar de 2023 (63,5%). O estado caiu para 44,2% em 2024
   e recuperou para 52,1% em 2025; a meta mediana de 2026 é 75,9%, contra 69,4%
   no país. Por isso 280 dos 299 municípios gaúchos aparecem em risco. Não é
   indicador de gestão; é caso de repactuação.
5. **Detecção de ano atípico.** Uma queda como a do RS contamina toda a projeção
   do estado. Monitorar variação atípica por UF evita ler um choque como
   tendência.

O projeto não autoriza decisão sobre uma criança específica. A unidade de
decisão é o território.

## Possíveis evoluções futuras

- Variáveis de aluno (sexo, idade, raça, trajetória), que dependem de acesso a
  microdado identificado. É onde está o ganho.
- Chave de escola estável, para cruzar Censo Escolar e INSE por escola.
- Censo Escolar agregado, FUNDEB, Censo 2022 do IBGE e Cadastro Único.
- Correção explícita de deriva entre anos e intervalo de predição por
  reamostragem.
- Um modelo direto no grão do município, para comparar com a agregação.
- Quando 2026 sair: validação com origem rolante (2024 → 2025, 2024+2025 →
  2026) e conferência da projeção contra o resultado.
- Persistir o modelo treinado e versionar as predições junto ao manifesto da
  Gold.
