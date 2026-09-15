# Roteiro do vídeo executivo — até 5 minutos

**Formato:** simulação de reunião com secretários de educação e equipe do
Compromisso Nacional Criança Alfabetizada. Uma pessoa apresenta, com o painel
`reports/dashboard_executivo.html` aberto na tela. Linguagem de gestão: taxa,
meta, município, decisão. Nada de AUC, feature, pipeline ou random forest — isso
fica no README e nos relatórios.

**Regra de ouro:** 5 minutos é o limite que a avaliação da Fase 2 cobrou. O texto
abaixo tem cerca de 640 palavras, o que dá 4 min 30 s em ritmo de apresentação.
Se estiver passando, corte o bloco 5 antes de qualquer outro.

---

## Bloco 1 — O problema (0:00 – 0:40)

**Na tela:** cabeçalho do painel e os quatro números grandes.

> Bom dia. Vou falar de uma pergunta só: quais municípios não vão cumprir a meta
> de alfabetização de 2026, e o que dá para fazer sobre isso antes de a avaliação
> sair.
>
> O contexto vocês conhecem. O Compromisso Nacional diz que toda criança precisa
> estar alfabetizada ao fim do 2º ano. O INEP mede isso todo ano, e a meta do país
> para 2030 é 80%. Em 2025, a rede pública chegou a 65,6%.
>
> O problema é o calendário. O resultado de um ano sai meses depois da prova.
> Quem decide onde colocar formação, material e acompanhamento decide no escuro.
> O que construímos é uma forma de acender a luz um ciclo antes.

## Bloco 2 — Onde o país está (0:40 – 1:30)

**Na tela:** gráfico da série nacional com a trajetória de metas.

> Primeiro a boa notícia, porque ela muda a leitura de tudo o que vem depois.
> Entre 2024 e 2025 o país avançou 6,4 pontos percentuais em um ano. É o maior
> salto da série, e é mais do que a trajetória oficial exige por ano até 2030.
> Pela primeira vez o resultado passou da meta do ano.
>
> Isso não foi efeito de entrar estado novo na conta. Fixando os mesmos estados
> nos dois anos, o salto se mantém.
>
> E a geografia surpreende: o Centro-Oeste lidera, o Nordeste está acima do
> Sudeste, e quem mais avançou foi quem partia de baixo — Bahia, Acre, Piauí,
> Alagoas, Paraíba. Há convergência acontecendo.

## Bloco 3 — O que construímos, em uma frase (1:30 – 2:00)

**Na tela:** ainda o gráfico; não mostrar nada técnico.

> Pegamos os microdados oficiais do INEP, 3,8 milhões de crianças avaliadas em
> dois anos, mais as metas oficiais de cada município, o nível socioeconômico e
> as taxas de aprovação e abandono. Com isso, um modelo estima a taxa de cada
> município no ano seguinte usando só o que se sabe antes da prova.
>
> Aferimos o método de forma honesta: prevemos 2025 sem olhar para 2025. O erro
> médio por município ficou em 10 pontos percentuais — contra 12,4 se simplesmente
> repetíssemos o resultado do ano anterior. É uma lista de priorização com margem
> de erro conhecida, não uma bola de cristal.

## Bloco 4 — O radar de 2026 (2:00 – 3:00)

**Na tela:** barras por estado, depois a tabela filtrada por um estado à escolha
(sugestão: São Paulo, que tem 164 municípios em risco e é fácil de reconhecer).

> Este é o resultado para 2026. De 4.972 municípios com meta e avaliação, 1.039
> aparecem projetados abaixo da meta. Em 2025, 28% ficaram abaixo de fato; para
> 2026 a projeção aponta 21%. A queda é consistente com o ritmo do país.
>
> A lista já está pronta por município: crianças avaliadas, taxa de 2025, meta de
> 2026, projeção e a chance de ficar abaixo. Dá para filtrar por estado e ordenar
> por onde há mais crianças. Um secretário estadual abre isso hoje e sabe onde
> colocar a equipe em fevereiro, não em dezembro.
>
> E uma ressalva que vale para a lista inteira: município pequeno tem margem
> maior. Com quarenta crianças avaliadas, a taxa oscila sozinha. O painel mostra
> o porte ao lado do risco de propósito.

## Bloco 5 — Três leituras que mudam a decisão (3:00 – 4:15)

**Na tela:** os três cartões de achados.

> O ranking sozinho seria uma lista de culpados. Três leituras evitam isso.
>
> A primeira é o Rio Grande do Sul. 280 dos 299 municípios gaúchos aparecem em
> risco — 27% de todo o risco do país num estado só. Não é má gestão. A rede
> municipal caiu de 63,5% para 44,2% no ano da enchente e recuperou para 52,1%.
> Mas a meta de 2026 continua em 75,9%, acima da mediana nacional, porque foi
> calculada sobre o patamar de antes do desastre e nunca foi repactuada. Cumprir
> exigiria 13,6 pontos em um ano. A decisão aqui é federativa: repactuar.
>
> A segunda é sobre as metas em geral. A meta de 2025 pedia ao município típico
> 2,3 pontos de avanço. O avanço real foi de 7,8. Nenhum município recebeu meta
> acima do que o país mostrou ser capaz de fazer. O problema do ciclo não foi meta
> inatingível — foi meta folgada, que sinaliza menos urgência do que o sistema
> aguenta. Isso é insumo direto para a negociação do próximo ciclo.
>
> A terceira é a mais importante para quem opera. No município típico, a melhor
> e a pior escola diferem 41 pontos percentuais. A escola explica mais do
> resultado do que município e estado somados. A unidade de intervenção é a
> escola; o município é só onde o dado chega.

## Bloco 6 — O que pedimos e o que não fazemos (4:15 – 4:50)

**Na tela:** painel "Quanto confiar na projeção".

> Três pedidos. Usar a lista de 2026 para planejar o ano letivo, não para
> cobrar. Repactuar as metas onde houve choque, começando pelo Rio Grande do Sul.
> E abrir os dados por escola: é o nível que mais explica e o único que os dados
> públicos escondem.
>
> E um limite, dito com clareza: isso não decide nada sobre uma criança. O
> modelo é fraco no indivíduo e útil no território. A unidade de decisão é o
> município, e a de ação é a escola.
>
> Obrigado. O método, a validação e cada número deste painel estão documentados
> no repositório.

---

## Apoio para a gravação

**Números que precisam sair certos** (todos do painel e dos relatórios):

| número | valor | onde confere |
|---|---|---|
| rede pública 2024 → 2025 | 59,2% → 65,6% (+6,4 p.p.) | painel, série nacional; `RELATORIO_VALIDACAO.md` |
| meta 2030 | 80% | `metas_uf`, meta nacional |
| municípios projetados abaixo em 2026 | 1.039 de 4.972 (20,9%) | `RISCO_MUNICIPAL.md`, Parte 2 |
| abaixo da meta em 2025, de fato | 27,9% (1.383 de 4.959) | `RISCO_MUNICIPAL.md`, Parte 1 |
| erro médio da projeção | 10,2 p.p. contra 12,4 repetindo o ano anterior | idem |
| RS | 280 de 299; 63,5 → 44,2 → 52,1; meta 75,9% vs 69,4% nacional; +13,6 p.p. | idem |
| metas 2025 | +2,3 p.p. pedidos vs +7,8 p.p. realizados | idem |
| escolas | 41 p.p. de amplitude no município mediano | `EDA.md` |

**O que não dizer no vídeo** (está no README, para quem quiser):
AUC, Brier, random forest, gradient boosting, validação cruzada, feature, data
leakage, pipeline, parquet, SHAP. Se alguém perguntar "que modelo é?", a resposta
de uma frase: "um modelo de árvores treinado só com o que se sabe antes da prova,
aferido prevendo 2025 sem olhar para 2025".

**Se o tempo apertar:** cortar o bloco 5 para um achado só (o Rio Grande do Sul)
economiza 45 segundos. Cortar a segunda metade do bloco 2 (geografia) economiza
20.

**Ordem das telas:** cabeçalho → série nacional → barras por UF → tabela filtrada
→ três cartões → "Quanto confiar" → voltar ao cabeçalho para encerrar.
