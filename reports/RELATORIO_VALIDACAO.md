# Relatório de verificação — camada Gold (fontes oficiais INEP)

- Execução: `753a22e3-c81a-44dc-bd65-fd930de39a26`
- Data: 2026-09-15 13:03:17 UTC
- Fontes: `/Users/luizrodrigues/Documents/tech-challenge-fase3/data/raw`
- Resultado: **0 falhas**, 3 avisos, 100 verificações aprovadas


## BRONZE — ingestão das fontes oficiais

| | Verificação | Detalhe |
|---|---|---|
| OK | metas de UF recalculadas entre divulgações | nenhuma |
|  | metas de UF: 187 valores | divulgação que forneceu o valor {2023: 168, 2024: 12, 2025: 7} |  |
| AVISO | metas de município recalculadas entre divulgações | 46 chaves revisadas acima de 0,5 p.p. (maior diferença 26.47 p.p.) — prevalece a divulgação mais recente |
|  | metas de município: 38,334 valores | divulgação que forneceu o valor {2023: 37499, 2024: 674, 2025: 161} |  |
| OK | metas de Brasil recalculadas entre divulgações | nenhuma |
|  | metas de Brasil: 7 valores | divulgação que forneceu o valor {2023: 7} |  |
| OK | metas oficiais de UF carregadas | 187 metas | 27 UFs | anos [2024, 2025, 2026, 2027, 2028, 2029, 2030] |
| OK | metas oficiais de município carregadas | 38,334 metas | 5,477 municípios |
| OK | metas nacionais carregadas | 2024=59.9%, 2025=63.8%, 2026=67.5%, 2027=71.0%, 2028=74.2%, 2029=77.2%, 2030=80.0% |
| OK | metas dentro do domínio 0–1 | UF: 0.3830–0.8000 | município: 0.0794–0.8000 |
|  | 33 metas de UF são limiar ('> 80', tratadas como piso de 80%) |  |
|  | nível de alfabetização por município: 16,194 registros, anos [2023, 2024, 2025] |  |
|  | agregados oficiais no grão UF: 225 linhas | por ano {2023: 70, 2024: 75, 2025: 80} |  |
| OK | agregados de UF sem duplicidade no grão | 0 duplicadas |
| OK | redes de UF no domínio oficial | presentes: [0, 2, 3, 5] |
| OK | taxa de UF em escala 0–100 | min=30.57 max=86.21 |
| OK | níveis de proficiência de UF somam 100% | 155 linhas completas, 0 fora da faixa 99,5–100,5 | soma mediana 100.00 |
|  | agregados oficiais no grão município: 36,411 linhas | por ano {2023: 11547, 2024: 12448, 2025: 12416} |  |
| OK | agregados de município sem duplicidade no grão | 0 duplicadas |
| OK | redes de município no domínio oficial | presentes: [0, 2, 3, 5] |
| OK | taxa de município em escala 0–100 | min=2.12 max=100.00 |
| OK | níveis de proficiência de município somam 100% | 24,864 linhas completas, 0 fora da faixa 99,5–100,5 | soma mediana 100.00 |
| OK | dimensão de UF completa | 27 UFs |
| OK | dimensão de município sem id duplicado | 5,571 municípios |

## MICRODADOS DE ALUNO — leitura e agregação ponderada

| | Verificação | Detalhe |
|---|---|---|
| OK | 2023 — o corte de 743 reproduz IN_ALFABETIZADO do INEP | 1,502,809 de 1,502,809 alunos avaliados |
| OK | 2023 — id de aluno único | 1,747,439 alunos lidos |
| OK | 2023 — dependência administrativa no domínio oficial | presentes: [2, 3] |
| OK | 2023 — proficiência na escala Saeb | min=578.5 max=904.4 |
|  | 2023: 1,747,439 alunos | 1,502,809 com proficiência válida | 244,630 sem medição |  |
| OK | 2024 — o corte de 743 reproduz IN_ALFABETIZADO do INEP | 1,851,852 de 1,851,852 alunos avaliados |
| OK | 2024 — id de aluno único | 2,120,560 alunos lidos |
| OK | 2024 — dependência administrativa no domínio oficial | presentes: [2, 3, 4] |
| OK | 2024 — proficiência na escala Saeb | min=593.9 max=900.9 |
|  | 2024: 2,120,560 alunos | 1,851,852 com proficiência válida | 268,708 sem medição |  |
| OK | 2025 — o corte de 743 reproduz IN_ALFABETIZADO do INEP | 1,966,605 de 1,966,605 alunos avaliados |
| OK | 2025 — id de aluno único | 2,222,792 alunos lidos |
| OK | 2025 — dependência administrativa no domínio oficial | presentes: [2, 3] | 628 registros sem dependência |
| OK | 2025 — proficiência na escala Saeb | min=572.4 max=904.0 |
|  | 2025: 2,222,792 alunos | 1,966,605 com proficiência válida | 256,187 sem medição |  |

## ENRIQUECIMENTO — INSE e taxas de rendimento por município

| | Verificação | Detalhe |
|---|---|---|
| OK | INSE municipal carregado | 28,127 pares município-rede | 5,558 municípios | média 4.85 |
| OK | INSE dentro da escala esperada | min=3.35 max=6.46 |
|  | taxas de rendimento de 2023: 25,512 pares município-rede (contexto de 2024) |  |
|  | taxas de rendimento de 2024: 25,524 pares município-rede (contexto de 2025) |  |
|  | taxas de rendimento de 2025: 25,535 pares município-rede (contexto de 2026) |  |
| OK | taxas de rendimento carregadas | 76,571 linhas | anos de consumo [2024, 2025, 2026] |
| OK | taxas de rendimento em escala 0–100 por cento | aprovação, reprovação e abandono |

## SILVER — modelo canônico e integração das metas oficiais

| | Verificação | Detalhe |
|---|---|---|
| OK | toda medição tem rótulo de rede | 0 sem rótulo |
| OK | taxa normalizada para fração 0–1 | min=0.0212 max=1.0000 |
| OK | todo fato municipal existe na dimensão do IBGE | 0 sem correspondência |
| OK | toda UF existe na dimensão | 0 sem correspondência |
| OK | UF do fato compatível com a UF do município na dimensão | 0 incompatíveis |
|  | situação da meta em cada medição: {'ano_anterior_a_meta': 11617, 'escopo_de_rede_sem_meta_oficial': 14019, 'oficial': 10930, 'territorio_sem_meta_publicada': 70} |  |
| OK | nenhuma meta de UF perdida no join | 51 aplicáveis, 51 aplicadas |
| OK | nenhuma meta de município perdida no join | 10,879 aplicáveis, 10,879 aplicadas |
| OK | meta em fração 0–1 | min=0.0794 max=0.8000 |
| OK | record_id único — nenhuma medição perdida | 36,636 medições, 36,636 chaves distintas |
|  | silver: 36,636 medições | 10,930 com meta oficial |  |

## QUALITY GATE — validação bloqueante antes da Gold

| | Verificação | Detalhe |
|---|---|---|
| OK | Silver não vazia | 36,636 medições |
| OK | aprovados maior que zero | 36,636 aprovados |
| OK | record_id único nos aprovados |  |
| OK | cobertura mínima de 80% | 100.0% (36,636/36,636) |
| OK | toda meta aprovada declara origem e escopo |  |

## GOLD — construção dos marts (um grão por mart)

| | Verificação | Detalhe |
|---|---|---|
|  | gold.indicador_municipio: 36,411 linhas, 25 colunas |  |
|  | gold.resumo_uf: 225 linhas, 23 colunas |  |
|  | gold.meta_vs_resultado_uf: 76 linhas, 18 colunas |  |
|  | gold.meta_vs_resultado_municipio: 16,396 linhas, 24 colunas |  |
|  | gold.evolucao_uf: 225 linhas, 14 colunas |  |
|  | gold.evolucao_municipio: 36,411 linhas, 16 colunas |  |
|  | gold.distribuicao_proficiencia: 4,837 linhas, 11 colunas |  |
| OK | metas de UF — grão único em ano + sigla_uf | 187 linhas | anos [2024, 2025, 2026, 2027, 2028, 2029, 2030] | 27 territórios |
| OK | metas de município — grão único em ano + id_municipio | 38,334 linhas | anos [2024, 2025, 2026, 2027, 2028, 2029, 2030] | 5,477 territórios |
| OK | metas de município casam com a dimensão territorial do IBGE | 0 sem correspondência |

## ALUNO_FEATURES — base de treino no grão do aluno

| | Verificação | Detalhe |
|---|---|---|
|  | 2024: 1,851,852 alunos avaliados | 42,328 escolas | 5,517 municípios |  |
|  | 2025: 1,966,605 alunos avaliados | 43,538 escolas | 5,556 municípios | 510 descartados sem escola/município na fonte |  |
| OK | aluno_features — um registro por aluno e ano | 3,817,947 linhas, 3,817,947 pares únicos |
| OK | aluno_features — alvo binário sem nulos | distribuição {1: 2409804, 0: 1408143} |
| OK | aluno_features — cobre apenas os anos com contexto anterior | anos [2024, 2025] |
| OK | aluno_features — a proficiência não está na base | o alvo contínuo ficaria como feature e tornaria o problema trivial |
| OK | aluno_features — o contexto municipal é o do ano anterior | 2,000 municípios conferidos contra o indicador de t-1 |
| OK | aluno_features — o contexto não é o do ano corrente (sem vazamento) | 8 de 2,000 municípios coincidem com o ano corrente (coincidência exata é possível quando a taxa não mudou) |
|  | aluno_features — features com valor faltante: {'mun_taxa_rede_t1': '1.3%', 'mun_media_lp_t1': '1.3%', 'mun_taxa_publica_t1': '5.6%', 'mun_nivel_t1': '8.1%', 'mun_variacao_publica_t1': '54.3%', 'mun_meta_ano': '2.1%', 'uf_taxa_publica_t1': '1.7%', 'uf_variacao_publica_t1': '49.6%', 'uf_meta_ano': '0.8%', 'mun_inse_media': '0.1%', 'mun_inse_pct_vulneravel': '0.3%', 'mun_inse_alunos': '0.1%', 'mun_aprovacao_1ano_t1': '0.3%', 'mun_aprovacao_2ano_t1': '0.0%', 'mun_reprovacao_2ano_t1': '0.0%', 'mun_abandono_iniciais_t1': '0.0%'} (a imputação é responsabilidade do pipeline de ML) |  |
|  | aluno_features — taxa de alfabetizados na base: 63.1% bruta | 62.5% ponderada |  |
|  | aluno_features — 3,817,947 linhas x 31 colunas | 85,866 grupos de escola para GroupKFold |  |

## VERIFICAÇÃO — grão, domínios e equivalência com o INEP

| | Verificação | Detalhe |
|---|---|---|
| OK | gold.indicador_municipio — grão único em ano + id_municipio + rede | 0 duplicadas |
| OK | gold.resumo_uf — grão único em ano + sigla_uf + rede | 0 duplicadas |
| OK | gold.meta_vs_resultado_uf — grão único em ano + sigla_uf | 0 duplicadas |
| OK | gold.meta_vs_resultado_municipio — grão único em ano + id_municipio | 0 duplicadas |
| OK | gold.metas_uf — grão único em ano + sigla_uf | 0 duplicadas |
| OK | gold.metas_municipio — grão único em ano + id_municipio | 0 duplicadas |
| OK | gold.evolucao_uf — grão único em ano + sigla_uf + rede | 0 duplicadas |
| OK | gold.evolucao_municipio — grão único em ano + id_municipio + rede | 0 duplicadas |
| OK | gold.distribuicao_proficiencia — grão único em ano + sigla_uf + rede + faixa_pontos + faixa_label | 0 duplicadas |
| OK | metas_uf concorda com meta_vs_resultado_uf nos anos em comum | 51 chaves conferidas, 0 divergentes |
| OK | metas_municipio concorda com meta_vs_resultado_municipio nos anos em comum | 10,879 chaves conferidas, 0 divergentes |
| OK | metas_uf cobre anos ainda não avaliados | anos [2024, 2025, 2026, 2027, 2028, 2029, 2030] — a projeção precisa da meta do ano seguinte ao último avaliado |
| OK | metas_municipio cobre anos ainda não avaliados | anos [2024, 2025, 2026, 2027, 2028, 2029, 2030] — a projeção precisa da meta do ano seguinte ao último avaliado |
| OK | meta_vs_resultado_uf não contém grão municipal |  |
| OK | cada mart de meta usa um único escopo de rede | UF: rede 5 | município: rede 3 |
| OK | indicador_municipio cobre toda medição aprovada no grão municipio | 36,411 chaves na Silver, 36,411 na Gold |
| OK | resumo_uf cobre toda medição aprovada no grão uf | 225 chaves na Silver, 225 na Gold |
| OK | gold.indicador_municipio.taxa_alfabetizacao em fração 0–1 | min=0.0212 max=1.0000 |
| OK | gold.resumo_uf.taxa_alfabetizacao em fração 0–1 | min=0.3057 max=0.8621 |
| OK | gold.evolucao_uf.taxa_alfabetizacao em fração 0–1 | min=0.3057 max=0.8621 |
| OK | gold.evolucao_municipio.taxa_alfabetizacao em fração 0–1 | min=0.0212 max=1.0000 |
| OK | gold.meta_vs_resultado_uf — gap coerente com taxa menos meta | 51 linhas com meta |
| OK | gold.meta_vs_resultado_uf — atingiu_meta coerente |  |
| OK | gold.meta_vs_resultado_uf — toda meta declara origem e escopo | origens: ['inep_compromisso_nacional'] |
| OK | gold.meta_vs_resultado_uf — sem meta implica atingiu_meta nulo | 25 linhas sem meta |
| OK | gold.meta_vs_resultado_municipio — gap coerente com taxa menos meta | 10,879 linhas com meta |
| OK | gold.meta_vs_resultado_municipio — atingiu_meta coerente |  |
| OK | gold.meta_vs_resultado_municipio — toda meta declara origem e escopo | origens: ['inep_compromisso_nacional'] |
| OK | gold.meta_vs_resultado_municipio — sem meta implica atingiu_meta nulo | 5,517 linhas sem meta |
| OK | gold.evolucao_uf — variação confere com a diferença entre anos | 144 linhas com ano anterior |
| OK | gold.evolucao_municipio — variação confere com a diferença entre anos | 23,383 linhas com ano anterior |
| OK | distribuicao_proficiencia — alfabetizados só acima do corte |  |
| OK | o indicador recalculado dos microdados reproduz o agregado do INEP | 222 pares | mediana 0.0033 p.p. | 95.0% dentro de 0,05 p.p. |
| AVISO | nenhum recorte diverge do agregado publicado acima de 0,1 p.p. | 2023 MS rede 2: 0.17 p.p. em 671 alunos; 2023 MS rede 3: 0.32 p.p. em 36,442 alunos; 2023 MS rede 5: 0.31 p.p. em 37,113 alunos; 2023 MT rede 2: 1.49 p.p. em 2,818 alunos; 2023 SE rede 2: 0.25 p.p. em 2,866 alunos; 2023 SE rede 3: 0.26 p.p. em 15,768 alunos; 2023 SE rede 5: 0.26 p.p. em 18,634 alunos; 2024 PB rede 2: 0.70 p.p. em 1,180 alunos |
| OK | indicador nacional de 2024 reproduz o publicado pelo INEP | recalculado 59.1996% x publicado 59.1973% |
| AVISO | indicador nacional de 2023 confere com o publicado | recalculado 57.46% x publicado 55.90% — a avaliação de 2023 cobriu 24 UFs e o nacional publicado abrange mais que a soma dos estados divulgados; use o valor por UF, que confere |
|  | indicador nacional da rede pública em 2023: 57.5% (ponderado por 1,743,618 alunos avaliados) |  |
|  | indicador nacional da rede pública em 2024: 59.2% (ponderado por 2,109,150 alunos avaliados) |  |
|  | indicador nacional da rede pública em 2025: 65.6% (ponderado por 2,222,164 alunos avaliados) |  |
| OK | meta_vs_resultado_uf reproduz o resultado publicado na planilha do INEP | 25 UFs conferidas | diferença máxima 0.0000 p.p. |

## DIAGNÓSTICO — leitura destes dados na Fase 3

| | Verificação | Detalhe |
|---|---|---|
|  | anos cobertos: [2023, 2024, 2025] |  |
|  | escopos de rede disponíveis: {0: 'total', 2: 'estadual', 3: 'municipal', 5: 'publica'} |  |
|  | UFs com medição por ano: {2023: 24, 2024: 25, 2025: 27} |  |
|  | 2023 (rede pública): 24 UFs medidas | média simples 54.3% | sem meta nacional (ano-base) | nenhuma UF tinha meta publicada | melhor CE 84.5%, pior SE 31.3% |  |
|  | 2024 (rede pública): 25 UFs medidas | média simples 56.6% | meta nacional 60% | 11 de 24 UFs com meta a atingiram | melhor CE 85.3%, pior BA 36.0% |  |
|  | 2025 (rede pública): 27 UFs medidas | média simples 65.6% | meta nacional 64% | 19 de 27 UFs com meta a atingiram | melhor CE 83.9%, pior RN 48.5% |  |
|  | municípios com meta oficial: 5,465 | metas distintas em SP num ano: 519 |  |
|  | trajetória da rede pública (média simples das UFs): 54.3% em 2023 -> 65.6% em 2025 | ritmo +5.7 p.p./ano | a meta oficial de 2030 é 80%, exigindo +2.9 p.p./ano |  |

## ESCRITA — materialização dos Parquet

| | Verificação | Detalhe |
|---|---|---|
| OK | indicador_municipio.parquet relido íntegro | 36,411 linhas, 1102.0 KB |
| OK | resumo_uf.parquet relido íntegro | 225 linhas, 27.8 KB |
| OK | meta_vs_resultado_uf.parquet relido íntegro | 76 linhas, 7.3 KB |
| OK | meta_vs_resultado_municipio.parquet relido íntegro | 16,396 linhas, 430.8 KB |
| OK | metas_uf.parquet relido íntegro | 187 linhas, 5.1 KB |
| OK | metas_municipio.parquet relido íntegro | 38,334 linhas, 601.7 KB |
| OK | evolucao_uf.parquet relido íntegro | 225 linhas, 10.7 KB |
| OK | evolucao_municipio.parquet relido íntegro | 36,411 linhas, 513.1 KB |
| OK | distribuicao_proficiencia.parquet relido íntegro | 4,837 linhas, 80.3 KB |
| OK | aluno_features.parquet relido íntegro | 3,817,947 linhas, 21470.4 KB |
