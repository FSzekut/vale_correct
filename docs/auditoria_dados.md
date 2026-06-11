# Auditoria dos dados e resultados

## Parecer executivo

Não há evidência de que os arquivos brutos tenham sido fabricados: os 37.164.054 IDs de
telemetria são únicos, os campos essenciais não têm nulos e os totais publicados nos notebooks
foram reproduzidos. Entretanto, várias interpretações e decisões metodológicas não são
sustentadas pelos dados.

### Achados críticos

1. **O target não representa uma falha ou parada confirmada.** O dicionário define
   `Is_Dont_Go` como uma flag indicando que o alarme consta na lista Don't Go. Ele não afirma
   que a condição completa da regra foi satisfeita nem que o equipamento parou. Das 19.962
   linhas positivas, 9.676 (48,5%) têm criticidade `Não Crítico`, e 15.972 (80,0%) ocorreram
   enquanto o apontamento do equipamento estava em `Operando`.

2. **As 19.962 linhas positivas não são 19.962 falhas independentes.** Há 5.130 repetições
   em até um minuto e 16.353 repetições em até uma hora. Agrupando alertas consecutivos,
   existem aproximadamente 3.571 episódios com separação de uma hora ou 1.460 episódios
   com separação de oito horas. O target atual prevê uma janela contendo linhas marcadas,
   não necessariamente uma nova falha.

3. **O “downtime real” não mede downtime causado pelo alerta.** O cálculo procura o próximo
   início de um apontamento `Operando`, mesmo quando o equipamento já estava operando no
   instante do alerta. Isso ocorre em 80% das linhas positivas. A mediana de 0,45 h e a média
   de 2,96 h são “tempo até o próximo início de Operando”, não tempo de parada causado por
   Don't Go. Esses valores não devem alimentar ROI.

4. **As correções de TAG estão incorretas.** `CA5926`, `CA65926`, `CA5927` e `CA65927`
   coexistem durante todo o semestre, possuem históricos próprios nos apontamentos e até
   frotas diferentes (`CA5926` é `793-D 5S`; `CA65926` é `793-D 4S`). Fundi-las reduz
   artificialmente 35 equipamentos para 33 e reduz as janelas positivas de junho de 292
   para 281. Essa limpeza mistura equipamentos reais e deve ser removida.

5. **As regras de negócio completas não foram aplicadas.** Os notebooks utilizam diretamente
   o `Is_Dont_Go` entregue. O catálogo possui condições de quantidade, tempo, situação e nível,
   mas a modelagem trata cada linha positiva como evento crítico. Todos os positivos pertencem
   a nomes de eventos presentes no catálogo, porém isso valida somente o nome do alarme, não
   o atendimento da regra.

### Achados altos

1. **O expurgo dos três dias é parcialmente justificável, mas não auditável como regra de
   limpeza.** Os volumes extremos e ausência de positivos foram confirmados, porém o critério
   é manual e não foi aplicado sistematicamente. Existem 270 combinações equipamento/dia com
   mais de 50 mil registros e zero Don't Go, totalizando 18,1 milhões de linhas. Isso não
   significa que todas devam ser removidas; significa que remover apenas três exige uma regra
   operacional ou estatística documentada.

2. **Há 265.573 duplicatas lógicas completas excedentes**, embora os IDs sejam únicos. Elas
   não foram tratadas nem justificadas. É necessário determinar se representam retransmissão,
   repetição legítima do sensor ou duplicação de ingestão.

3. **A ausência total de dados em 31/05 foi confirmada**, mas chamá-la de “apagão dos
   sensores” é inferência sem evidência externa. Deve ser descrita como lacuna global nos
   dados até confirmação operacional.

4. **A seleção dos 19 alarmes usa conhecimento do período completo.** Esses alarmes foram
   escolhidos porque apresentaram `Is_Dont_Go` em toda a base, incluindo validação e teste.
   Isso introduz vazamento na seleção de features. A lista deve ser derivada apenas do treino
   ou diretamente do catálogo de regras, sem consultar o target futuro.

5. **Os apontamentos possuem 427 sobreposições para `CA65789`.** Embora não existam durações
   negativas ou zeradas, as sobreposições precisam ser resolvidas antes de cruzamentos
   temporais.

### Auditoria dos resultados publicados

- As contagens brutas, os três volumes expurgados, a lacuna de 31/05, os 19 alarmes positivos
  e os splits exibidos foram reproduzidos.
- As métricas do Notebook 04 foram calculadas sobre o conjunto de teste e o threshold foi
  escolhido na validação, o que é estruturalmente correto. Porém, elas medem o target
  semanticamente inadequado e usam a fusão incorreta de TAGs; portanto ainda não são métricas
  válidas de previsão de falha.
- O ROI não é observado nos dados. `R$ 8.000/h`, `R$ 3.500/h`, `R$ 800/inspeção` e o fator
  de 50% são premissas manuais. Além disso, o downtime usado no cálculo é inválido. O valor
  de aproximadamente R$ 285 mil deve ser removido ou apresentado apenas como simulação de
  cenário, com premissas explicitadas.
- O artefato `modelo_nb04_telemetria_puro.pkl` é salvo com o modelo vencedor, mas sempre com
  `feat_A`. Quando o vencedor é `CatBoost_B`, o modelo e a lista de features são incompatíveis.
- A análise SHAP do Notebook 04 usa sempre `cat_A`, não o modelo vencedor `CatBoost_B`.
- O Notebook 05 não foi executado; seus resultados ainda não existem.

### Recomendação antes de nova modelagem

1. Redefinir formalmente o evento alvo usando as condições completas do catálogo ou um evento
   operacional confirmado nos apontamentos.
2. Agrupar linhas repetidas em episódios independentes de alerta.
3. Remover a fusão manual das quatro TAGs.
4. Criar uma política reproduzível para anomalias e duplicatas, preservando relatório
   antes/depois.
5. Reconstruir downtime somente para episódios com transição operacional compatível.
6. Reexecutar feature engineering, treino, teste, SHAP e ROI após essas correções.

## Telemetria bruta

|   registros |   ids_distintos | data_min                   | data_max                   |   tags |   alarmes |   linhas_dont_go |   pct_dont_go |
|------------:|----------------:|:---------------------------|:---------------------------|-------:|----------:|-----------------:|--------------:|
|    37164054 |        37164054 | 2025-01-01 00:00:00.017000 | 2025-06-30 23:59:56.887000 |     35 |       712 |            19962 |     0.0537132 |

| mes     |   registros |   tags |   linhas_dont_go | inicio                     | fim                        |
|:--------|------------:|-------:|-----------------:|:---------------------------|:---------------------------|
| 2025-01 |     5400002 |     32 |             2581 | 2025-01-01 00:00:00.017000 | 2025-01-31 23:59:58.737000 |
| 2025-02 |     5709935 |     30 |             4493 | 2025-02-01 00:00:03.657000 | 2025-02-28 23:59:54.920000 |
| 2025-03 |     5688538 |     30 |             4223 | 2025-03-01 00:00:01.383000 | 2025-03-31 23:59:58.827000 |
| 2025-04 |     6475045 |     32 |             2159 | 2025-04-01 00:00:01.070000 | 2025-04-30 23:59:57.267000 |
| 2025-05 |     6036291 |     31 |             1280 | 2025-05-01 00:00:01.850000 | 2025-05-30 23:59:58.983000 |
| 2025-06 |     7854243 |     31 |             5226 | 2025-06-01 00:00:00.013000 | 2025-06-30 23:59:56.887000 |

### Qualidade do target

|   Is_Dont_Go |   registros |   alarmes |   tags |
|-------------:|------------:|----------:|-------:|
|            0 |    37144092 |       706 |     35 |
|            1 |       19962 |        19 |     33 |

### Duplicidades

|   ids_repetidos_excedentes |   eventos_logicos_repetidos_excedentes |
|---------------------------:|---------------------------------------:|
|                          0 |                                 265579 |

### Nulos em campos usados

|   tag_nulo |   data_nula |   alarme_nulo |   tipo_nulo |   criticidade_nula |   classe_nula |   target_nulo |
|-----------:|------------:|--------------:|------------:|-------------------:|--------------:|--------------:|
|          0 |           0 |             0 |           0 |                  0 |             0 |             0 |

### Correções manuais de TAG

| TAG     |   registros | inicio                     | fim                        |   tipos |   linhas_dont_go |
|:--------|------------:|:---------------------------|:---------------------------|--------:|-----------------:|
| CA5926  |      107226 | 2025-01-01 00:00:14.553000 | 2025-06-30 23:57:52.887000 |       1 |              472 |
| CA5927  |       54286 | 2025-01-01 00:31:25.447000 | 2025-06-30 23:56:30.337000 |       1 |              471 |
| CA65926 |       95554 | 2025-01-01 00:03:25.787000 | 2025-06-30 23:59:11.887000 |       1 |             4923 |
| CA65927 |       87988 | 2025-01-01 00:05:33.753000 | 2025-06-30 23:48:07.083000 |       1 |             1313 |

## Regras de limpeza usadas nos notebooks

### Três dias expurgados

| exclusao      |   registros |   linhas_dont_go |   timestamps_distintos |   alarmes_distintos | inicio                     | fim                        |
|:--------------|------------:|-----------------:|-----------------------:|--------------------:|:---------------------------|:---------------------------|
| CA65932/03-26 |       12356 |                0 |                  12356 |                  15 | 2025-03-26 00:01:10.543000 | 2025-03-26 23:59:57.870000 |
| PE3797/01-12  |      136880 |                0 |                  48383 |                  37 | 2025-01-12 00:12:17.243000 | 2025-01-12 23:59:55.357000 |
| PE3798/06-29  |     1334065 |                0 |                1317842 |                  39 | 2025-06-29 00:00:01.390000 | 2025-06-29 23:57:56.303000 |

### Maiores volumes por equipamento/dia

| TAG    | dia                 |   registros |   linhas_dont_go |   timestamps_distintos |   alarmes_distintos |
|:-------|:--------------------|------------:|-----------------:|-----------------------:|--------------------:|
| PE3798 | 2025-06-29 00:00:00 |     1334065 |                0 |                1317842 |                  39 |
| PE3797 | 2025-01-12 00:00:00 |      136880 |                0 |                  48383 |                  37 |
| PE3797 | 2025-02-23 00:00:00 |       94510 |                0 |                  93424 |                  41 |
| PE3799 | 2025-02-04 00:00:00 |       90778 |                0 |                  90082 |                  33 |
| PE3797 | 2025-02-09 00:00:00 |       87507 |                0 |                  86539 |                  39 |
| PE3799 | 2025-02-09 00:00:00 |       85997 |                0 |                  85241 |                  37 |
| PE3797 | 2025-06-27 00:00:00 |       85973 |                0 |                  85028 |                  38 |
| PE3797 | 2025-02-25 00:00:00 |       85296 |                0 |                  84423 |                  40 |
| PE3797 | 2025-02-16 00:00:00 |       84364 |                0 |                  83614 |                  31 |
| PE3799 | 2025-02-12 00:00:00 |       83304 |                0 |                  82752 |                  31 |
| PE3799 | 2025-02-03 00:00:00 |       82391 |                0 |                  81533 |                  34 |
| PE3799 | 2025-03-01 00:00:00 |       81096 |                0 |                  80551 |                  60 |
| PE3795 | 2025-06-05 00:00:00 |       80460 |                0 |                  79133 |                  40 |
| PE3799 | 2025-03-09 00:00:00 |       79866 |                0 |                  79272 |                  36 |
| PE3797 | 2025-06-22 00:00:00 |       78690 |                0 |                  77843 |                  43 |
| PE3799 | 2025-03-11 00:00:00 |       78602 |                0 |                  77999 |                  36 |
| PE3796 | 2025-02-11 00:00:00 |       78258 |                0 |                  77341 |                  43 |
| PE3797 | 2025-02-18 00:00:00 |       78109 |                0 |                  77391 |                  39 |
| PE3797 | 2025-06-28 00:00:00 |       78096 |                0 |                  77230 |                  90 |
| PE3797 | 2025-02-15 00:00:00 |       78004 |                0 |                  77346 |                  28 |

## Apontamentos

|   registros |   ids_distintos |   tags | inicio_min          | fim_max             |   datas_nulas |   duracao_negativa |   duracao_zero |
|------------:|----------------:|-------:|:--------------------|:--------------------|--------------:|-------------------:|---------------:|
|      377907 |          377907 |     47 | 2025-01-01 00:00:00 | 2025-07-01 00:00:00 |             0 |                  0 |              0 |

| Classe     |   registros |   duracao_media_min |
|:-----------|------------:|--------------------:|
| Operando   |      182527 |             26.3644 |
| Parado     |      106531 |             12.7459 |
| Hibernando |       54868 |             59.9945 |
| Manutenção |       33981 |             51.6906 |

## Auditoria do chamado “downtime real”

|   linhas_dont_go |   episodios_gap_1h |   episodios_gap_8h |   mediana_h_ate_proximo_operando |   media_h_ate_proximo_operando |   sem_proximo_operando |
|-----------------:|-------------------:|-------------------:|---------------------------------:|-------------------------------:|-----------------------:|
|            19962 |               3571 |               1460 |                         0.454169 |                        2.95934 |                    198 |

### Classe operacional no instante do alerta

| classe_no_instante   |   linhas_dont_go |
|:---------------------|-----------------:|
| Operando             |            15972 |
| Manutenção           |             2560 |
| Parado               |             1239 |
| Hibernando           |              131 |

## Regras de negócio versus target entregue

|   regras |   eventos |   tipos |   situacoes |   niveis |
|---------:|----------:|--------:|------------:|---------:|
|      151 |       136 |       3 |          19 |        3 |

|   linhas_dont_go |   evento_encontrado_nas_regras |   evento_ausente_das_regras |
|-----------------:|-------------------------------:|----------------------------:|
|            19962 |                          19962 |                           0 |
