# Fontes oficiais do INEP

Os arquivos desta pasta não são versionados: são públicos e reprodutíveis.

## Avaliação da alfabetização

Baixe os nove da página de
[Resultados da Avaliação da Alfabetização](https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/avaliacao-da-alfabetizacao/resultados)
(abas 2023, 2024 e 2025) e coloque-os aqui com estes nomes:

| Arquivo | Aba | Conteúdo |
|---|---|---|
| `microdados_avaliacao_da_alfabetizacao_2023.zip` | 2023 | TS_ALUNO, TS_ESTADO, TS_MUNICIPIO |
| `microdados_avaliacao_da_alfabetizacao_2024.zip` | 2024 | idem |
| `microdados_AEEB_2025.zip` | 2025 | idem |
| `resultados_e_metas_ufs.xlsx` | 2023 | metas oficiais por UF — **maior precisão** |
| `resultados_e_metas_ufs_2024_2.xlsx` | 2024 | metas por UF (duas casas) |
| `resultados_e_metas_ufs_2025_v1.xlsx` | 2025 | metas por UF (inteiros) |
| `resultados_e_metas_municipios.xlsx` | 2023 | metas oficiais por município — **maior precisão** |
| `resultados_e_metas_municipios_2024.xlsx` | 2024 | metas por município |
| `resultados_e_metas_municipios_2025_3.xlsx` | 2025 | metas por município |

As três divulgações publicam os mesmos valores com precisões diferentes: a de
2023 traz o float completo, a de 2024 arredonda para duas casas e a de 2025 para
inteiro. O pipeline usa a mais precisa disponível para cada chave e registra a
origem na coluna `meta_publicacao`. A de 2025 tem a maior cobertura de
municípios e entra como complemento.

## Enriquecimento municipal

Quatro arquivos adicionais, também do INEP, usados por `aluno_features`:

| Arquivo | Origem | Conteúdo |
|---|---|---|
| `INSE_2023_municipios.xlsx` | [Indicadores educacionais — INSE](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/nivel-socioeconomico) | nível socioeconômico por município e rede |
| `tx_rend_municipios_2023.zip` | [Indicadores educacionais — taxas de rendimento](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-rendimento-escolar) | aprovação, reprovação e abandono |
| `tx_rend_municipios_2024.zip` | idem | idem |
| `tx_rend_municipios_2025.zip` | idem | idem |

O INSE sai a cada dois anos junto com o SAEB; 2023 é a safra mais recente e entra
como característica estrutural, sem defasagem. As taxas de rendimento entram
defasadas em um ano, como todo indicador de resultado: as de 2023 alimentam 2024,
as de 2024 alimentam 2025 e as de 2025 compõem o contexto da **projeção de
2026** — estas últimas não encontram aluno em `aluno_features`, porque a
avaliação de 2026 ainda não ocorreu, e existem só para `prever_municipios.py`.

## Dimensões territoriais

As do IBGE (`uf.csv`, `municipio.csv`) ficam em `data/external/` e são
versionadas — são pequenas e estáveis.
