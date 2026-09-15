# Risco municipal — quem não atinge a meta de alfabetização

Duas partes, com modelos diferentes de propósito: a **Parte 1 afere** o método contra 2025, que o modelo não viu, e a **Parte 2 projeta** 2026 com um modelo reajustado em todos os anos disponíveis. A primeira dá a margem de erro; a segunda usa essa margem.

# Parte 1 — aferição do método (2024 → 2025)

Modelo `floresta` treinado em 2024 e projetado em 2025, agregando a probabilidade de cada aluno para o grão **município × rede municipal** — o único em que o INEP publica meta por município. Nenhuma informação de 2025 entra na predição: as features são contexto de t-1 e metas publicadas antes da avaliação.

## Por que agregar muda o problema

No grão do aluno o modelo tem AUC 0,64 — modesto, porque 86% da variância do alvo está entre alunos da mesma escola e nenhuma variável disponível chega lá. Agregado ao município, o erro individual se cancela na média ponderada e o mesmo modelo chega a **AUC 0,750** para separar quem cumpre de quem não cumpre a meta. O modelo não ficou melhor: a pergunta mudou para o grão em que ele tem o que dizer. As seções seguintes medem quanto disso é mérito do modelo e quanto já estava na taxa do ano anterior.

## Prova da agregação

A taxa observada reconstruída a partir dos microdados ponderados bate com o indicador publicado em `meta_vs_resultado_municipio`: **5.494 de 5.500 municípios (99,89%)** dentro de 0,1 p.p., com diferença mediana de 0,0025 p.p. — o arredondamento da própria publicação. Sem essa prova o resto do relatório não teria valor.

As 6 maiores divergências ficam registradas em vez de escondidas:

| id_municipio | sigla_uf | alunos_avaliados | taxa_observada | taxa_publicada | diferenca |
|---|---:|---:|---:|---:|---:|
| 1100338 | RO | 423 | 0,7413 | 0,7250 | 0,0163 |
| 1100304 | RO | 1177 | 0,7713 | 0,7847 | 0,0134 |
| 1709500 | TO | 840 | 0,6357 | 0,6426 | 0,0069 |
| 2607208 | PE | 1284 | 0,5930 | 0,5966 | 0,0036 |
| 2611101 | PE | 4737 | 0,7301 | 0,7281 | 0,0020 |
| 5103403 | MT | 6069 | 0,6144 | 0,6132 | 0,0012 |

## Erro da taxa municipal prevista

| fonte | erro_medio_absoluto | raiz_erro_quadratico | vies | correlacao | dentro_de_5pp |
|---|---:|---:|---:|---:|---:|
| modelo | 0,1020 | 0,1296 | -0,0644 | 0,7239 | 0,3112 |
| persistencia_t1 | 0,1240 | 0,1615 | -0,0907 | 0,7206 | 0,2783 |

O modelo erra 10,2 p.p. em média contra 12,4 p.p. de repetir o ano anterior — **2,2 p.p. a menos, 18% de redução**. É a primeira vez no projeto que o aprendizado supera a persistência territorial com folga: no grão do aluno a diferença era de um milésimo de AUC.

Base: 4.959 municípios de 5.504 avaliados em 2025 (51 sem meta publicada, 71 sem taxa em t-1, e os demais com menos de 30 alunos avaliados — abaixo disso a própria taxa observada é ruído amostral).

## Acerto no risco de não atingir a meta

Classe positiva: **ficar abaixo da meta**, que é o caso que dispara ação. 1.383 municípios (27,9%) de fato ficaram abaixo em 2025.

| fonte | acuracia | precisao | recall | f1 | auc_roc |
|---|---:|---:|---:|---:|---:|
| modelo | 0,6523 | 0,4276 | 0,7281 | 0,5388 | 0,7496 |
| persistencia_t1 | 0,6100 | 0,4027 | 0,8243 | 0,5411 | 0,7521 |

Matriz de confusão (positivo = ficar abaixo da meta):

| fonte | verdadeiros_positivos | falsos_positivos | falsos_negativos | verdadeiros_negativos |
|---|---:|---:|---:|---:|
| modelo | 1007 | 1348 | 376 | 2228 |
| persistencia_t1 | 1140 | 1691 | 243 | 1885 |

Aqui o placar é mais sóbrio: em AUC os dois empatam (0,750 contra 0,752). A comparação de acurácia e sensibilidade no limiar fixo da meta é enganosa, porque os dois têm viés diferente: quem prevê mais baixo aciona mais alarmes e acerta mais dos que falham, ao custo de errar mais dos que cumprem. O ganho real do modelo está no **nível** da taxa prevista, não na ordenação.

## Deriva entre anos — o que nenhum modelo treinado em t-1 poderia saber

A rede municipal saltou de 58,6% em 2024 para 66,0% em 2025: **+7,4 p.p. em um ano**. O modelo projetou 61,9%, ou seja +3,3 p.p. — capturou 45% da alta, provavelmente pela meta do ano, que é a única feature que olha para a frente. O resto ele não tinha como saber.

Descontado esse deslocamento, o erro médio cai de 10,2 p.p. para 8,8 p.p.: só **14% do erro é nível — o restante é ordenação**, e esse é o limite real do modelo. O desconto é diagnóstico e não predição: o viés só é conhecido depois da avaliação.

| sigla_uf | municipios | taxa_t1 | taxa_observada | vies | erro_medio_absoluto |
|---|---:|---:|---:|---:|---:|
| BA | 404 | 0,3660 | 0,6003 | -0,1909 | 0,1926 |
| AC | 22 | 0,4350 | 0,6449 | -0,1496 | 0,1573 |
| RO | 52 | 0,6718 | 0,8133 | -0,1260 | 0,1260 |
| PI | 204 | 0,6580 | 0,8011 | -0,1187 | 0,1355 |
| AL | 101 | 0,5268 | 0,7002 | -0,1181 | 0,1263 |
| PB | 198 | 0,5916 | 0,7399 | -0,1139 | 0,1574 |
| PR | 376 | 0,7423 | 0,8456 | -0,1105 | 0,1141 |
| MT | 136 | 0,6558 | 0,7875 | -0,1070 | 0,1198 |

O caso extremo é **RS**: a rede municipal caiu -19,3 p.p. entre 2023 e 2024, contra -2,7 p.p. da segunda maior queda. O modelo lê esse ano deprimido como o patamar estrutural do estado e projeta descumprimento generalizado — 129 dos 200 municípios de maior risco são de RS, e boa parte deles cumpriu a meta. **Um sistema em produção precisa detectar o ano anômalo antes de usá-lo como contexto**, e não herdá-lo como estrutura.

## Incerteza por porte do município

O erro não é homocedástico: num município com poucas dezenas de alunos avaliados a taxa oscila por sorteio, numa capital ela é estável. O desvio usado na probabilidade é o do estrato de porte, não um número único.

| estrato | municipios | alunos_efetivos_medianos | desvio_do_erro | erro_medio_absoluto |
|---|---:|---:|---:|---:|
| 0 | 1240 | 47,0000 | 0,1288 | 0,1237 |
| 1 | 1240 | 91,6078 | 0,1188 | 0,1068 |
| 2 | 1239 | 179,8149 | 0,1069 | 0,0996 |
| 3 | 1240 | 498,2108 | 0,0895 | 0,0779 |

A probabilidade de descumprir é `Φ((meta − prevista) / σ_estrato)`. O σ vem dos resíduos de 2025: aplicado a um ano ainda não avaliado ele é a melhor estimativa disponível, mas provavelmente otimista, porque não embute a mudança de regime entre um ano e outro.

**815 municípios** saíram com probabilidade ≥ 80% de descumprir; destes, 60,4% de fato descumpriram.

Confrontando a probabilidade declarada com a frequência observada:

| faixa de risco | municipios | risco_medio_previsto | descumpriram_de_fato |
|---|---:|---:|---:|
| 0% a 20% | 917 | 0,1070 | 0,0510 |
| 20% a 40% | 1052 | 0,3000 | 0,1740 |
| 40% a 60% | 1202 | 0,4960 | 0,2570 |
| 60% a 80% | 973 | 0,6940 | 0,3620 |
| 80% a 100% | 815 | 0,9020 | 0,6040 |

**A ordenação funciona, a calibração não.** A frequência de descumprimento cresce monotonicamente de uma faixa para a seguinte — o ranking separa bem. Mas o nível está deslocado em todas elas, pela mesma razão da seção anterior: a taxa prevista é baixa demais, então a probabilidade de ficar abaixo da meta é alta demais. **Use a ordem, não o valor absoluto** — ou recalibre contra esta tabela antes de usar o número para dimensionar recurso.

## Municípios de maior risco em 2025 (topo de 40)

| município | uf | alunos | taxa t-1 | meta | prevista | gap previsto | risco | observada |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Campo Bom | RS | 677 | 45,4% | 78,1% | 46,7% | -31,4 | 100% | 63,2% |
| Canela | RS | 340 | 42,2% | 79,1% | 47,8% | -31,3 | 100% | 47,3% |
| Canguçu | RS | 318 | 51,7% | 79,8% | 50,9% | -28,9 | 100% | 59,1% |
| Lajeado | RS | 667 | 47,5% | 76,3% | 48,4% | -27,8 | 100% | 58,5% |
| Pindaí | BA | 159 | 38,3% | 73,8% | 41,5% | -32,4 | 100% | 75,7% |
| Igrejinha | RS | 335 | 49,6% | 80,0% | 53,1% | -26,9 | 100% | 76,2% |
| Sapiranga | RS | 746 | 41,1% | 75,0% | 48,8% | -26,2 | 100% | 57,8% |
| Urbano Santos | MA | 334 | 38,6% | 77,7% | 51,6% | -26,1 | 100% | 71,2% |
| Santa Maria | RS | 1.194 | 39,7% | 70,0% | 44,0% | -26,0 | 100% | 47,9% |
| Gramado | RS | 400 | 55,3% | 79,3% | 53,4% | -26,0 | 100% | 71,9% |
| Osório | RS | 287 | 44,5% | 71,7% | 45,8% | -25,8 | 100% | 46,4% |
| Caxias do Sul | RS | 2.796 | 43,2% | 72,6% | 46,8% | -25,8 | 100% | 52,9% |
| Santa Cruz do Sul | RS | 580 | 43,8% | 69,7% | 44,8% | -24,9 | 100% | 54,4% |
| Gravataí | RS | 2.078 | 41,0% | 68,9% | 44,2% | -24,7 | 100% | 46,0% |
| São Gabriel | RS | 358 | 35,6% | 67,2% | 42,9% | -24,3 | 100% | 44,2% |
| Novo Aripuanã | AM | 149 | 51,0% | 80,0% | 51,6% | -28,4 | 100% | 64,6% |
| São Luiz Gonzaga | RS | 131 | 42,3% | 80,0% | 51,7% | -28,3 | 100% | 63,2% |
| Bento Gonçalves | RS | 746 | 50,8% | 78,2% | 54,5% | -23,7 | 100% | 69,7% |
| Novo Hamburgo | RS | 1.984 | 36,0% | 68,1% | 44,8% | -23,3 | 100% | 46,8% |
| Viamão | RS | 2.107 | 38,9% | 65,7% | 42,5% | -23,2 | 100% | 41,0% |
| Araricá | RS | 138 | 43,5% | 77,0% | 49,3% | -27,7 | 100% | 61,7% |
| Esteio | RS | 712 | 47,0% | 68,7% | 45,6% | -23,2 | 100% | 53,2% |
| Matões | MA | 346 | 34,5% | 74,7% | 51,7% | -23,0 | 99% | 76,3% |
| Dois Irmãos | RS | 285 | 56,9% | 78,9% | 56,0% | -22,9 | 99% | 66,9% |
| Sapucaia do Sul | RS | 1.080 | 48,0% | 65,9% | 43,1% | -22,8 | 99% | 54,4% |
| São Lourenço do Sul | RS | 287 | 58,7% | 79,4% | 56,7% | -22,7 | 99% | 59,2% |
| Estância Velha | RS | 541 | 44,4% | 71,3% | 48,7% | -22,6 | 99% | 56,0% |
| Nova Hartz | RS | 230 | 45,3% | 74,5% | 47,5% | -27,0 | 99% | 46,9% |
| Taquara | RS | 288 | 44,6% | 69,1% | 46,5% | -22,6 | 99% | 65,2% |
| Farroupilha | RS | 639 | 56,7% | 80,0% | 57,7% | -22,3 | 99% | 75,7% |
| Marau | RS | 297 | 43,6% | 70,9% | 48,7% | -22,2 | 99% | 47,1% |
| Bagé | RS | 661 | 46,6% | 67,8% | 45,7% | -22,1 | 99% | 51,2% |
| Venâncio Aires | RS | 294 | 59,2% | 78,7% | 56,6% | -22,1 | 99% | 70,1% |
| Cachoeirinha | RS | 934 | 40,6% | 65,2% | 43,1% | -22,1 | 99% | 46,4% |
| Parnarama | MA | 392 | 54,7% | 80,0% | 58,0% | -22,0 | 99% | 83,6% |
| Candelária | RS | 184 | 53,2% | 76,8% | 50,8% | -26,0 | 99% | 67,3% |
| Santo Antônio do Içá | AM | 425 | 37,9% | 66,3% | 44,6% | -21,7 | 99% | 61,7% |
| Torres | RS | 288 | 44,0% | 68,4% | 46,7% | -21,7 | 99% | 54,9% |
| Nova Viçosa | BA | 470 | 37,2% | 64,1% | 42,5% | -21,6 | 99% | 64,7% |
| São Leopoldo | RS | 1.639 | 37,2% | 64,5% | 42,9% | -21,6 | 99% | 40,4% |

Taxas em pontos percentuais. `observada` é a conferência posterior, não entrou na predição — e mostra quantos superaram a projeção. A tabela completa fica em `data/predictions/risco_2025_aferido.parquet`.

## Figuras

![previsto contra observado](../images/08_previsto_vs_observado_municipio.png)

![risco de meta](../images/09_risco_de_meta_municipio.png)

![viés por UF](../images/10_vies_por_uf.png)

Features descartadas por serem nulas em 2024: `mun_variacao_publica_t1`, `uf_variacao_publica_t1`.

---

# Parte 2 — projeção de 2026

Tudo acima é **aferição**: mede o método contra um ano com gabarito. Esta parte é **previsão**, e não tem contra o que conferir até o INEP divulgar 2026.

O modelo aqui é outro: reajustado com **3.817.947 alunos de 2024 e 2025**, e não só com 2024. A divisão temporal existe para medir generalização, não para limitar o que o modelo final aprende — descartar metade dos dados na hora de projetar não melhoraria previsão nenhuma. O conjunto de features é o mesmo, para que a margem de erro da Parte 1 continue descrevendo este modelo.

## Como o quadro de features foi montado

Não existe roteiro de alunos de 2026 — a avaliação não ocorreu. Mas **nenhuma feature descreve a criança**: são contexto municipal e estadual de t-1 mais as metas do ano, e 2025 já fechou. Cada aluno avaliado em 2025 vira uma linha de 2026 com o mesmo território, escola e peso, e todo o contexto trocado pelo de 2026: indicadores de 2025, metas de 2026 (mart `metas_municipio`) e taxas de rendimento de 2025.

**A suposição embutida é de composição**: a coorte de 2026 se parece com a de 2025 em porte de escola e distribuição de pesos. Município que fechar escolas, crescer muito ou migrar de rede vai destoar por um motivo que não é do modelo. Há verificação automática de que o contexto foi de fato reescrito — um merge que falhasse em silêncio repetiria o ano anterior sem mudar o formato da saída.

## Resultado

**1.039 de 4.972 municípios (20,9%) são projetados abaixo da meta de 2026.** A meta mediana do ano é 69,4% e a taxa mediana projetada é 75,4%.

**Leia esse número com o viés da Parte 1 em mente.** O modelo subestimou 2025 em 6,4 p.p., e nada garante que não subestime 2026 também — treinar com 2025 junto corrige parte disso, mas ancora a previsão entre os dois regimes. Se a alta continuar, o número acima é um teto pessimista: a contagem real de municípios em risco tende a ser menor.

## Onde o risco se concentra

| sigla_uf | municipios | projetados_abaixo | proporcao | taxa_t1_mediana | meta_mediana |
|---|---:|---:|---:|---:|---:|
| RS | 299 | 280 | 0,9365 | 0,6232 | 0,7590 |
| AM | 60 | 36 | 0,6000 | 0,5652 | 0,6172 |
| SC | 256 | 124 | 0,4844 | 0,7218 | 0,7293 |
| PA | 143 | 49 | 0,3427 | 0,5948 | 0,6268 |
| RN | 140 | 42 | 0,3000 | 0,5069 | 0,5644 |
| SP | 577 | 164 | 0,2842 | 0,6599 | 0,6882 |
| AP | 16 | 4 | 0,2500 | 0,6444 | 0,5770 |
| RJ | 92 | 22 | 0,2391 | 0,6446 | 0,6774 |

**RS responde por 280 dos 1.039 municípios em risco** — 93,6% dos seus. Isso já aparecia na Parte 1, mas por um motivo diferente, e vale separar os dois.

Lá, o modelo herdava o ano deprimido de 2024 como se fosse estrutura. Aqui ele já viu a recuperação: a rede municipal de RS foi a 63,5% em 2023 → 44,2% em 2024 → 52,1% em 2025. O problema é outro — **a meta não foi repactuada depois do choque**. A meta mediana de RS para 2026 é 75,9%, acima da mediana nacional de 69,4%, porque a trajetória foi calibrada sobre o patamar de 2023 — que o estado ainda não recuperou. Cumprir exigiria **+13,6 p.p. em um ano**, contra um avanço mediano nacional de +7,8 p.p. entre 2024 e 2025.

Não é previsão de má gestão: é meta incompatível com a trajetória. É exatamente o tipo de caso que justifica repactuação, e o tipo de conclusão que um ranking sem leitura de contexto transformaria numa lista de culpados.

## Municípios de maior risco em 2026 (topo de 40)

| município | uf | alunos | taxa t-1 | meta | prevista | gap previsto | risco |
|---|---:|---:|---:|---:|---:|---:|---:|
| Osório | RS | 287 | 46,4% | 73,5% | 53,3% | -20,2 | 99% |
| Canguçu | RS | 318 | 59,1% | 79,8% | 60,2% | -19,6 | 99% |
| São Sepé | RS | 111 | 30,2% | 80,0% | 54,4% | -25,6 | 98% |
| Balneário Pinhal | RS | 174 | 31,9% | 68,7% | 45,7% | -23,0 | 98% |
| Rio Grande | RS | 1.138 | 35,7% | 66,6% | 47,3% | -19,3 | 98% |
| Gravataí | RS | 2.078 | 46,0% | 71,4% | 52,2% | -19,2 | 98% |
| Passo Fundo | RS | 1.169 | 39,3% | 68,8% | 49,9% | -18,9 | 98% |
| Tramandaí | RS | 548 | 42,5% | 66,7% | 47,8% | -18,9 | 98% |
| São Leopoldo | RS | 1.639 | 40,4% | 68,0% | 49,5% | -18,5 | 98% |
| Viamão | RS | 2.107 | 41,0% | 69,0% | 50,9% | -18,0 | 98% |
| Alvorada | RS | 1.568 | 40,5% | 62,6% | 44,7% | -17,9 | 98% |
| São Gabriel | RS | 358 | 44,2% | 70,1% | 52,4% | -17,7 | 98% |
| Triunfo | RS | 296 | 48,6% | 73,0% | 55,3% | -17,7 | 98% |
| Canoas | RS | 2.010 | 41,9% | 66,1% | 48,9% | -17,2 | 97% |
| São Lourenço do Sul | RS | 287 | 59,2% | 79,5% | 62,8% | -16,7 | 97% |
| São Jerônimo | RS | 44 | 48,9% | 80,0% | 56,2% | -23,8 | 97% |
| Santa Maria | RS | 1.194 | 47,9% | 72,2% | 56,1% | -16,1 | 96% |
| Imbé | RS | 272 | 45,5% | 72,6% | 53,4% | -19,2 | 96% |
| Sapiranga | RS | 746 | 57,8% | 76,1% | 60,0% | -16,1 | 96% |
| Cachoeirinha | RS | 934 | 46,4% | 68,6% | 52,5% | -16,0 | 96% |
| Marau | RS | 297 | 47,1% | 72,9% | 57,1% | -15,8 | 96% |
| Canela | RS | 340 | 47,3% | 79,3% | 63,6% | -15,6 | 96% |
| Bento Gonçalves | RS | 746 | 69,7% | 78,5% | 63,0% | -15,6 | 96% |
| São Gonçalo do Amarante | RN | 694 | 37,4% | 65,6% | 50,5% | -15,1 | 95% |
| Novo Hamburgo | RS | 1.984 | 46,8% | 70,7% | 55,6% | -15,1 | 95% |
| São Borja | RS | 368 | 45,5% | 72,3% | 57,2% | -15,0 | 95% |
| Charqueadas | RS | 216 | 43,8% | 71,4% | 53,8% | -17,7 | 95% |
| Porto Alegre | RS | 2.677 | 26,7% | 59,0% | 44,2% | -14,7 | 95% |
| Bagé | RS | 661 | 51,2% | 70,6% | 55,9% | -14,6 | 95% |
| Guaíba | RS | 832 | 41,2% | 64,3% | 49,8% | -14,5 | 95% |
| Cidreira | RS | 145 | 29,9% | 60,6% | 43,6% | -17,0 | 94% |
| Palmares do Sul | RS | 85 | 40,8% | 66,2% | 47,7% | -18,6 | 94% |
| Caxias do Sul | RS | 2.796 | 52,9% | 74,2% | 60,3% | -13,9 | 94% |
| Pelotas | RS | 1.367 | 29,2% | 54,4% | 40,5% | -13,9 | 94% |
| Montenegro | RS | 343 | 48,6% | 72,5% | 58,7% | -13,8 | 94% |
| São José do Norte | RS | 193 | 35,5% | 66,5% | 49,9% | -16,5 | 94% |
| Capão do Leão | RS | 265 | 32,6% | 63,7% | 47,7% | -16,0 | 93% |
| Extremoz | RN | 679 | 38,8% | 63,4% | 50,1% | -13,3 | 93% |
| Sentinela do Sul | RS | 62 | 49,7% | 76,6% | 57,7% | -18,9 | 93% |
| Cerrito | RS | 30 | 53,7% | 77,3% | 58,4% | -18,9 | 93% |

Sem coluna de observado: não existe ainda. A tabela completa fica em `data/predictions/risco_2026_projetado.parquet`.
