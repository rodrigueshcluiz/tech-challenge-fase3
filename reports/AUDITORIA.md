# Auditoria independente do projeto

Revisão conduzida sobre o estado do repositório na branch `otimizacao-hiperparametros`,
sem reaproveitar as verificações que o próprio pipeline executa — a ideia era
justamente procurar o que o pipeline não olha. Seis frentes: uso das fontes
oficiais, consistência, valores extremos, hipóteses do projeto, qualidade das
features e vazamento.

**Veredito curto:** nenhum erro que invalide número publicado. Dois achados
acionáveis (dado oficial não ingerido, redundância entre features), uma
afirmação do README levemente otimista, e um ponto conceitual sobre features
contemporâneas que vale registrar.

---

## 1. Todas as fontes oficiais estão sendo usadas?

**Arquivos:** os 13 arquivos em `data/raw` são consumidos; nenhum sobra, nenhum
falta. Corrigido hoje: `tx_rend_municipios_2025.zip` estava parado na pasta e
passou a compor o contexto da projeção de 2026.

### Achado 1.1 — nove colunas oficiais não ingeridas

`TS_MUNICIPIO` e `TS_ESTADO` trazem `PC_ALUNO_NIVEL_0_LP` … `PC_ALUNO_NIVEL_8_LP`:
a **distribuição completa dos alunos pelos nove níveis de proficiência**, por
município, rede e ano. O pipeline lê apenas `PC_ALUNO_ALFABETIZADO` e
`VL_MEDIA_LP` dessas tabelas, e as nove colunas de nível ficam de fora.

Isso não é detalhe. Dois municípios com a mesma taxa de 52% podem ter
distribuições muito diferentes — um com massa no nível 0, outro concentrado logo
abaixo do corte —, e o segundo tem muito mais chance de cruzar 743 no ano
seguinte. A taxa sozinha não distingue os dois casos.

Medi o ganho potencial, prevendo a taxa municipal de 2025 a partir do contexto de
2024 (regressão linear, 5 folds, 5.430 municípios):

| contexto de t-1 | R² |
|---|---:|
| só a taxa | 0,4749 |
| taxa + média de proficiência | 0,4814 |
| **taxa + 9 níveis** | **0,5042** |
| taxa + média + 9 níveis | 0,5062 |

**+0,029 de R², 6,2% de melhora relativa** num modelo linear no grão do município.

> **Atualização após implementar — leia antes de agir sobre este achado.** As nove
> colunas foram ingeridas e estão na Gold (`indicador_municipio` e `resumo_uf`),
> mas **não são utilizáveis como feature hoje**: a divulgação de **2023 não as
> publica**. Como o contexto é defasado, as linhas de 2024 — o ano de treino —
> ficariam inteiramente nulas, e `features_utilizaveis` as descartaria pelo mesmo
> motivo que já descarta `mun_variacao_publica_t1`. Elas entram em uso quando o
> treino puder incluir 2025, ou seja, no ciclo de 2026.
>
> Eu não verifiquei a cobertura por ano antes de escrever a recomendação. Era o
> primeiro teste a fazer.

### Achado 1.2 — `media_portugues` está na Gold e não vira feature

A média de proficiência do município em t-1 é lida, chega à Gold em
`indicador_municipio.media_portugues` e não aparecia em `aluno_features`. Ganho
isolado no teste linear municipal: +0,0065 de R².

> **Atualização após implementar: a recomendação estava errada.** Implementei,
> testei em base completa, e a feature **piora** o modelo:
>
> | conjunto | aluno: AUC | aluno: Brier | município: MAE | município: AUC |
> |---|---:|---:|---:|---:|
> | sem a média | **0,6407** | **0,2146** | **10,20 p.p.** | 0,7496 |
> | com a média | 0,6395 | 0,2149 | 10,34 p.p. | 0,7502 |
>
> O motivo é o mesmo do achado 5.1: `mun_media_lp_t1` correlaciona **0,930** com
> `mun_taxa_rede_t1` e carrega **menos** sinal sobre o alvo (0,225 contra 0,239).
> É uma cópia degradada. Numa floresta com `max_features="sqrt"`, acrescentá-la
> dilui o sorteio de variáveis a cada divisão e reduz a diversidade entre árvores
> — exatamente o mecanismo pelo qual a configuração ajustada da busca, com
> `max_features=0.5`, generalizou pior (ver `OTIMIZACAO.md`).
>
> A coluna **fica em `aluno_features`** para análise, e **fora de `NUMERICAS`**.
>
> A lição vale para o achado 1.1: o ganho de +0,029 de R² foi medido num modelo
> **linear** no grão do município, onde a média e a distribuição acrescentam o que
> uma função linear da taxa não expressa. Uma floresta já captura essa não
> linearidade a partir da própria taxa. **Dado oficial a mais não é
> automaticamente modelo melhor** — e é preciso testar no modelo de destino, não
> num proxy linear.

### O que corretamente ficou de fora

Os microdados de 2025 trazem `TX_RESPOSTA_BLOCO_1..4` e `TX_GABARITO_BLOCO_1..4` —
as respostas de cada aluno item a item, e os gabaritos. **Usá-las seria vazamento
total**: a proficiência é calculada por TRI a partir exatamente dessas respostas,
e o alvo é a proficiência acima de 743. Não são usadas, e não devem ser. Fica
registrado porque é o tipo de coluna que um enriquecimento apressado captura.

`IN_PREENCHIMENTO_LP` também não é usada, e não faz falta: ela é perfeitamente
equivalente a ter proficiência válida (355.158 de 355.158 numa amostra), que é o
filtro que o pipeline já aplica.

---

## 2. Consistência dos dados

### A regra de negócio é exata

O corte de 743 reproduz a flag oficial `IN_ALFABETIZADO` com **zero divergências
em 3.818.457 alunos** nos dois anos. Não é "bate quase sempre": é identidade.

### A Gold reproduz o publicado

Já verificado pelo pipeline e reconferido: 99,89% dos 5.500 municípios dentro de
0,1 p.p., mediana de 0,0025 p.p. Os 6 que divergem mais estão listados em
`RISCO_MUNICIPAL.md`, com o maior caso em 1,63 p.p.

### Achado 2.1 — cinco recortes existem no microdado e não na tabela publicada

Comparando as células município × rede do microdado de 2025 com as que o INEP
publica em `TS_MUNICIPIO`: **5 de 6.574 células não são publicadas** (n entre 7 e
35). Investiguei se seria supressão por tamanho amostral e **não é** — há células
publicadas com apenas 4 alunos. O motivo da ausência dessas cinco não é
explicável pelos dados disponíveis.

Consequência prática: a agregação municipal calcula taxa para recortes que o
INEP optou por não divulgar. São 4 municípios na rede municipal de 2025, todos
eliminados depois pelo filtro de meta publicada — ou seja, não contaminam
nenhum número do relatório. Mas vale saber que a Gold é, nesse ponto, mais
abrangente que a fonte.

---

## 3. Valores extremos

### Pesos amostrais: sem patologia

Mínimo 1,00 · mediana 1,095 · p99 1,70 · máximo 29,83. Nenhum peso nulo, negativo
ou faltante em 3,8 milhões de linhas. A razão máximo/mediana de 27 afeta poucos
casos e já é tratada pelo tamanho efetivo de Kish na estratificação da incerteza.

### Taxas de 0% e 100%: reais, não erro

122 municípios da rede municipal ficaram em 0% ou 100% em 2025. Investiguei os 4
em 0% na fonte: as proficiências são valores plausíveis (630 a 733), todas logo
**abaixo** do corte, e a flag oficial do INEP concorda que nenhum aluno foi
alfabetizado. Três são municípios pequenos da Paraíba que caíram de 58%, 100% e
30% em 2024 — queda drástica, mas o dado é o que a fonte diz. Não há o que
descartar.

### Achado 3.1 — 13,4% do erro medido é ruído do alvo, não do modelo

O erro-padrão binomial mediano da **taxa observada** é de 3,50 p.p. Num município
de 30 alunos ele chega a 7,6 p.p. — três quartos do erro médio do modelo
(10,2 p.p.). Decompondo a variância do erro de predição, **13,4% dela é atribuível
ao ruído amostral do próprio alvo**.

O modelo é, portanto, um pouco melhor do que o número publicado sugere. A
recomendação não é mudar o número — é registrar essa parcela junto dele.

### O corte de 30 alunos é robusto

Testei a sensibilidade das conclusões ao piso amostral:

| corte | municípios | MAE modelo | MAE persistência | ganho | AUC do risco |
|---:|---:|---:|---:|---:|---:|
| 30 | 4.959 | 10,20 | 12,40 | 2,20 | 0,7496 |
| 50 | 4.275 | 9,73 | 11,86 | 2,14 | 0,7486 |
| 100 | 2.947 | 9,16 | 11,12 | 1,96 | 0,7438 |
| 200 | 1.710 | 8,16 | 10,03 | 1,88 | 0,7449 |
| 400 | 834 | 7,22 | 8,84 | 1,62 | 0,7456 |

O MAE cai porque o ruído do alvo cai, mas **o ganho sobre a persistência
permanece e o AUC é estável em todos os cortes**. A conclusão do projeto não
depende de onde a linha foi traçada — que era o risco a descartar.

---

## 4. As hipóteses do projeto resistem?

Recalculei do zero as três afirmações centrais do README.

| afirmação do README | recálculo simples | estimador não enviesado (ICC) |
|---|---:|---:|
| escola explica 14,5% | 15,4% | **13,5%** |
| município explica 8,3% | 8,3% | 8,1% |
| UF explica 3,7% | 3,7% | 4,0% |

### Achado 4.1 — a variância da escola está ~1 p.p. otimista

A decomposição simples (variância das médias por grupo) **superestima**, porque a
média de um grupo pequeno carrega ruído amostral que entra como se fosse variação
real. Com o componente de variância da ANOVA de um fator, a escola fica em 13,5%.

As conclusões sobrevivem, com margem menor:
- escola ainda explica mais que município e UF **somados** (13,5% contra 12,1%),
  mas a folga cai de 2,5 para 1,4 p.p.;
- escola continua valendo **1,67×** o município (o README diz 1,7×);
- o "teto é dos dados" fica ainda mais forte: **86,5% da variância é dentro da
  escola**, onde não existe variável de origem.

**Sugestão:** trocar "14,5%" por "entre 13,5% e 14,5%, conforme o estimador" ou
adotar o ICC. É rigor, não correção de erro — a conclusão não muda.

### As outras duas hipóteses batem

**Diluição do INSE** confirmada: correlação com o alvo sobe de **+0,019** no grão
do aluno para **+0,135** no município e **+0,143** na UF. É exatamente o padrão
que o README descreve, e é consequência direta do item acima.

**Corte de 743**: zero divergências em 3,8 milhões de alunos (seção 2).

---

## 5. As features são as melhores possíveis?

### Achado 5.1 — oito pares redundantes em dezenove variáveis numéricas

| par | r |
|---|---:|
| `mun_aprovacao_2ano_t1` × `mun_reprovacao_2ano_t1` | −0,994 |
| `mun_taxa_rede_t1` × `mun_taxa_publica_t1` | +0,973 |
| `mun_inse_media` × `mun_inse_pct_vulneravel` | −0,945 |
| `mun_taxa_publica_t1` × `mun_nivel_t1` | +0,944 |
| `mun_taxa_rede_t1` × `mun_nivel_t1` | +0,920 |
| `mun_alunos_avaliados` × `mun_inse_alunos` | +0,918 |
| `uf_taxa_publica_t1` × `uf_meta_ano` | +0,841 |
| `latitude` × `mun_inse_media` | −0,823 |

Vários são redundantes **por construção**: aprovação e reprovação no 2º ano somam
quase 100%; `mun_nivel_t1` é uma discretização da taxa; a meta da UF é derivada da
taxa da UF. O par `latitude` × INSE é real, não artefato — no Brasil a geografia
é proxy de condição socioeconômica.

**Podar não melhora o desempenho.** Removi cinco redundantes (mantendo o de maior
correlação com o alvo de cada par) e testei numa amostra de 250 mil alunos/ano:

| conjunto | numéricas | AUC | Brier |
|---|---:|---:|---:|
| completo | 17 | 0,6394 | 0,2163 |
| podado | 12 | 0,6378 | 0,2170 |

Piora ligeiramente nos dois. Árvores extraem sinal complementar mesmo de
variáveis correlacionadas. **Recomendação: não podar.**

### Achado 5.2 — mas a redundância distorce a leitura de importância

Esta é a consequência que importa. Com features correlacionadas, a importância
por permutação **subestima ambas**: ao embaralhar uma, a outra compensa, e a
queda de AUC não aparece. Isso provavelmente explica o contraste que o README
atribui a diferença entre algoritmos — o boosting concentrando 0,064 numa
variável e a floresta espalhando 0,012 no topo. A floresta, por sortear
subconjuntos de variáveis em cada divisão, distribui o crédito entre correlatas;
o boosting fixa uma.

**Recomendação:** a seção de interpretabilidade deve dizer que o ranking é de
*grupos correlacionados*, não de variáveis isoladas. Os quatro primeiros lugares
(`mun_taxa_rede_t1`, `mun_meta_ano`, `mun_taxa_publica_t1`, `mun_nivel_t1`) são
quase a mesma informação medida de quatro formas.

### Transformações ausentes

`mun_alunos_avaliados` vai de 7 a 95.476 (mediana 1.152) — três ordens de
grandeza, sem transformação. Para as árvores é indiferente; para a regressão
logística, um `log1p` seria mais adequado que o `StandardScaler` aplicado ao
valor bruto. Impacto esperado pequeno, já que a logística é a referência e não o
modelo escolhido.

---

## 6. Há vazamento?

Auditei as três frentes, e **não encontrei vazamento material**.

### A meta é a única feature que olha para a frente — e está limpa

Era o ponto que mais merecia escrutínio. Se a meta de 2025 tivesse sido revisada
depois da avaliação de 2025, ela carregaria o resultado.

**98% das metas de 2025 vêm da divulgação de 2023** — dois anos antes da
avaliação. Apenas 10 municípios de 5.477 têm valor originado na divulgação de
2025. E as divulgações concordam entre si:

| comparação | pares | diferença mediana | acima de 0,5 p.p. |
|---|---:|---:|---:|
| 2023 vs 2024 | 5.232 | 0,002 p.p. | 0 |
| 2023 vs 2025 | 5.324 | 0,194 p.p. | 0 |
| 2024 vs 2025 | 5.323 | 0,200 p.p. | 10 |

As metas não foram recalculadas em função do resultado. A feature é legítima.

### O contexto é mesmo de t-1

Conferindo as 13.102 chaves ano × município × rede contra o indicador do **ano
corrente**: a correlação fica em 0,56–0,62 (persistência real do território) e a
coincidência exata em **0,35% dos casos** — compatível com municípios cuja taxa
não mudou, não com cópia do ano corrente.

### Achado 6.1 — duas features são contemporâneas, não anteriores

`escola_alunos_avaliados` e `mun_alunos_avaliados` contam alunos **do ano t**.
São estruturais (porte), não derivam do alvo, mas estritamente falando **não são
conhecidas antes da avaliação** — só se sabe quantos alunos foram avaliados
depois de avaliá-los.

O risco é baixo e mensurável: a correlação com o alvo é de **−0,013 e −0,047**,
praticamente nula. Mas há uma inconsistência de desenho que vale registrar: na
aferição o modelo usa a contagem verdadeira do ano; na projeção de 2026 usa a de
2025 carregada para a frente. São regimes diferentes entre ajuste e uso.

**Recomendação:** ou substituir por matrícula do Censo Escolar em t-1 (conhecida
antes), ou declarar explicitamente que são proxies de porte com defasagem
implícita. Dado o sinal quase nulo, remover também seria defensável.

### Estrutura de validação: correta

- **Divisão temporal** treina em 2024 e testa em 2025 — sem sobreposição.
- **`GroupKFold` por escola** dentro do treino, necessário porque 13,5% da
  variância está entre escolas.
- **Pré-processamento dentro do `Pipeline`**: imputador e scaler são reajustados
  em cada fold, não veem o conjunto inteiro.
- **A busca de hiperparâmetros não vê 2025** — verificado no código: toda a
  seleção usa `GroupKFold` dentro de 2024.

---

## Resumo das recomendações

| # | recomendação | situação | resultado |
|---|---|---|---|
| 1 | Ingerir `PC_ALUNO_NIVEL_0..8` | **feito na Gold** | inutilizável como feature até 2026 (2023 não publica) |
| 2 | Usar `media_portugues` de t-1 como feature | **testado e rejeitado** | piora AUC e Brier |
| 3 | Reler a interpretabilidade como grupos correlacionados | **feito** no README | corrige leitura |
| 4 | Declarar a escola como 13,5%–14,5% | **feito** no README | rigor |
| 5 | Registrar que 13,4% do erro é ruído do alvo | **feito** no README | rigor |
| 6 | Resolver o status de `*_alunos_avaliados` | **feito** — declaradas como proxies de porte com defasagem implícita (`dados.py`, README) | coerência de desenho; troca pelo Censo Escolar fica como evolução |
| 7 | Não podar features redundantes | — | poda piora, confirmado |

**O resultado mais útil desta auditoria acabou sendo negativo.** As duas
recomendações que prometiam melhorar o modelo não se sustentaram quando
implementadas e testadas: uma esbarra numa lacuna da fonte em 2023, a outra piora
o desempenho por redundância. Ambas pareciam boas medidas num proxy linear no
grão do município, e nenhuma sobreviveu ao modelo real.

Isso converge com a busca de hiperparâmetros (`OTIMIZACAO.md`), que também não
moveu o número, e reforça a tese central do projeto por um terceiro caminho
independente: **o teto é dos dados que faltam — variáveis do aluno e da escola —,
não do que se pode extrair melhor dos dados que existem.**

Nada aqui invalida número publicado.

---

## Adendo da revisão final

Uma segunda revisão, feita depois desta auditoria, encontrou um ponto que ela
não tinha olhado: **o baseline de persistência no grão do aluno usava a taxa da
rede pública** (`mun_taxa_publica_t1`), enquanto a feature mais forte do modelo é
a taxa da rede do próprio aluno (`mun_taxa_rede_t1`). Com o baseline justo, a
coluna sozinha faz AUC 0,6433 em 2025 — acima da floresta (0,6407). A conclusão
do projeto não muda (o ganho é calibração e grão municipal), mas a frase "a
floresta supera a persistência por 0,001" foi corrigida no README e em
`MODELAGEM.md`, que agora publica os dois baselines.

A mesma revisão mediu overfit e underfit numa amostra de 300 mil alunos por ano:
treino 0,698 / CV 0,653 / 2025 0,638 para a floresta; sem freios, 0,731 / 0,633.
Curva de aprendizado plana (0,635 → 0,641 de 30 mil a 1,85 milhão). E testou a
hipótese de que lat/long e as features municipais deixariam a validação cruzada
por escola decorar o município: CV agrupada por município dá 0,654 contra 0,653
por escola — refutada.
