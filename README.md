# Tech Challenge Fase 3 — Predição e Inteligência Analítica para Alfabetização no Brasil

Projeto integrador da Fase 3. Parte da camada Gold construída na Fase 2 e a
utiliza para análise exploratória e modelagem supervisionada da alfabetização
infantil.

**Estado atual:** a camada Gold está reconstruída, validada e materializada em
Parquet, agora sobre fontes 100% oficiais do INEP. A modelagem é a próxima etapa.

---

## Contexto do problema

O Compromisso Nacional Criança Alfabetizada estabelece que toda criança deve
estar alfabetizada até o fim do 2º ano do ensino fundamental. O INEP mede isso
com o Indicador Criança Alfabetizada: é considerado alfabetizado o aluno que
atinge **743 pontos** na escala de Língua Portuguesa da Avaliação da
Alfabetização.

Saber o resultado de hoje não basta. Gestores precisam antecipar risco,
identificar territórios vulneráveis e entender quais fatores movem o indicador.

## Objetivo analítico

Desenvolver um modelo supervisionado que preveja se um aluno será considerado
**alfabetizado ou não alfabetizado**, a partir de variáveis educacionais,
territoriais e socioeconômicas, e extrair dele inteligência aplicável a política
pública.

## Descrição da base

Toda a base vem de fontes oficiais do INEP, cobrindo **2023, 2024 e 2025**.

### Fontes

| Fonte | Conteúdo |
|---|---|
| Microdados da AEEB (2023, 2024, 2025) | `TS_ALUNO` — 4,3 milhões de alunos com proficiência e peso amostral; `TS_ESTADO` e `TS_MUNICIPIO` — agregados oficiais |
| Planilhas "Resultados e metas" (3 divulgações) | metas oficiais do Compromisso Nacional por UF (rede pública) e por município (rede municipal), 2024–2030 |
| IBGE (`data/external`) | dimensões territoriais: UF, região, município, capital, coordenadas |

`data/raw/README.md` traz a URL de cada arquivo. Eles não são versionados (~82 MB).

### Camada Gold

Oito marts, **um grão por mart**, em `data/gold`:

| Mart | Linhas | Grão |
|---|---:|---|
| `indicador_municipio` | 36.411 | ano + município + rede |
| `resumo_uf` | 225 | ano + UF + rede |
| `meta_vs_resultado_uf` | 76 | ano + UF *(escopo: rede pública)* |
| `meta_vs_resultado_municipio` | 16.396 | ano + município *(escopo: rede municipal)* |
| `evolucao_uf` | 225 | ano + UF + rede |
| `evolucao_municipio` | 36.411 | ano + município + rede |
| `distribuicao_proficiencia` | 4.837 | ano + UF + rede + faixa |
| `aluno_features` | 3.817.947 | **ano + aluno** — base de treino do modelo |

Tipos legíveis sem conversão por Spark, DuckDB, Polars e pandas: texto `string`,
inteiros `int64`, decimais `double`, datas `timestamp[us, UTC]`.

### `aluno_features` — a base de treino

Uma linha por aluno avaliado em **2024 e 2025** (3,8 milhões). 2023 não entra como
ano de treino por ser o primeiro da série e não ter contexto anterior — mas
alimenta as features defasadas de 2024.

| Grupo | Colunas |
|---|---|
| Alvo | `alfabetizado` (0/1) |
| Identificação | `ano`, `id_aluno`, `id_escola_ano`, `id_municipio`, `sigla_uf` |
| Aluno / escola | `rede`, `rede_label`, `escola_alunos_avaliados`, `mun_alunos_avaliados` |
| Território | `regiao`, `capital`, `latitude`, `longitude` |
| Contexto municipal (t-1) | `mun_taxa_rede_t1`, `mun_taxa_publica_t1`, `mun_nivel_t1`, `mun_variacao_publica_t1` |
| Contexto estadual (t-1) | `uf_taxa_publica_t1`, `uf_variacao_publica_t1` |
| Metas (ano corrente) | `mun_meta_ano`, `uf_meta_ano` |
| Socioeconômico (INSE 2023) | `mun_inse_media`, `mun_inse_pct_vulneravel`, `mun_inse_alunos` |
| Rendimento escolar (t-1) | `mun_aprovacao_1ano_t1`, `mun_aprovacao_2ano_t1`, `mun_reprovacao_2ano_t1`, `mun_abandono_iniciais_t1` |
| Peso amostral | `peso_amostral` |

Distribuição do alvo: **63,1%** alfabetizados (62,5% ponderado). 85.866 grupos de
escola disponíveis para validação.

**Como o vazamento foi tratado**

- Todo indicador de *resultado* vem de **t-1**. A taxa do município em 2024 é
  calculada a partir dos próprios alunos que o modelo prevê — usá-la vazaria o
  alvo. Duas verificações automáticas confirmam a defasagem: uma confere que o
  contexto bate com o indicador de t-1, e a contraprova confere que ele **não**
  coincide com o do ano corrente.
- As **metas são exceção legítima**: publicadas antes da avaliação e derivadas do
  resultado anterior, não do corrente.
- A **proficiência não está na base**. É o alvo antes do corte de 743; incluí-la
  tornaria o problema trivial. Há uma verificação que falha se ela aparecer.
- `peso_amostral` é peso de desenho amostral — entra como `sample_weight` no
  treino, nunca como feature.

**Sobre `id_escola_ano`.** O INEP publica o código da escola **mascarado, com
códigos fictícios resorteados a cada ano** (confirmado no dicionário da AEEB e
por teste: dos 42.497 códigos comuns entre 2024 e 2025, apenas 2,0% apontam para
o mesmo município). Ele **não joina** com Censo Escolar nem INSE, e não permite
montar histórico por escola. Por isso a coluna sai como par `ano-código`, válida
só dentro do ano, e serve para duas coisas: porte da escola e `GroupKFold`, para
que colegas do mesmo aluno não fiquem divididos entre treino e teste.

**Enriquecimento municipal.** Duas fontes do INEP, ambas publicadas já agregadas
por município — o que contorna o código de escola mascarado:

- **INSE 2023** (`MEDIA_INSE` por município e rede). Sai a cada dois anos junto
  com o SAEB, então entra como característica estrutural, não como série. Para os
  alunos de 2024 é defasagem de um ano; para os de 2025, de dois.
- **Taxas de rendimento 2023 e 2024**, defasadas em um ano como todo indicador de
  resultado. Incluem o recorte por ano escolar: `mun_aprovacao_1ano_t1` é a
  aprovação no 1º ano — a mesma coorte, um ano antes da prova.

Cobertura quase total: INSE com 0,1% de faltantes e as taxas entre 0,0% e 0,3%.

**Valores faltantes.** `mun_variacao_publica_t1` (54,3%) e `uf_variacao_publica_t1`
(49,6%) só existem para 2025, porque a variação em t-1 exige t-2. As demais ficam
abaixo de 9%. A imputação é responsabilidade do pipeline de ML, como o enunciado
pede.

**Correlação bivariada com o alvo** (amostra de 300 mil), para calibrar
expectativa antes de modelar:

| Feature | Correlação |
|---|---:|
| `mun_taxa_publica_t1` | +0,246 |
| `mun_abandono_iniciais_t1` | −0,126 |
| `mun_aprovacao_1ano_t1` | +0,060 |
| `mun_inse_media` | +0,040 |
| `mun_inse_pct_vulneravel` | −0,033 |
| `mun_reprovacao_2ano_t1` | −0,023 |

Duas leituras contraintuitivas valem discussão no relatório. O **INSE quase não
correlaciona** (+0,04): o gradiente socioeconômico existe, mas a maior parte dele
vive *dentro* do município, entre escolas e famílias — e só temos a média
municipal. E a **aprovação no 2º ano tem média de 98,1%**, quase sem variância,
efeito da progressão continuada; é uma feature provavelmente descartável.

**Limite conhecido.** Não há variáveis demográficas do aluno na fonte — sem sexo,
idade, raça ou dados do domicílio. Entre alunos do mesmo município e da mesma
rede, só variam a escola e o porte dela. O teto do modelo está posto por essa
ausência, não pela modelagem.

### Domínio de rede

Conforme o dicionário oficial da AEEB — atenção, o código **5 é pública**, não
privada:

| Código | Escopo |
|---|---|
| 0 | Total (federal + estadual + municipal + privada) |
| 1 | Federal |
| 2 | Estadual |
| 3 | Municipal |
| 4 | Privada |
| 5 | **Pública** (estadual + municipal) |
| 6 | Pública com federal |

## Como reproduzir

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python gerar_gold.py
```

Baixe antes as fontes para `data/raw` (ver `data/raw/README.md`). A geração leva
cerca de 10 segundos e grava os Parquet em `data/gold`, o relatório de
verificação em `reports/RELATORIO_VALIDACAO.md` e o manifesto (linhas, colunas,
SHA-256) em `reports/manifest.json`.

Se qualquer verificação bloqueante falhar, **nenhum Parquet é gravado** e o
processo sai com código 1.

## Estrutura

```
tech-challenge-fase3
├── data
│   ├── raw/          fontes oficiais do INEP (não versionadas)
│   ├── external/     dimensões territoriais do IBGE
│   └── gold/         saída do pipeline (.parquet)
├── notebooks/        análise exploratória (script em células `# %%`)
├── tests/            testes das regras de negócio
├── src
│   ├── config.py     caminhos, domínios oficiais, constantes
│   ├── utils.py      funções compartilhadas
│   ├── report.py     coleta das verificações
│   ├── preprocessing/  bronze · silver · quality_gate · gold
│   ├── modeling/     pipeline de ML
│   ├── evaluation/   validação da Gold e métricas de modelo
│   └── visualization/
├── reports/          relatório de validação e manifesto
├── images/
├── gerar_gold.py     ponto de entrada do pipeline de dados
├── requirements.txt
└── README.md
```

## Validação da camada de dados

83 verificações aprovadas, 0 falhas, 3 avisos na última execução. As decisivas:

- **O pipeline reproduz o indicador oficial.** Recalculado a partir de 2,1
  milhões de registros ponderados, o indicador nacional de 2024 da rede pública
  dá **59,1996%** contra **59,1973%** publicados pelo INEP. Nos 222 recortes por
  UF e rede, a mediana da diferença é 0,0033 p.p.
- **A regra de negócio está validada pela fonte.** O corte de 743 pontos
  reproduz a flag `IN_ALFABETIZADO` do INEP em 100% dos alunos avaliados.
- **Os resultados por UF batem com a planilha oficial** — diferença máxima
  0,0000 p.p.
- Grão único em cada mart, nenhuma medição perdida entre Silver e Gold,
  `gap_meta` e `atingiu_meta` conferidos por recálculo independente, e toda meta
  com origem e escopo declarados.

### Precedência entre as divulgações de meta

As três divulgações publicam a mesma meta com precisões diferentes (2023 traz o
float completo, 2024 duas casas, 2025 inteiros), mas algumas metas foram de fato
**recalculadas** — o Acre não participou da avaliação de 2023 e as metas dos seus
municípios foram revisadas depois, em até 26,47 p.p.

Por isso o valor vigente é sempre o da divulgação mais recente; a mais antiga só
o substitui quando as duas concordam dentro de 0,5 p.p., aí é o mesmo alvo com
mais casas decimais. A coluna `meta_publicacao` registra qual divulgação forneceu
cada valor. Hoje: 37.499 metas municipais vêm de 2023, 674 de 2024 e 161 de 2025.

## Testes

```bash
./.venv/bin/pytest
```

31 testes sobre as regras que, se mudarem em silêncio, invalidam a Gold inteira:
domínio e composição dos escopos de rede, corte de alfabetização e as faixas em
torno dele, leitura e consolidação das metas, chave determinística, arredondamento
compatível com Spark, e a defasagem temporal da `aluno_features`.

O caso central é o **guarda de regressão do código de rede**. O erro da Fase 2 —
rotular o código 5 como "privada" quando ele é a rede pública — atravessou painel,
KPIs e vídeo sem nenhum alarme disparar. Reintroduzir esse erro hoje quebra a
suíte imediatamente (verificado por mutação: dois testes falham).

Os testes cobrem funções puras e rodam em menos de meio segundo, sem depender dos
arquivos do INEP. São complementares ao `RELATORIO_VALIDACAO.md`, que valida os
dados a cada execução: um verifica a regra, o outro verifica o resultado.

## Correções em relação à Fase 2

1. **Código de rede trocado.** O `REDE_MAP` da Fase 2 rotulava o código 5 como
   "privada" quando ele é a rede **pública** agregada. A coluna bate exatamente
   com o resultado oficial da rede pública (0,0000 p.p. nas 25 UFs de 2024) e
   fica entre estadual e municipal em 25 de 25 casos. O filtro "Rede pública" do
   painel usava média simples das redes 2 e 3, errando até 12,40 p.p.
2. **Metas eram projeção.** A Fase 2 interpolava linearmente até 100% em 2030; a
   meta oficial é "> 80%". A meta municipal era a estadual replicada — as
   oficiais variam de verdade (519 valores distintos em SP num único ano).
3. **Procedência da meta perdida no join.** Agora toda meta carrega
   `meta_origem`, `meta_escopo`, `meta_publicacao` e `meta_limiar`; quando não há
   meta, `meta_status` diz por quê.
4. **Escopo de meta e resultado alinhados.** O INEP publica meta de rede pública
   no grão UF e de rede municipal no grão município. Cada mart de meta usa um
   único escopo.
5. **Grão misto separado.** `meta_vs_resultado` e `evolucao_temporal` viraram
   dois marts cada, por nível territorial.
6. **Alunos reais.** Os 11.600 alunos simulados deram lugar a 4,3 milhões de
   registros reais com peso amostral.

## Notas de leitura dos dados

1. **Escolha o escopo de rede conscientemente.** Média simples das redes 2 e 3
   não é a rede pública; use a rede 5.
2. **O número nacional é ponderado, não é a média das UFs.** Em 2024 a média
   simples dá 56,6%; o indicador nacional é 59,2%.
3. **Nem toda UF tem meta.** Ceará, Acre e Distrito Federal já superam o patamar
   e só têm o piso de "> 80" em 2030. Um ranking filtrado por "tem meta" exclui
   justamente as melhores.
4. **2023 não tem meta** — é o ano-base da trajetória.
5. **A cobertura cresce no tempo:** 24 UFs em 2023, 25 em 2024, 27 em 2025. Toda
   comparação entre anos precisa fixar o conjunto de UFs.
6. **O nacional de 2023 não é reproduzível** a partir do microdado estadual: a
   avaliação cobriu 24 UFs e o número publicado tem abrangência maior. Os valores
   por UF conferem.
7. **`meta_limiar = true` é piso, não alvo pontual.**

---

## Etapas de modelagem

*A preencher conforme o desenvolvimento.*

- [x] Análise exploratória — `notebooks/01_analise_exploratoria.py`, relatório em `reports/EDA.md`
- [x] Engenharia de atributos — contexto territorial defasado em `aluno_features`
- [x] Pipeline Scikit-learn com imputação, transformação e encoding integrados — `src/modeling/pipeline.py`
- [x] Tratamento de data leakage — contexto territorial defasado em `aluno_features`
- [x] Treinamento, validação e otimização — `treinar_modelo.py`
- [x] Interpretabilidade (Feature Importance, SHAP)

O tratamento de data leakage já está feito na camada de dados: `aluno_features`
traz todo indicador de resultado defasado em um ano, com verificação automática
nos dois sentidos. Ver a seção da base acima.

## Escolha do algoritmo

Dois modelos, e dois baselines que existem para dar sentido aos números.

| | Por quê |
|---|---|
| **Taxa média** | O piso absoluto. AUC 0,5 por construção. |
| **Persistência municipal** | Prevê, para cada aluno, a taxa do seu município no ano anterior. Não usa aprendizado nenhum — só uma coluna que já está na tabela. **É contra este que o modelo precisa ser comparado.** |
| **Regressão logística** | Referência linear. Imputação por mediana, padronização e one-hot, tudo dentro do `Pipeline`. |
| **Random forest** | 200 árvores fundas e independentes, depois a média. Ataca variância. Precisa de imputação e one-hot, não de escala. |
| **Gradient boosting em histograma** | Árvores rasas encadeadas, cada uma corrigindo a anterior. Ataca viés. Trata valor faltante nativamente e divide categóricas por conjunto. |

Floresta e boosting foram escolhidos por atacarem o erro por caminhos opostos —
variância contra viés. Se os dois chegam ao mesmo patamar, é evidência de que o
teto é dos dados, não do algoritmo.

O pré-processamento está **dentro** do `Pipeline`, não antes dele. Isso não é
estilo: um imputador ajustado fora aprenderia a mediana do conjunto inteiro,
teste incluído, e essa informação escorreria para o treino. Dentro do pipeline,
cada fold reajusta o pré-processamento só com os seus próprios dados.

**Duas features foram descartadas automaticamente**: `mun_variacao_publica_t1` e
`uf_variacao_publica_t1` são 100% nulas em 2024, porque variação em t-1 exige
t-2. Sob divisão temporal elas existiriam só no teste — o modelo nunca teria
visto um valor. O código detecta e descarta, em vez de imputar um número
inventado.

## Métricas de avaliação

Todas ponderadas pelo peso amostral — sem isso descrevem a amostra avaliada, não
a população de crianças.

- **AUC-ROC** e **precisão média**: discriminação, a capacidade de ordenar alunos.
- **Brier** e **log loss**: calibração, se a probabilidade prevista corresponde à
  frequência real. Num problema de sinal fraco, é onde o modelo pode agregar
  mesmo sem discriminar melhor.

**Validação:** divisão temporal (treina em 2024, testa em 2025) e, dentro do
treino, `GroupKFold` por escola. A divisão temporal mede o que interessa — se o
modelo serve no ano seguinte. O agrupamento por escola evita que colegas do mesmo
aluno fiquem dos dois lados da divisão: com 14,5% da variância entre escolas,
conhecer um colega é quase conhecer a resposta.

## Interpretação dos resultados

| modelo | AUC | Brier | log loss |
|---|---:|---:|---:|
| **Random forest** | **0,6407** | **0,2146** | **0,6170** |
| Persistência municipal | 0,6397 | 0,2193 | 0,6282 |
| Gradient boosting | 0,6394 | 0,2166 | 0,6211 |
| Regressão logística | 0,6322 | 0,2209 | 0,6319 |
| Taxa média | 0,5000 | 0,2297 | 0,6521 |

**A floresta supera a persistência territorial — por 0,001 de AUC.** Tecnicamente
é o melhor modelo; na prática, ganhar um milésimo de um baseline que não aprende
nada significa que **o aprendizado de máquina quase não acrescenta discriminação
aqui**. O boosting empata (0,6394) e a logística perde. Três algoritmos
diferentes chegando ao mesmo patamar é o que se espera quando o limite é dos
dados, não do método.

**O ganho real é em calibração.** A floresta leva o Brier de 0,2193 para 0,2146
e o log loss de 0,6282 para 0,6170 — uma melhora de 2,1% e 1,8% sobre a
persistência, ordens de grandeza acima do ganho em AUC. As probabilidades são
mais confiáveis mesmo ordenando quase igual, o que importa se a saída alimentar
alocação de recurso em vez de só um ranking.

**O custo de generalizar entre anos é visível:** dentro de 2024 a validação
cruzada dá AUC entre 0,662 e 0,669 para os três modelos; em 2025 todos caem para
a faixa de 0,632 a 0,641. Essa perda de cerca de 0,03 é a distância entre prever
o presente e prever o futuro, e só aparece porque a divisão é temporal. Uma
divisão aleatória a teria escondido.

**A importância confirma o diagnóstico.** Na floresta, `mun_taxa_rede_t1` lidera
a permutação (0,0120), seguida de `mun_meta_ano` (0,0058) e
`mun_taxa_publica_t1` (0,0041) — todas medidas do próprio território no passado.
O SHAP ordena igual. O INSE e as taxas de rendimento aparecem, mas com
contribuição marginal. **O modelo é, essencialmente, um mapa de onde a criança
mora.**

Vale notar o contraste entre os dois modelos de árvore: o boosting concentrou
quase toda a importância numa variável (0,064 em `mun_taxa_rede_t1`), enquanto a
floresta distribuiu (0,012 no topo). Mesma performance, leituras diferentes — a
floresta é mais informativa para explicar o fenômeno.

## Insights encontrados

Da análise exploratória (`reports/EDA.md`, com as figuras em `images/`):

1. **A escola explica 14,5% da variância do alvo** — mais que município (8,3%) e
   UF (3,7%) somados. É o nível mais informativo e o único que não podemos
   enriquecer, porque o código de escola do INEP é mascarado e resorteado a cada
   ano. No município mediano, a melhor e a pior escola diferem **41 p.p.**
2. **86% da variação acontece entre alunos da mesma escola**, e a fonte não traz
   nenhuma variável de aluno. O teto do modelo é da fonte, não da modelagem.
3. **O INSE parece irrelevante e não é**: +0,02 no grão do aluno, +0,14 no
   município, +0,16 dentro da UF. A diluição é consequência direta do item 2.
4. **Persistência territorial domina**: a taxa do município em t-1 correlaciona
   +0,71 com o resultado. O melhor preditor de onde um município estará é onde
   ele estava.
5. **O salto de 59,2% para 65,7% entre 2024 e 2025 é real**, não composição — a
   diferença se mantém com o conjunto de UFs fixo.
6. **A desigualdade regional não segue o eixo econômico**: Sudeste (64,7%) abaixo
   do Nordeste (66,0%), com o Centro-Oeste liderando (73,8%).

## Limitações do projeto

- O indicador nacional de 2023 não é reproduzível a partir dos microdados
  estaduais (cobertura parcial da avaliação naquele ano).
- Um recorte (PB 2024, rede estadual, 1.180 alunos) diverge 0,70 p.p. do
  agregado publicado, provavelmente por critério de publicação do INEP não
  codificado nos microdados.
- **O teto é da fonte, não do método.** 86% da variância do alvo está entre
  alunos da mesma escola, e os microdados não trazem nenhuma variável de aluno —
  sem sexo, idade, raça ou dados do domicílio. Nenhum algoritmo alcança
  discriminação alta com o que existe.
- **O nível mais informativo é inacessível.** A escola explica 14,5% da variância,
  mas o código de escola do INEP é mascarado e resorteado a cada ano: não joina
  com Censo Escolar nem com o INSE por escola, e não permite montar histórico.
- **O enriquecimento disponível é todo municipal** e, por isso, constante dentro
  do município — exatamente onde a variação acontece.
- A base ainda não inclui Censo Escolar agregado, FUNDEB municipal, Censo 2022 do
  IBGE nem Cadastro Único.

## Aplicação prática para políticas públicas

*A preencher.*

## Possíveis evoluções futuras

*A preencher.*
