# Contrato de dados — camada Gold

O que cada tabela de `data/gold` garante a quem a consome. Se uma garantia daqui
deixar de valer, o pipeline **não grava nada** e sai com código 1 — as
verificações estão em `src/evaluation/validacao.py` e no relatório de execução
`reports/RELATORIO_VALIDACAO.md`.

Este documento existe porque a Gold é consumida por código que não a produziu: o
pipeline de modelagem, os notebooks e quem vier depois. Sem contrato, cada
consumidor redescobre o grão por tentativa, e um `SUM` sobre o mart errado passa
despercebido.

---

## Convenções que valem para todas as tabelas

**Um grão por tabela.** Nenhum mart mistura níveis territoriais. Isso é resposta
direta a um problema da Fase 2, em que `meta_vs_resultado` tinha UF e município
na mesma tabela e uma média sem filtro contava o mesmo dado duas vezes.

**Taxas em fração, não em percentual.** `taxa_alfabetizacao`, `meta_taxa`,
`pc_nivel_*` e `gap_meta` vão de 0 a 1. A fonte publica em percentual; a
normalização acontece na Silver e é verificada. **Exceção:** as taxas de
rendimento em `aluno_features` (`mun_aprovacao_*`, `mun_reprovacao_*`,
`mun_abandono_*`) permanecem em 0–100, como o INEP publica.

**Proficiência em pontos da escala INEP**, tipicamente de 570 a 905.

**Tipos legíveis sem conversão** por Spark, DuckDB, Polars e pandas: texto
`string`, inteiros `int64`, decimais `double`, datas `timestamp[us, UTC]`. O
pandas 3 serializa texto como `large_string`; a escrita converte para `string`
porque nem todo consumidor lê o tipo largo.

**`fonte_dados`** registra a procedência em toda linha. Hoje só existe o valor
`oficial_inep` — nenhum dado do projeto é simulado ou derivado de projeção.

**`updated_at`** é o instante de processamento, não a data do fato.

### Domínio de rede — leia antes de filtrar

`rede` segue o dicionário oficial da AEEB. **O código 5 é pública, não privada** —
a Fase 2 trocava os dois, e o erro atravessou painel, KPIs e vídeo sem alarme.

| código | `rede_label` | composição |
|---:|---|---|
| 0 | `total` | federal + estadual + municipal + privada |
| 1 | `federal` | federal |
| 2 | `estadual` | estadual |
| 3 | `municipal` | municipal |
| 4 | `privada` | privada |
| 5 | `publica` | estadual + municipal |
| 6 | `publica_com_federal` | federal + estadual + municipal |

Dois cuidados que custaram erro no passado:

- **Média simples das redes 2 e 3 não é a rede pública.** Use a rede 5. A média
  simples errava até 12,40 p.p.
- **O indicador nacional é ponderado**, não é a média das UFs. Em 2024 a média
  simples dá 56,6% e o indicador nacional 59,2%.

### Escopo das metas

O INEP publica meta de **rede pública no grão UF** e de **rede municipal no grão
município** — e só nesses recortes. Comparar a meta de rede pública com o
resultado da rede estadual isolada não significa nada. Os marts respeitam isso:
`meta_escopo` diz qual vale em cada linha.

`meta_limiar = true` significa que a meta é **piso**, não alvo pontual: a de 2030
é "> 80%". `meta_publicacao` diz de qual divulgação (2023, 2024 ou 2025) veio o
valor — as três publicam os mesmos números com precisões diferentes, e o
pipeline usa a mais precisa disponível para cada chave.

---

## Os dez marts

### 1. `indicador_municipio` — 36.411 linhas

**Grão:** `ano + id_municipio + rede`. O indicador oficial por município.

| coluna | tipo | significado |
|---|---|---|
| `ano` | Int64 | ano da avaliação (2023–2025) |
| `sigla_uf`, `nome_uf`, `regiao` | str | UF do município |
| `id_municipio` | str | código IBGE de 7 dígitos, com zero à esquerda |
| `nome_municipio`, `capital`, `latitude`, `longitude` | str/Int64/float | dimensão IBGE; `capital` é 0/1 |
| `nivel_alfabetizacao` | Int64 | nível 1–5 do Compromisso Nacional (**não confundir** com `pc_nivel_*`) |
| `rede`, `rede_label` | Int64/string | escopo de rede (tabela acima) |
| `fonte_dados` | str | `oficial_inep` |
| `taxa_alfabetizacao` | float64 | fração 0–1 de alunos acima de 743 pontos |
| `media_portugues` | float64 | proficiência média em Língua Portuguesa |
| `pc_nivel_0` … `pc_nivel_8` | float64 | fração de alunos em cada um dos nove níveis de proficiência; somam 1,0 |
| `updated_at` | timestamp | instante do processamento |

**Garantias:** grão único; `taxa_alfabetizacao` em 0–1; redes no domínio oficial;
`pc_nivel_*` somam 1,00 (tolerância de 0,5 p.p.); cobre toda medição aprovada no
Quality Gate.

**Cuidado:** `pc_nivel_*` só existe a partir de 2024 — a divulgação de 2023 não
publica essas colunas.

### 2. `resumo_uf` — 225 linhas

**Grão:** `ano + sigla_uf + rede`. As mesmas medidas no grão estadual, mais:

| coluna | tipo | significado |
|---|---|---|
| `alunos_taxa_ponderada` | float64 | soma dos pesos amostrais usada na taxa |
| `alunos_proficiencia_media` | float64 | soma dos pesos usada na média |
| `alunos_amostra` | float64 | alunos efetivamente avaliados |
| `municipios_cobertos` | Int64 | municípios da UF com medição — **alcance do pipeline, não entra no cálculo da taxa** |

**Cobertura cresce no tempo:** 24 UFs em 2023, 25 em 2024, 27 em 2025. Toda
comparação entre anos precisa fixar o conjunto de UFs.

### 3 e 4. `meta_vs_resultado_uf` (76) e `meta_vs_resultado_municipio` (16.396)

**Grão:** `ano + território`. **Um escopo de rede por mart** — rede 5 no de UF,
rede 3 no de município. São a **interseção** entre meta e resultado: só existem
para anos já avaliados.

| coluna | tipo | significado |
|---|---|---|
| `meta_taxa` | float64 | meta oficial do ano, fração 0–1 |
| `meta_brasil` | Float64 | meta nacional do ano |
| `meta_limiar` | boolean | `true` = piso mínimo, não alvo pontual |
| `meta_origem` | string | `inep_compromisso_nacional` |
| `meta_escopo` | string | `rede_publica` ou `rede_municipal` |
| `meta_publicacao` | Int64 | divulgação que forneceu o valor |
| `gap_meta` | float64 | `taxa_alfabetizacao − meta_taxa` |
| `atingiu_meta`, `atingiu_meta_brasil` | boolean | nulos quando não há meta |

**Cuidado:** nem toda UF tem meta. Ceará, Acre e Distrito Federal já superam o
patamar e só têm o piso de "> 80" em 2030 — um ranking filtrado por "tem meta"
exclui justamente as melhores. **2023 não tem meta**: é o ano-base.

### 5 e 6. `metas_uf` (187) e `metas_municipio` (38.334)

**Grão:** `ano + território`, **2024 a 2030**, independente de haver resultado.

Existem porque os marts `meta_vs_resultado_*` param no último ano avaliado, e
projetar 2026 exige a meta de 2026. Colunas de meta iguais às acima, mais a
dimensão territorial, sem as colunas de resultado.

**Garantia:** concordam com `meta_vs_resultado_*` nos anos em comum — verificação
bloqueante. Divergir significaria publicar dois números oficiais incompatíveis.

### 7 e 8. `evolucao_uf` (225) e `evolucao_municipio` (36.411)

**Grão:** `ano + território + rede`. Variação ano a ano.

| coluna | tipo | significado |
|---|---|---|
| `taxa_ano_anterior`, `ano_anterior` | float64/Int64 | o ponto de comparação |
| `variacao_absoluta` | float64 | diferença em fração |
| `variacao_relativa` | float64 | variação proporcional; nula quando a base é zero |
| `tendencia` | string | `alta`, `queda` ou `estavel` |

**Cuidado:** o ano anterior é o **anterior na série medida**, não `ano − 1`. Um
território sem medição em 2024 compara 2025 com 2023.

### 9. `distribuicao_proficiencia` — 4.837 linhas

**Grão:** `ano + sigla_uf + rede + faixa_pontos + faixa_label`. Histograma
reconstruído dos microdados ponderados.

`faixa_label` **não é derivável** de `faixa_pontos`: o corte de 743 cai dentro do
bloco 725–749, que por isso aparece dividido. O grão precisa das duas colunas.

| coluna | tipo | significado |
|---|---|---|
| `alunos_avaliados` | Int64 | contagem bruta |
| `alunos_alfabetizados` | Int64 | contagem bruta acima do corte |
| `alunos_estimados` | float64 | soma dos pesos amostrais |
| `proficiencia_media` | float64 | média ponderada da faixa |

**Garantia:** nenhuma faixa abaixo de 743 tem alfabetizados.

### 10. `aluno_features` — 3.817.947 linhas

**Grão:** `ano + id_aluno`. A base de treino. Uma linha por aluno avaliado em
2024 e 2025. **2023 não entra como ano de treino** — é o primeiro da série e não
tem contexto anterior —, mas alimenta as features defasadas de 2024.

#### Identificação e alvo

| coluna | tipo | significado |
|---|---|---|
| `id_aluno` | Int64 | identificador do aluno no ano |
| `id_escola_ano` | str | par `ano-código`, ver abaixo |
| `id_municipio`, `sigla_uf`, `regiao`, `capital`, `latitude`, `longitude` | — | território |
| `rede`, `rede_label` | Int64/string | dependência administrativa do aluno |
| `peso_amostral` | float32 | `VL_PESO_ALUNO_LP`; **toda métrica é ponderada por ele** |
| `alfabetizado` | int8 | **o alvo**: 1 se proficiência ≥ 743 |

**`id_escola_ano` só vale dentro do ano.** O INEP publica o código da escola
mascarado, com códigos fictícios **resorteados a cada ano**. O mesmo número é
outra escola em outro ano, e ele não joina com Censo Escolar nem com o INSE por
escola. Serve para duas coisas: porte da escola e agrupamento no `GroupKFold`.

#### Features — e a regra que as governa

**Todo indicador de resultado vem de t-1.** A taxa do município em 2025 é
calculada a partir dos próprios alunos que o modelo tenta prever; usá-la seria
vazamento. As metas são a exceção legítima: foram publicadas antes da avaliação.

| coluna | origem | defasagem |
|---|---|---|
| `escola_alunos_avaliados`, `mun_alunos_avaliados` | porte, do próprio ano | **contemporânea** (ver ressalva) |
| `mun_taxa_rede_t1` | taxa do município na rede do aluno | t-1 |
| `mun_media_lp_t1` | proficiência média do município na rede do aluno | t-1 |
| `mun_taxa_publica_t1`, `mun_nivel_t1` | taxa e nível na rede pública | t-1 |
| `mun_variacao_publica_t1` | variação da taxa municipal | t-1 |
| `uf_taxa_publica_t1`, `uf_variacao_publica_t1` | idem no grão UF | t-1 |
| `mun_meta_ano`, `uf_meta_ano` | meta oficial | **ano corrente** |
| `mun_inse_media`, `mun_inse_pct_vulneravel`, `mun_inse_alunos` | INSE 2023 | estrutural |
| `mun_aprovacao_1ano_t1`, `mun_aprovacao_2ano_t1`, `mun_reprovacao_2ano_t1`, `mun_abandono_iniciais_t1` | taxas de rendimento, **escala 0–100** | t-1 |

**A proficiência não está na base.** Ela é o alvo antes do corte — incluí-la
tornaria o problema trivial. Há verificação automática de que nenhuma coluna com
"proficiencia" no nome existe aqui.

#### Ressalvas conhecidas para quem for modelar

1. **`mun_variacao_publica_t1` e `uf_variacao_publica_t1` são 100% nulas em 2024**
   — variação em t-1 exige t-2. `src/modeling/dados.py` as descarta
   automaticamente e registra o descarte.
2. **`mun_media_lp_t1` está na tabela e fora do conjunto de features.** Ela
   correlaciona 0,930 com `mun_taxa_rede_t1` e carrega menos sinal sobre o alvo;
   acrescentá-la piorou AUC e Brier em base completa. Ver `reports/AUDITORIA.md`.
3. **`escola_alunos_avaliados` e `mun_alunos_avaliados` são contemporâneas.** São
   estruturais e não derivam do alvo, mas estritamente não são conhecidas antes
   da avaliação. Correlação com o alvo: −0,013 e −0,047.
4. **Há redundância alta entre features** — oito pares com |r| > 0,80. Podar
   piora o desempenho, mas a importância por permutação subestima features
   correlacionadas: leia o ranking como de grupos, não de variáveis isoladas.

---

## O que a Gold garante sobre a fonte

- **A regra de negócio é exata.** O corte de 743 pontos reproduz a flag oficial
  `IN_ALFABETIZADO` com **zero divergências em 3.818.457 alunos**.
- **O pipeline reproduz o indicador oficial.** Recalculado dos microdados
  ponderados, o indicador nacional de 2024 da rede pública dá **59,1996%** contra
  **59,1973%** publicados. Nos 222 recortes por UF e rede, a mediana da diferença
  é 0,0033 p.p.
- **A reconstrução municipal bate com o publicado** em 99,89% dos 5.500
  municípios, dentro de 0,1 p.p.

## Limites conhecidos, registrados em vez de escondidos

- O indicador nacional de **2023 não é reproduzível** a partir do microdado
  estadual: a avaliação cobriu 24 UFs e o número publicado tem abrangência maior.
  Os valores por UF conferem.
- Um recorte (**PB 2024, rede estadual**, 1.180 alunos) diverge 0,70 p.p. do
  agregado publicado, provavelmente por critério de publicação não codificado nos
  microdados.
- **Seis municípios** divergem acima de 0,1 p.p. na reconstrução de 2025, o maior
  em 1,63 p.p. Listados em `reports/RISCO_MUNICIPAL.md`.
- **Cinco células município × rede** existem no microdado e não na tabela
  publicada pelo INEP. Não é supressão por tamanho — há células publicadas com 4
  alunos. A Gold é, nesse ponto, mais abrangente que a fonte.

---

Versão do esquema: `SCHEMA_VERSION = "2.0"` · regra de alfabetização:
`ALFABETIZACAO_RULE_VERSION = "1.0"` (corte de 743 pontos). Ambas em
`src/config.py`; o manifesto de cada execução, com linhas, colunas e SHA-256 de
cada Parquet, fica em `reports/manifest.json`.
