# Fontes oficiais do INEP

Os arquivos desta pasta não são versionados: somam ~82 MB, são públicos e
reprodutíveis. Baixe os seis da página de
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

As dimensões territoriais do IBGE (`uf.csv`, `municipio.csv`) ficam em
`data/external/` e são versionadas — são pequenas e estáveis.
