# Relatório de Decisões do Projeto Vale Correct

Última atualização: 29 de junho de 2026.

Este relatório resume as decisões tomadas até agora, sempre separando evidência observada, decisão
metodológica e limite de interpretação. O documento operacional completo de continuidade está em
`docs/CONTINUIDADE_PROJETO.md`.

## 1. Princípio de trabalho

O projeto foi reestruturado para evitar decisões por suposição. As regras adotadas são:

- dados brutos não são alterados;
- anomalia não é automaticamente erro;
- exclusões só existem em camada analítica derivada;
- toda exclusão precisa de regra localizada, justificativa e contagem antes/depois;
- `Is_Dont_Go` não é interpretado como falha, parada ou downtime confirmado;
- splits, seleção de features e thresholds respeitam ordem temporal.

## 2. Dados auditados

Telemetria:

- 37.164.054 registros brutos;
- 37.164.054 `Id_Eventos_Telemetria` distintos;
- período de 01/01/2025 a 30/06/2025;
- 35 TAGs;
- 19.962 linhas com `Is_Dont_Go = 1`;
- lacuna global em 31/05/2025.

Apontamentos:

- 377.907 registros;
- 47 TAGs;
- classes `Operando`, `Parado`, `Hibernando` e `Manutenção`;
- sem durações negativas ou zeradas na auditoria.

## 3. Target e ROI histórico

A auditoria concluiu que `Is_Dont_Go` é uma flag de presença na lista entregue. Ela não comprova:

- falha mecânica;
- parada do equipamento;
- downtime causado pelo alarme;
- atendimento integral da regra corporativa;
- independência entre eventos repetidos.

Decisão:

- remover interpretação de falha confirmada;
- não usar o downtime histórico para ROI;
- tratar o ROI anterior apenas como simulação com premissas manuais;
- usar como target provisório o início de pelo menos um novo episódio `Is_Dont_Go` nas próximas 8h.

## 4. Limpeza analítica aprovada

Decisões principais:

- não fundir `CA5926`, `CA65926`, `CA5927` e `CA65927`, pois os dados mostram equipamentos distintos;
- remover duplicatas exatas apenas da camada analítica, preservando contagem de IDs brutos por linha;
- expurgar somente o loop localizado da `PE3798` em 29/06/2025 para os alarmes Remote PTO
  `1241582851` e `1241582848`;
- preservar outros registros da `PE3798` no mesmo dia e preservar esses alarmes em outros contextos;
- invalidar janelas que atravessam a lacuna global de 31/05/2025.

Resultado da base analítica do baseline:

- 35.608.094 registros analíticos;
- 265.564 duplicatas exatas retiradas;
- 19.941 linhas analíticas `Is_Dont_Go`;
- 4.303.625 sequências;
- 14.612 sequências `Dont Go`.

## 5. Baseline temporal de 8 horas

Configuração:

- sequência por `TAG + Id_Alarme`;
- novo episódio quando o intervalo excede 60 segundos;
- 8 horas de observação;
- 8 horas de horizonte;
- treino de janeiro a abril;
- validação em maio;
- teste em junho;
- vocabulário dos 200 IDs mais frequentes escolhido apenas no treino;
- threshold escolhido apenas na validação.

Resultado do baseline `RandomForest_com_IDs` no teste:

| PR-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0,330 | 0,210 | 0,752 | 0,496 | 218 | 820 | 72 | 2.005 |

Interpretação:

- existe sinal temporal real para prever recorrência da flag;
- o modelo ainda gera muitos falsos positivos;
- o resultado não comprova previsão de falha nem causalidade.

## 6. Estados operacionais e Hibernando

Experimentos com apontamentos operacionais mostraram:

- `Hibernando` aparece no teste, mas estado dominante `Hibernando` teve 0 positivos;
- features de estado aumentaram pouco PR-AUC;
- nenhum cenário com estados superou claramente o baseline em F2;
- remover `CA65789` não mudou a conclusão geral.

Decisão:

- não excluir `Hibernando`;
- preservar `Hibernando` como feature experimental;
- não tratar `Hibernando` como correção de estado;
- priorizar representação dos alarmes antes de insistir em apontamentos.

## 7. Escavadeiras versus caminhões

Achados do notebook 06:

| Tipo | Amostras teste | Positivas reais | Predições positivas | TP | FP | FN | TN | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Caminhao | 2.670 | 288 | 1.038 | 218 | 820 | 70 | 1.562 | 0,757 |
| Escavadeira | 445 | 2 | 0 | 0 | 0 | 2 | 443 | 0,000 |

Escavadeiras têm:

- 5 TAGs;
- 32.347.375 registros analíticos;
- 2.156.657 sequências;
- apenas 167 sequências `Dont Go`.

Decisão:

- segmentar auditorias por tipo de equipamento;
- tratar maior custo/cascata de escavadeira como hipótese operacional plausível, mas ainda externa aos
  dados atuais;
- não treinar modelo pesado separado para escavadeiras enquanto o target tiver poucos positivos;
- buscar target melhor ou dado real de custo/parada antes de separar arquitetura por escavadeiras.

## 8. Conceitos de alarme

O notebook 07 testou `conceito_alarme_textual`, derivado por normalização determinística do campo
`Alarme`. Os conceitos usados como features foram selecionados por frequência apenas no treino.

Resultados no teste:

| Modelo | PR-AUC | Precisão | Recall | F2 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| RF IDs + conceitos | 0,346 | 0,205 | 0,834 | 0,518 | 936 | 48 |
| RF conceitos | 0,337 | 0,199 | 0,821 | 0,506 | 955 | 52 |
| RF IDs baseline | 0,330 | 0,210 | 0,752 | 0,496 | 820 | 72 |

Decisão:

- conceitos textuais agregam sinal e justificam próxima etapa;
- o ganho de recall veio com aumento de falsos positivos;
- criar um mapa manual pequeno de conceitos/famílias, começando pelos erros e conceitos importantes;
- testar `IDs + conceitos manuais` contra `IDs + conceitos textuais` e baseline;
- repetir auditoria de erros depois do novo modelo.

Nota para fase econômica:

- quando forem incorporados valores reais de parada, perda de produção, manutenção corretiva e
  manutenção preditiva, o objetivo poderá mudar para uma função de custo;
- nesse cenário, pode ser correto aceitar mais falsos positivos para reduzir quebras, desde que o
  custo esperado de uma falha evitada supere o custo das inspeções/intervenções adicionais;
- essa decisão deve ser validada por dados ou premissas financeiras explícitas, não por preferência
  subjetiva por recall.

## 9. Mapa manual inicial

O primeiro mapa manual de conceitos/famílias foi testado no notebook 08. Ele é exploratório, pois foi
orientado pelos erros já auditados, inclusive no teste de junho. Portanto, seus resultados servem para
desenvolvimento e precisam de validação posterior com mapa congelado.

Resultados no teste:

| Modelo | PR-AUC | Precisão | Recall | F2 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| RF IDs + conceitos textuais | 0,346 | 0,205 | 0,834 | 0,518 | 936 | 48 |
| RF IDs + famílias manuais | 0,333 | 0,215 | 0,762 | 0,505 | 806 | 69 |
| RF IDs + conceitos manuais | 0,337 | 0,198 | 0,821 | 0,503 | 967 | 52 |
| RF IDs baseline | 0,330 | 0,210 | 0,752 | 0,496 | 820 | 72 |

Decisão:

- conceitos textuais continuam sendo a melhor referência técnica em F2 e recall;
- famílias manuais são promissoras para reduzir falsos positivos;
- o mapa manual deve ser refinado de forma localizada, não expandido como taxonomia ampla;
- escavadeiras continuam sem recall, reforçando que o gargalo é target escasso ou target inadequado.

## 10. Testes temporais

O notebook 09 comparou gaps de sequência e janelas temporais. O objetivo foi verificar se a definição
de episódio e de amostra explica parte dos falsos positivos e falsos negativos.

Gaps com observação/horizonte 8h/8h:

| Gap | PR-AUC | Precisão | Recall | F2 | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|
| 30s | 0,325 | 0,197 | 0,828 | 0,504 | 980 | 50 |
| 900s | 0,343 | 0,215 | 0,751 | 0,501 | 792 | 72 |
| 60s baseline | 0,328 | 0,210 | 0,745 | 0,493 | 813 | 74 |
| 3600s | 0,272 | 0,179 | 0,772 | 0,465 | 974 | 63 |

O gap de 900s foi escolhido pela validação e apresentou melhor equilíbrio no teste que o gap inicial
de 60s.

Janelas usando gap 900s:

| Observação | Horizonte | PR-AUC | Precisão | Recall | F2 | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 24h | 24h | 0,509 | 0,306 | 0,940 | 0,665 | 1.218 | 34 |
| 24h | 8h | 0,348 | 0,205 | 0,821 | 0,512 | 910 | 51 |
| 8h | 8h | 0,343 | 0,215 | 0,751 | 0,501 | 792 | 72 |
| 12h | 8h | 0,329 | 0,193 | 0,832 | 0,500 | 1.012 | 49 |
| 4h | 4h | 0,327 | 0,242 | 0,503 | 0,413 | 304 | 96 |

Decisão:

- usar gap 900s como nova referência de desenvolvimento;
- usar observação 24h e horizonte 8h como próxima configuração principal;
- manter 8h/8h como baseline histórico comparável;
- não adotar 24h/24h como baseline principal agora, pois muda a natureza operacional do target e
  dobra aproximadamente o número de positivos no teste.

## 11. Refino do gap 24h/8h

O notebook 10 refinou a busca em torno de 900s com janela fixa 24h/8h.

Pela regra de escolha pré-definida, o melhor gap por validação foi 450s:

| Gap | Val F2 | Val precisão | Val recall | Teste F2 | Teste FP | Teste FN |
|---:|---:|---:|---:|---:|---:|---:|
| 450s | 0,489 | 0,196 | 0,780 | 0,501 | 986 | 49 |
| 600s | 0,485 | 0,194 | 0,777 | 0,516 | 977 | 42 |
| 900s | 0,471 | 0,194 | 0,735 | 0,512 | 910 | 51 |
| 1200s | 0,475 | 0,184 | 0,787 | 0,510 | 1.007 | 41 |

Decisão:

- não trocar automaticamente para 600s apenas porque foi melhor no teste;
- manter 900s como referência operacional conservadora para a próxima rodada, pois teve melhor PR-AUC
  no teste e menor FP entre os gaps competitivos;
- registrar 450s como vencedor formal por validação;
- considerar 450s, 600s e 900s como sensibilidade quando houver custo computacional;
- retestar a faixa 450s-1200s quando houver validação temporal adicional.

## 12. Conceitos e famílias em 24h/8h

O notebook 11 reavaliou as representações de alarme na configuração temporal mais promissora:
observação 24h, horizonte 8h, gap principal 900s, com sensibilidade para 450s e 600s.

No gap principal 900s, resultado no teste:

| Modelo | PR-AUC | Precisão | Recall | F2 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| RF IDs + conceitos textuais | 0,333 | 0,230 | 0,789 | 0,531 | 753 | 60 |
| RF IDs + conceitos textuais + famílias | 0,340 | 0,200 | 0,849 | 0,514 | 971 | 43 |
| RF IDs + famílias manuais | 0,352 | 0,192 | 0,842 | 0,501 | 1.013 | 45 |
| RF IDs | 0,336 | 0,182 | 0,828 | 0,485 | 1.059 | 49 |

Sensibilidade:

- em 450s, o melhor modelo no teste também foi `RF IDs + conceitos textuais`, F2 0,517;
- em 600s, o melhor F2 no teste foi `RF IDs`, F2 0,521;
- em 900s, `RF IDs + conceitos textuais` teve o melhor F2, 0,531, e menos FP entre os modelos de
  maior desempenho.

Decisão:

- nova referência técnica: gap 900s, observação 24h, horizonte 8h, `IDs + conceitos textuais`;
- famílias manuais ficam como ferramenta de análise e interpretabilidade, não como feature principal;
- a próxima etapa deve auditar FP/FN dessa nova referência contra o baseline histórico.

## 13. Auditoria da nova referência

O notebook 12 comparou a nova referência técnica contra o baseline histórico, mantendo escolha de
threshold na validação.

Resultado global no teste:

| Modelo | PR-AUC | ROC-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 60s 8h/8h IDs | 0,328 | 0,807 | 0,210 | 0,745 | 0,493 | 216 | 813 | 74 | 2.012 |
| Referência 900s 24h/8h IDs + conceitos | 0,333 | 0,821 | 0,227 | 0,730 | 0,505 | 208 | 710 | 77 | 2.050 |

Delta observado:

- PR-AUC: +0,005;
- precisão: +0,017;
- recall: -0,015;
- F2: +0,012;
- falsos positivos: -103;
- falsos negativos: +3.

Decisão:

- manter `gap=900s`, observação 24h, horizonte 8h e `IDs + conceitos textuais` como referência de
  desenvolvimento;
- aceitar essa referência como melhor equilíbrio atual porque reduz falsos positivos e melhora F2,
  sem afirmar que ela é o threshold final de produção;
- quando houver custos reais de parada/manutenção/perda de produção, reavaliar threshold e métrica de
  decisão, possivelmente aceitando mais falsos positivos para reduzir quebras.

Escavadeiras:

- baseline: 445 amostras, 2 positivos reais, 0 predições positivas, recall 0;
- nova referência: 435 amostras, 2 positivos reais, 0 predições positivas, recall 0;
- conclusão: a nova referência não resolve escavadeiras. A segmentação por tipo segue necessária na
  auditoria, mas um modelo próprio para escavadeiras continua prematuro com apenas 2 positivos no
  teste e sem target operacional mais forte.

## 14. Multijanelas temporais

O notebook 13 testou representações multijanelas mantendo fixos `gap=900s`, observação 24h,
horizonte 8h, target, split e Random Forest.

Resultado no teste:

| Cenário | PR-AUC | Precisão | Recall | F2 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Multijanela core | 0,363 | 0,188 | 0,877 | 0,506 | 250 | 1.082 | 35 |
| Multijanela híbrida | 0,372 | 0,186 | 0,884 | 0,506 | 252 | 1.100 | 33 |
| Referência agregada 24h | 0,333 | 0,227 | 0,730 | 0,505 | 208 | 710 | 77 |
| Multijanela IDs/conceitos por bucket | 0,372 | 0,184 | 0,849 | 0,492 | 242 | 1.075 | 43 |

Leitura:

- multijanelas aumentam PR-AUC e recall, então há sinal real de recência;
- a multijanela core recupera 42 positivos adicionais contra a referência agregada;
- o custo é adicionar 372 falsos positivos;
- como F2 fica praticamente empatado, a troca automática da referência não é justificada;
- escavadeiras seguem com recall zero, inclusive na multijanela.

Decisão:

- manter `900s + 24h/8h + IDs + conceitos textuais` agregado como baseline técnico principal;
- preservar `multijanela_core_ids_textual` como candidato para cenário orientado a recall/custo;
- não adotar as versões com IDs/conceitos por bucket agora, pois aumentam complexidade sem ganho
  suficiente;
- o `PerformanceWarning` observado é aviso de desempenho por fragmentação de `DataFrame`, não erro de
  execução nem invalidação dos resultados.

## 15. Próxima fase

Ordem atual:

1. buscar dados reais ou premissas aprovadas de custo e, principalmente, uma ligação observável entre
   alerta, intervenção, parada ou manutenção;
2. manter escavadeiras, tags com FP alto e falsos negativos de baixa probabilidade como recortes
   obrigatórios de auditoria;
3. depois comparar novos algoritmos;
4. só discutir produção, downtime ou ROI após target/consequência operacional mais forte.

Justificativa:

- o gap atual de 60 segundos é uma premissa inicial, não um parâmetro validado;
- os alarmes têm cadências muito diferentes, então parte dos FP/FN pode vir de agrupamento temporal;
- refinar famílias antes de validar sequência e janela aumenta o risco de ajustar taxonomia ao teste
  de junho;
- o mapa manual fica preservado, mas seu refinamento será retomado depois dos testes temporais.

Notebook executado:

- `13_Teste_Multijanelas_Temporais.ipynb`;
- conclusão consolidada: multijanelas são úteis para recall, mas ainda não substituem a referência
  agregada sem uma função de custo.

## 16. Threshold e cenários de custo

O notebook `14_Threshold_Curva_Decisao_Custo.ipynb` comparou a referência agregada contra a
`multijanela_core_ids_textual` com curva explícita de thresholds e uma camada econômica de
sensibilidade.

Limite:

- os custos usados são premissas externas, não valores observados no projeto;
- `p_acao_confirmada` foi incluído porque `Is_Dont_Go` não é falha confirmada;
- a análise econômica não é ROI.

Resultado técnico no teste, com threshold escolhido por F2 na validação:

| Cenário | Threshold | PR-AUC | Precisão | Recall | F2 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Referência agregada 24h | 0,185 | 0,333 | 0,230 | 0,789 | 0,531 | 225 | 753 | 60 |
| Multijanela core | 0,145 | 0,362 | 0,200 | 0,846 | 0,514 | 241 | 965 | 44 |

Decisão técnica:

- manter a referência agregada como baseline principal;
- a multijanela core recupera 16 positivos adicionais, mas adiciona 212 falsos positivos;
- a multijanela core continua candidata apenas para cenário de alto custo operacional/alto recall.

Resultado econômico:

- as premissas externas com fonte estão documentadas em `docs/PREMISSAS_ECONOMICAS_EXTERNAS.md`;
- após o notebook 15, o cenário base passou a usar `p_acao_confirmada = 0,655` para caminhões, derivado
  do treino pela taxa `Dont Go -> Manutenção em 8h`;
- com essa premissa empírica, a otimização econômica escolheu threshold 0,445 para a referência
  agregada e 0,425 para a multijanela core;
- no teste, o valor incremental simulado foi 1.942.800 para a referência e 2.096.000 para a
  multijanela core;
- os thresholds técnicos de F2 continuam economicamente ruins por excesso de falsos positivos;
- em cenários de sensibilidade mais agressivos, com maior impacto operacional e maior
  `p_acao_confirmada`, a multijanela core passou a vencer.

Conclusão:

O projeto agora tem uma ligação observável entre `Is_Dont_Go` e `Manutenção` em caminhões, suficiente
para uma simulação econômica melhor que a premissa externa de 20%. Ainda não é ROI observado: faltam
custo real, causalidade operacional e separação entre manutenção preventiva, corretiva e rotina.

## 17. Validação operacional do target

O notebook `15_Validacao_Operacional_Target.ipynb` mediu a relação entre episódios `Is_Dont_Go` e
apontamentos `Manutenção`.

Limites:

- `Manutenção` é proxy de intervenção, não causalidade;
- janelas que atravessam `2025-05-31` foram invalidadas;
- o período completo aparece apenas como descrição retrospectiva.

Achados principais:

- foram encontrados 33.981 apontamentos `Manutenção`;
- a mediana de duração de `Manutenção` é 1,0h em caminhões e escavadeiras, nos três splits;
- em caminhões, episódios `Is_Dont_Go` seguidos por manutenção em até 8h tiveram taxa:
  - treino: 0,655;
  - validação: 0,788;
  - teste: 0,751;
- no sentido inverso, apenas parte das manutenções é precedida por `Is_Dont_Go` em até 8h:
  - caminhões treino: 0,189;
  - caminhões validação: 0,156;
  - caminhões teste: 0,151;
- escavadeiras têm poucos episódios `Is_Dont_Go`, então as taxas `Dont Go -> Manutenção` são
  instáveis, e a cobertura `Manutenção -> Dont Go anterior` fica abaixo de 3% em 8h.

Decisão:

- existe associação operacional mensurável entre `Is_Dont_Go` e manutenção posterior em caminhões;
- `Is_Dont_Go` não é target geral de manutenção, pois cobre parcela pequena das manutenções totais;
- usar `Dont Go -> Manutenção em 8h` como primeira estimativa empírica de `p_acao_confirmada` para
  caminhões em cenários econômicos;
- não usar essa taxa para escavadeiras sem mais dados;
- manter a janela 8h como candidata porque é coerente com o horizonte atual do modelo e foi razoável
  em validação e teste.

## 18. Calibração de probabilidades

O notebook `16_Calibracao_Probabilidades.ipynb` avaliou calibração para a referência agregada e a
multijanela core.

Desenho:

- treino do modelo base: janeiro-março;
- calibração: abril;
- threshold: maio;
- teste final: junho.

Achado de calibração:

- os scores brutos superestimavam a prevalência no teste;
- calibração reduziu Brier/ECE;
- melhor Brier no teste:
  - multijanela core isotônica: Brier 0,0715, ECE 0,0135;
  - referência sigmoide: Brier 0,0732, ECE 0,0174.

Resultado econômico no teste, com threshold escolhido na validação:

| Cenário | Calibração | Threshold | Valor incremental | Precisão | Recall | TP | FP | FN |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Multijanela core | Sigmoide | 0,310 | 2.454.300 | 0,441 | 0,277 | 79 | 100 | 206 |
| Multijanela core | Isotônica | 0,315 | 2.379.400 | 0,432 | 0,288 | 82 | 108 | 203 |
| Referência agregada | Sigmoide | 0,405 | 2.298.600 | 0,487 | 0,204 | 58 | 61 | 227 |

Decisão:

- calibração é necessária se o score for usado para decisão econômica;
- melhor candidato econômico até aqui: `multijanela_core_ids_textual` com calibração sigmoide;
- baseline técnico principal segue sendo a referência agregada até comparação de algoritmos e
  estabilidade temporal final;
- os valores econômicos seguem simulação, não ROI observado.

## 19. Comparação de algoritmos calibrados

O notebook `17_Comparacao_Algoritmos_Calibrados.ipynb` comparou RandomForest, XGBoost, LightGBM e
CatBoost em três splits temporais, sempre com calibração sigmoide e threshold econômico escolhido
antes do mês de teste.

Splits:

| Split | Treino | Calibração | Threshold | Teste |
|---|---|---|---|---|
| S1 | Jan/2025 | Fev/2025 | Mar/2025 | Abr/2025 |
| S2 | Jan-Fev/2025 | Mar/2025 | Abr/2025 | Mai/2025 |
| S3 | Jan-Mar/2025 | Abr/2025 | Mai/2025 | Jun/2025 |

Vencedores por split:

| Split | Melhor combinação | Valor incremental | Precisão | Recall |
|---|---|---:|---:|---:|
| S1 | Referência + RandomForest | 3.005.700 | 0,413 | 0,332 |
| S2 | Multijanela + CatBoost | 1.652.600 | 0,398 | 0,272 |
| S3 | Multijanela + XGBoost | 3.820.200 | 0,467 | 0,372 |

Ranking médio por valor incremental:

| Ranking | Combinação | Valor médio | Valor mínimo | Valor máximo | Precisão média | Recall médio |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Multijanela + CatBoost | 2.379.933 | 1.652.600 | 3.319.800 | 0,415 | 0,312 |
| 2 | Multijanela + RandomForest | 2.165.200 | 1.569.200 | 2.742.700 | 0,420 | 0,280 |
| 3 | Referência + CatBoost | 2.158.100 | 861.100 | 2.894.300 | 0,412 | 0,296 |
| 4 | Multijanela + XGBoost | 1.955.167 | 608.000 | 3.820.200 | 0,406 | 0,287 |

Decisão:

- `multijanela_core_ids_textual + CatBoost + calibração sigmoide` passa a ser o candidato principal
  econômico;
- `referencia_24h_ids_textual + RandomForest` permanece como baseline simples e competitivo;
- XGBoost não deve ser descartado, pois venceu junho, mas a média e o mínimo foram inferiores ao
  CatBoost;
- não há suporte operacional robusto para escavadeiras nesta formulação, pois os eventos
  `Is_Dont_Go` são raros e o melhor candidato concentrou valor em caminhões;
- a próxima etapa deve auditar explicabilidade, estabilidade de threshold e robustez antes de chamar
  o candidato de modelo principal.

## 20. Threshold explícito e robustez

O notebook `18_Threshold_Robustez_Curva_Decisao.ipynb` auditou a curva de decisão dos candidatos em
um grid explícito de thresholds de 0,01 a 0,99.

Definição usada:

- threshold robusto = pelo menos 95% do melhor valor médio do modelo e valor positivo em todos os
  splits de teste.

Faixas robustas:

| Modelo | Thresholds robustos | Faixa | Valor médio máximo | Pior split mínimo |
|---|---:|---:|---:|---:|
| Referência + RandomForest | 4 | 0,415-0,430 | 2.305.100 | 1.302.000 |
| Multijanela + CatBoost | 12 | 0,410-0,490 | 2.811.367 | 2.190.500 |
| Multijanela + XGBoost | 14 | 0,380-0,445 | 2.425.400 | 1.729.200 |

Sensibilidade econômica:

- CatBoost multijanela venceu todos os cenários médios testados;
- XGBoost multijanela ficou próximo em cenários conservadores e segue como candidato de
  sensibilidade;
- referência RF continua positiva e auditável, mas inferior ao CatBoost na média e menos robusta em
  cenários conservadores.

Decisão:

- manter `multijanela_core_ids_textual + CatBoost + calibração sigmoide` como candidato principal;
- usar faixa operacional candidata de threshold `0,410-0,490`;
- manter `referencia_24h_ids_textual + RandomForest` como baseline, faixa `0,415-0,430`;
- testar no próximo ciclo um modelo treinado apenas em caminhões;
- não treinar modelo separado de escavadeiras ainda, pois o volume mensal de positivos fica entre 1 e
  7 eventos, insuficiente para uma avaliação confiável.
