# Continuidade do Projeto Vale Correct

Última atualização: 29 de junho de 2026.

Este documento registra o histórico técnico, as decisões aprovadas, os resultados auditados e os
próximos passos do projeto. Ele deve ser lido no início de uma nova sessão antes de qualquer
alteração nos dados, notebooks ou modelos.

## 1. Princípio orientador

> Este projeto estabelece uma base de investigação sem remover registros brutos e sem converter
> anomalias em erros por suposição. Toda transformação deve ser reproduzível, rastreável e sustentada
> pelos dados.

Consequências práticas:

- arquivos brutos nunca são alterados;
- exclusões existem somente em camadas analíticas derivadas;
- toda exclusão deve ter regra, justificativa e contagem antes/depois;
- anomalia não é automaticamente erro;
- `Is_Dont_Go` não é interpretado como falha ou parada confirmada;
- splits e transformações temporais devem impedir vazamento de dados.

## 2. Repositório e ambiente

- Repositório: <https://github.com/FSzekut/vale_correct>
- Branch de trabalho: `auditoria-correcao-dados`
- Ambiente virtual local: `.venv`
- Dados locais: `data/raw/Base`
- Os dados e o ambiente virtual estão protegidos pelo `.gitignore`.

Último commit remoto anterior ao baseline:

```text
14d78f3 Normalize notebook file permissions
```

O baseline auditado foi registrado localmente no commit:

```text
807a50d Add audited baseline notebook
```

A branch local está um commit à frente do remoto enquanto não houver novo `git push`.

## 3. Estrutura dos notebooks

### `00_EDA_Historico_Original.ipynb`

Cópia preservada do EDA histórico. Não foi executada nem corrigida. Serve apenas como registro do
estado anterior do projeto.

### `01_Auditoria_e_Preparacao_Dos_Dados.ipynb`

Auditoria estrutural, semântica e temporal das fontes. Foi executado integralmente sem erros.

### `02_Aprofundamento_Das_Decisoes_Pendentes.ipynb`

Aprofundamento dos conflitos de nomes, duplicidades, anomalias de volume, sobreposições operacionais,
regras e sensibilidade dos episódios. Foi executado integralmente sem erros.

### `SIDE_Destrinchar_Tempos_Dos_Alarmes.ipynb`

Estudo lateral da cadência de emissão dos alarmes e da variação entre equipamentos. Não é uma etapa
numerada da preparação. Foi executado integralmente sem erros.

### `03_Baseline_Episodios_8h.ipynb`

Primeira preparação auditada para treinamento, formação de sequências e baseline temporal. Foi
executado integralmente sem erros.

### `04_Auditoria_Do_Baseline_8h.ipynb`

Auditoria do baseline de 8 horas por `TAG`, tipo de equipamento, período, faixas de probabilidade e
drill down de falsos positivos/falsos negativos. Reproduz as premissas do notebook 03 sem alterar
limpeza, target, split ou threshold. Foi executado integralmente sem erros.

### `05_Cenarios_Estados_Hibernando.ipynb`

Experimento de cenários com apontamentos operacionais e `Hibernando`, mantendo a base do notebook 03
congelada. Compara Random Forest baseline, XGBoost baseline e variações com features de estado. Foi
executado integralmente sem erros.

### `06_Investigacao_Erros_E_Familias.ipynb`

Investigação dos erros do baseline e de candidatos iniciais a conceitos/famílias de alarme, sem
alterar limpeza, target, split, sequência, janela ou threshold. Foi executado integralmente sem erros.

### `07_Modelo_Com_Conceitos_De_Alarme.ipynb`

Primeiro teste controlado de representação por `conceito_alarme_textual`, derivado por normalização
determinística do campo `Alarme`. Compara IDs, conceitos, IDs + conceitos e flags leves de tipo de
equipamento. Foi executado integralmente sem erros.

### `08_Modelo_Com_Mapa_Manual_De_Conceitos.ipynb`

Experimento exploratório com primeiro mapa manual pequeno de `conceito_alarme` e `familia_alarme`,
orientado pelos achados dos notebooks 06 e 07. Compara IDs, conceitos textuais, conceitos manuais e
famílias manuais. Foi executado integralmente sem erros.

### `09_Teste_Gaps_E_Janelas_Temporais.ipynb`

Experimento temporal com diferentes gaps de sequência e combinações de observação/horizonte, mantendo
limpeza, split e modelo de referência. Foi executado integralmente sem erros.

### `10_Refino_Gap_Sequencia_24h8h.ipynb`

Refino do gap de sequência em torno de 900s usando janela fixa 24h/8h. Foi executado integralmente
sem erros.

### `11_Conceitos_Familias_24h8h_Sensibilidade_Gap.ipynb`

Reavaliação de `IDs`, `IDs + conceitos textuais`, `IDs + famílias manuais` e `IDs + conceitos
textuais + famílias manuais` com janela 24h/8h. Usa gap principal 900s e sensibilidade para 450s e
600s. Foi executado integralmente sem erros.

### `12_Auditoria_Nova_Referencia_24h8h.ipynb`

Auditoria comparativa da nova referência `900s + 24h/8h + IDs + conceitos textuais` contra o baseline
histórico `60s + 8h/8h + IDs`, com recortes por tipo, `TAG`, FP e FN. Foi executado integralmente sem
erros.

### `13_Teste_Multijanelas_Temporais.ipynb`

Teste investigativo de representações multijanelas dentro das 24h anteriores à previsão. Mantém
`gap=900s`, horizonte 8h, target, split e Random Forest, comparando a referência agregada 24h contra
buckets 0-8h, 8-16h e 16-24h. Foi executado integralmente; houve apenas `PerformanceWarning` na
criação de features derivadas por fragmentação de `DataFrame`, sem erro de execução.

Os notebooks são reproduzidos pelos scripts em `scripts/create_*.py`. Alterações permanentes devem
ser feitas prioritariamente nos geradores, seguidas de regeneração e execução completa do notebook.

## 4. Inventário dos dados

### Telemetria

- 37.164.054 registros brutos;
- 37.164.054 `Id_Eventos_Telemetria` distintos;
- período de 01/01/2025 a 30/06/2025;
- 35 TAGs;
- 1.324 `Id_Alarme` e 712 descrições distintas de alarme;
- 19.962 linhas com `Is_Dont_Go = 1`;
- ausência global de registros em 31/05/2025;
- sem nulos nos campos essenciais auditados.

Significado dos identificadores:

- `Id_Eventos_Telemetria`: identificador da leitura/evento individual;
- `TAG`: identificador do equipamento;
- `Id_Alarme`: identificador do tipo de alarme.

### Apontamentos

- 377.907 registros;
- 47 TAGs;
- classes: `Operando`, `Parado`, `Hibernando` e `Manutenção`;
- não foram encontradas durações negativas ou iguais a zero.

## 5. Auditoria do target histórico

`Is_Dont_Go` é uma flag indicando que o alarme consta na lista entregue. Ela não comprova:

- falha mecânica;
- parada do equipamento;
- satisfação integral de uma regra corporativa;
- início de um episódio independente;
- downtime causado pelo alarme.

Conclusões:

- as 19.962 linhas positivas não são 19.962 falhas;
- o downtime histórico calculava tempo até o próximo início de `Operando`, mesmo quando o
  equipamento já estava operando;
- esse downtime não deve alimentar ROI;
- o ROI histórico é uma simulação com premissas manuais, não resultado observado;
- métricas dos modelos históricos não são válidas como previsão de falha confirmada.

O target provisório do baseline é:

> Início de pelo menos um novo episódio contendo `Is_Dont_Go = 1` nas próximas 8 horas.

O modelo prevê recorrência da flag fornecida, não falha operacional confirmada.

## 6. Decisões de qualidade e limpeza

### TAGs semelhantes

`CA5926`, `CA65926`, `CA5927` e `CA65927` são equipamentos distintos. Eles coexistem, possuem
históricos próprios e não devem ser fundidos.

### Duplicatas

Foram encontradas 265.564 duplicatas exatas excedentes após desconsiderar somente
`Id_Eventos_Telemetria`.

Decisão:

- preservar todas na camada bruta;
- sinalizar os grupos duplicados;
- manter o menor ID como referência na camada analítica;
- retirar apenas as cópias exatas do treinamento;
- registrar quantos IDs brutos cada linha analítica representa.

Existem aproximadamente dez repetições lógicas excedentes que não são cópias exatas. Elas foram
preservadas porque possuem diferenças contextuais, não são `Dont Go` e não há evidência de erro.

### Nomes dos alarmes

Após trim, normalização Unicode, capitalização, espaços e remoção do sufixo textual `(L-1850)`,
restaram 11 conflitos entre `Id_Alarme` e descrição. Eles correspondem a:

- problemas de codificação de caracteres, como `Ó` versus `?`;
- nomes semanticamente equivalentes, como `ENTRADA ARTICULADA` e
  `ENTRADA OPERAÇÃO ARTICULADA`.

Decisão:

- usar `Id_Alarme` como chave principal;
- preservar o texto bruto;
- criar descrição normalizada;
- futuramente construir `conceito_alarme` e `familia_alarme`;
- não formar famílias apenas por similaridade textual: componente, posição e significado técnico
  também devem ser considerados.

## 7. Anomalias de volume

### PE3798 em 29/06/2025

Foram encontrados 1.334.065 registros no dia. Dois alarmes Remote PTO explicam 1.290.396 registros:

| Id_Alarme | Resumo | Registros |
|---:|---|---:|
| `1241582851` | Remote PTO - Not Configured | 645.199 |
| `1241582848` | Remote PTO - Switch Off | 645.197 |

Os sinais alternam em dezenas de milissegundos e não possuem `Dont Go`.

Regra aprovada para a camada de treinamento:

```text
TAG = PE3798
data = 2025-06-29
Id_Alarme IN (1241582851, 1241582848)
```

Somente essa combinação é expurgada. Os outros 43.669 registros da PE3798 no mesmo dia são
preservados. Os dois IDs também são preservados em outros dias ou equipamentos.

Outras anomalias de volume permanecem sinalizadas e aguardam investigação específica. Não existe
regra universal de exclusão aprovada.

## 8. Estados operacionais e sobreposições

A `CA65789` possui 427 sobreposições de apontamentos, sempre envolvendo `Hibernando`:

- `Hibernando` com `Operando`: 241;
- `Hibernando` com `Parado`: 155;
- `Hibernando` com `Manutenção`: 31.

Entretanto, excluindo a `CA65789`, outras máquinas também emitem alarmes enquanto estão
exclusivamente:

- `Hibernando`: 7.277 registros em 9 TAGs, incluindo 131 `Dont Go`;
- `Parado`: 2.638.033 registros em 32 TAGs, incluindo 1.184 `Dont Go`.

Logo, não se pode descartar `Hibernando` quando existe um alarme. Essa regra introduziria viés.

Experimentos futuros aprovados:

1. modelo sem apontamentos operacionais;
2. modelo com estado principal;
3. estado principal mais flags de hibernação e sobreposição;
4. modelo 3 sem a `CA65789`;
5. modelo 3 sem informação relacionada a `Hibernando`.

## 9. Tempos e sequências de alarmes

Os logs não são emitidos regularmente a cada segundo:

- mediana global entre registros consecutivos do mesmo `TAG + Id_Alarme`: aproximadamente 6,1 s;
- somente 0,035% dos intervalos são exatamente 1 s;
- existem sinais em milissegundos e outros separados por minutos ou horas.

Um intervalo entre registros mistura:

1. retransmissão enquanto a condição permanece ativa;
2. ausência real seguida de nova ocorrência.

Mediana, P90 e P99 descrevem a distribuição dos intervalos, mas não definem automaticamente o fim de
um episódio.

Hierarquia futura para um mapa de tempos:

1. parâmetro por `Id_Alarme`;
2. parâmetro por família ou conceito;
3. parâmetro global como fallback;
4. `Id_Alarme + TAG` somente se a variação entre equipamentos justificar.

No baseline foi aprovado um limite inicial de 60 segundos:

- registros do mesmo `TAG + Id_Alarme` separados por até 60 s pertencem à mesma sequência;
- intervalo maior que 60 s inicia nova sequência;
- esse parâmetro ainda não é considerado ótimo ou definitivo.

## 10. Lacuna global de 31/05/2025

O dia não é preenchido com zeros. Zero significaria equipamento observado sem alarmes, mas o que
existe é ausência de observação.

No baseline:

- foram usadas fronteiras de 8 horas em `00:00`, `08:00` e `16:00`;
- features usam sequências iniciadas nas 8 horas anteriores;
- target usa novos episódios iniciados nas 8 horas seguintes;
- qualquer amostra cuja observação ou horizonte coincida com 31/05 é invalidada;
- 140 amostras foram removidas devido à lacuna;
- nenhuma sequência conecta 30/05 a 01/06.

## 11. Baseline de 8 horas

### Preparação

- 1.290.396 registros do loop localizado foram expurgados;
- 265.564 duplicatas exatas foram retiradas da camada analítica;
- restaram 35.608.094 registros analíticos;
- 19.941 linhas analíticas possuem `Is_Dont_Go = 1`;
- foram formadas 4.303.625 sequências;
- 14.612 sequências possuem `Is_Dont_Go`;
- quase todos os episódios positivos possuem `Activate`, mas 167 positivos têm `Classe` nula e
  foram preservados.

### Janelas e splits

- observação: 8 horas;
- horizonte: 8 horas;
- treino: janeiro a abril;
- validação: 1 a 30 de maio;
- teste: junho, começando em 01/06 às 08:00;
- nenhuma divisão aleatória foi utilizada;
- vocabulário dos 200 IDs mais frequentes foi escolhido somente no treino;
- threshold foi selecionado somente na validação;
- teste não participou de seleção de features, parâmetros ou threshold.

Distribuição:

| Split | Amostras | Positivas | Prevalência |
|---|---:|---:|---:|
| Treino | 12.565 | 1.922 | 15,30% |
| Validação | 3.150 | 288 | 9,14% |
| Teste | 3.115 | 290 | 9,31% |

### Features básicas

- total de sequências;
- alarmes distintos;
- registros analíticos e brutos representados;
- duração média e máxima;
- maior sequência;
- sequências críticas, `Activate`, `Inactive` e classe nula;
- hora e dia da semana em codificação cíclica;
- contagens dos 200 `Id_Alarme` mais frequentes no treino.

Não foram usadas famílias, multijanelas, catálogo corporativo ou informações operacionais.

### Modelos

Foram comparados:

- `DummyClassifier`;
- Random Forest somente com agregados;
- Random Forest com agregados e IDs.

Resultados no teste:

| Modelo | PR-AUC | Precisão | Recall | F2 |
|---|---:|---:|---:|---:|
| Dummy | 0,093 | 0,000 | 0,000 | 0,000 |
| Random Forest agregado | 0,211 | 0,166 | 0,817 | 0,458 |
| Random Forest com IDs | 0,330 | 0,210 | 0,752 | 0,496 |

O modelo com IDs encontrou 218 dos 290 positivos, com:

- 72 falsos negativos;
- 820 falsos positivos;
- 2.005 verdadeiros negativos.

### Interpretação auditada

O baseline demonstra que existe sinal temporal para prever recorrência da flag. O resultado não é
somente memorização de IDs, pois o modelo agregado também supera o Dummy.

Entretanto, os IDs elevam significativamente o PR-AUC. Na camada analítica:

- 20 IDs são sempre positivos;
- 27 IDs possuem rótulo misto;
- 1.277 IDs são sempre negativos.

Portanto, parte do ganho vem da recorrência de tipos específicos de alarme. O resultado não comprova
previsão de falha nem causalidade.

## 12. Catálogo corporativo

O livro de regras histórico não será implementado literalmente. O projeto pretende desenvolver
novas regras e modelos.

O catálogo mostrou que múltiplos `Id_Alarme` podem representar o mesmo conceito corporativo. Essa
informação motivou a futura criação de famílias/conceitos, mas não será usada como vínculo obrigatório
entre `EVENTO` e `Id_Alarme`.

## 13. Auditoria do baseline

O notebook `04_Auditoria_Do_Baseline_8h.ipynb` reproduziu a base e o modelo do notebook 03:

- 35.608.094 registros analíticos;
- 265.564 duplicatas exatas retiradas da camada analítica;
- 19.941 linhas analíticas `Is_Dont_Go`;
- 4.303.625 sequências;
- 14.612 sequências `Dont Go`;
- split de teste com 3.115 amostras e 290 positivas.

O modelo auditado foi o `RandomForest_com_IDs`, com threshold 0,205 escolhido na validação.

Resultados reproduzidos:

| Conjunto | PR-AUC | ROC-AUC | Precisão | Recall | F2 |
|---|---:|---:|---:|---:|---:|
| Validação | 0,336 | 0,788 | 0,204 | 0,691 | 0,467 |
| Teste | 0,330 | 0,808 | 0,210 | 0,752 | 0,496 |

Matriz no teste:

|  | Previsto 0 | Previsto 1 |
|---|---:|---:|
| Real 0 | 2.005 | 820 |
| Real 1 | 72 | 218 |

Principais achados por `TAG`:

- mais falsos negativos: `CA65935` (8), `CA65937` (7), `CA65936` (6), `CA65933` (6);
- mais falsos positivos: `CA65792` (60), `CA5927` (51), `CA65928` (48), `CA65930` (48),
  `CA65916` (47);
- `CA65926` teve alta prevalência no teste (55 positivos em 89 amostras) e alto recall
  (52 de 55), mas ainda com 22 falsos positivos;
- `CA65792`, `CA5927`, `CA65928`, `CA65930` e `CA65916` indicam sensibilidade excessiva do
  threshold/modelo para certas recorrências.

Achados por tipo:

- caminhões concentram quase todo o target do teste: 288 positivos, recall 0,757;
- escavadeiras tiveram apenas 2 positivos no teste e ambos foram falsos negativos;
- a baixa prevalência nas escavadeiras não permite concluir ausência de risco, apenas que o
  baseline atual não aprendeu sinal suficiente para esse tipo.

Achados temporais:

- não houve diferença relevante entre os horários 00h, 08h e 16h;
- os dias com mais falsos negativos foram 22/06 (7), 24/06 (6) e 20/06 (5);
- o recall semanal caiu nas semanas finais de junho, sugerindo possível mudança de regime ou
  limitação das features atuais;
- os dados vão até `2025-06-30 23:59:56.887`, então a última janela do teste tem horizonte
  praticamente completo.

Faixas de probabilidade:

- a taxa positiva cresce nas faixas mais altas, indicando que o score ordena risco de forma útil;
- há 38 falsos negativos dentro de +/- 0,05 do threshold, portanto parte dos erros é sensível à
  decisão de corte;
- falsos positivos de alta probabilidade devem ser investigados antes de qualquer ajuste agressivo
  de threshold.

Conclusão:

O baseline tem sinal temporal real para recorrência da flag, mas ainda opera com muitos falsos
positivos. A próxima melhoria deve investigar padrões por `TAG` e `Id_Alarme` nos erros antes de
adicionar complexidade ao modelo.

## 14. Cenários com estados e Hibernando

O notebook `05_Cenarios_Estados_Hibernando.ipynb` testou features de apontamentos operacionais sem
alterar limpeza, target, split, sequência ou janela do baseline.

Cobertura dos estados nas janelas:

- no teste, `Hibernando` aparece em 466 de 3.115 amostras;
- estado dominante `Hibernando` teve 463 amostras no teste e 0 positivos;
- estado dominante `Operando` concentrou 252 dos 290 positivos do teste;
- escavadeiras continuam com poucos positivos e baixo sinal aprendido.

Resultados no teste:

| Cenário | PR-AUC | Precisão | Recall | F2 | Predições positivas |
|---|---:|---:|---:|---:|---:|
| RF baseline IDs | 0,330 | 0,210 | 0,752 | 0,496 | 1.038 |
| XGB baseline IDs | 0,322 | 0,183 | 0,797 | 0,477 | 1.262 |
| XGB estado sem Hibernando | 0,340 | 0,245 | 0,583 | 0,457 | 691 |
| XGB estado com Hibernando | 0,341 | 0,202 | 0,721 | 0,476 | 1.035 |
| XGB flags Hibernando | 0,342 | 0,191 | 0,731 | 0,467 | 1.112 |
| XGB flags sem CA65789 | 0,340 | 0,187 | 0,794 | 0,482 | 1.218 |

Leitura auditada:

- XGBoost sem novas features aumentou recall, mas piorou precisão e F2 contra o RF baseline;
- features de estado aumentaram levemente PR-AUC, mas não superaram o RF baseline em F2;
- retirar informação explícita de `Hibernando` aumentou precisão, porém reduziu recall de forma forte;
- incluir `Hibernando` não resolveu falsos positivos e não justificou tratamento especial neste ponto;
- remover `CA65789` não mudou a conclusão geral, então a sobreposição dessa TAG não explica sozinha o
  comportamento do modelo;
- `Hibernando` deve continuar preservado como feature experimental, mas não deve ser usado como regra
  de exclusão nem como correção de estado.

Decisão provisória:

O próximo ganho provavelmente não virá de estados operacionais isolados. Antes de insistir em
apontamentos, priorizar famílias/conceitos de alarme, janelas multiescala e análise dos falsos
positivos por `TAG + Id_Alarme`.

## 15. Investigação de erros e candidatos a famílias

O notebook `06_Investigacao_Erros_E_Familias.ipynb` reproduziu o mesmo baseline auditado:

- threshold 0,205 escolhido na validação;
- teste com 3.115 amostras e 290 positivas;
- matriz no teste: 2.005 TN, 820 FP, 218 TP e 72 FN;
- PR-AUC 0,330, precisão 0,210, recall 0,752 e F2 0,496.

Achados por tipo:

| Tipo | Amostras teste | Positivas reais | Predições positivas | TP | FP | FN | TN | Recall | Prevalência |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Caminhao | 2.670 | 288 | 1.038 | 218 | 820 | 70 | 1.562 | 0,757 | 10,79% |
| Escavadeira | 445 | 2 | 0 | 0 | 0 | 2 | 443 | 0,000 | 0,45% |

Achados específicos para escavadeiras:

- existem 5 TAGs de escavadeira na telemetria analítica;
- elas concentram 32.347.375 registros analíticos, contra 3.260.719 registros de caminhões;
- geraram 2.156.657 sequências, número próximo ao dos caminhões;
- possuem apenas 167 sequências `Dont Go`, contra 14.445 nos caminhões;
- no teste, os 2 positivos de escavadeira foram falsos negativos;
- a probabilidade média do baseline para escavadeiras no teste foi 0,024 e o P90 foi 0,072.

Leitura auditada:

- a hipótese de maior impacto financeiro/cascata em escavadeiras é operacionalmente plausível, mas
  não é observável nos dados atuais porque não há custo, perda de produção ou consequência financeira
  por equipamento;
- a decisão baseada nos dados atuais é que há forte escassez de positivos `Is_Dont_Go` para
  escavadeiras, apesar de grande volume de telemetria;
- se escavadeiras forem priorizadas por custo, isso deve ser registrado como premissa externa ou
  alimentado por uma tabela real de custo/parada;
- com o target atual, o baseline praticamente não aprende sinal de escavadeira.

Alarmes associados aos erros:

- nos falsos negativos e falsos positivos de caminhões, aparecem recorrentemente alarmes como
  `OEM Interface`, `Dipper`, `Cycle`, `Body Up`, `Load`, `Payload Overload`, `Rx Channel` e
  `Tire Tag Timeout`;
- em escavadeiras, os candidatos ligados aos falsos negativos incluem `OEM Interface`,
  `TESTE OP ENTRADA ARTICULADA`, `Battery Voltage 19V`, `Bucket Angle At Or Above Level`,
  `Engine At High Throttle`, `Ladder Down`, `Lift Arms Too High` e limites de direção/hoist;
- a normalização textual encontrou candidatos com múltiplos `Id_Alarme`, mas eles ainda são
  candidatos de inspeção, não famílias aprovadas.

Decisão:

- repetir esta investigação depois de cada modelo relevante;
- construir `conceito_alarme` apenas para grupos sustentados por erros, positivos reais e semântica
  técnica plausível;
- não criar uma taxonomia ampla antes de testar se os candidatos melhoram validação/teste;
- não usar custo de escavadeira sem dado real ou premissa explicitamente separada das métricas.
- avaliar separação entre caminhões e escavadeiras como hipótese de arquitetura, mas ainda não treinar
  modelo pesado específico para escavadeiras com o target atual, pois o teste tem apenas 2 positivos
  de escavadeira e o semestre completo tem poucos episódios `Dont Go` nesse tipo;
- por enquanto, manter métricas e auditorias sempre segmentadas por tipo, testar interações
  `Tipo + conceito_alarme` e só separar modelos se houver target suficiente, target melhor ou ganho
  mensurável fora do agregado.

## 16. Modelo com conceitos de alarme

O notebook `07_Modelo_Com_Conceitos_De_Alarme.ipynb` testou uma primeira representação por conceito
sem criar taxonomia manual:

- `conceito_alarme_textual` foi derivado por normalização textual de `Alarme`;
- os 200 conceitos usados como features foram escolhidos por frequência apenas no treino;
- o teste não participou da seleção de conceitos, parâmetros ou threshold;
- a base, limpeza, target, split, sequência e janelas permaneceram congelados.

Resultados no teste:

| Modelo | PR-AUC | Precisão | Recall | F2 | Predições positivas | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RF IDs + conceitos | 0,346 | 0,205 | 0,834 | 0,518 | 1.178 | 242 | 936 | 48 | 1.889 |
| RF conceitos | 0,337 | 0,199 | 0,821 | 0,506 | 1.193 | 238 | 955 | 52 | 1.870 |
| RF IDs + conceitos + tipo | 0,344 | 0,221 | 0,738 | 0,503 | 968 | 214 | 754 | 76 | 2.071 |
| RF conceitos + tipo | 0,335 | 0,186 | 0,855 | 0,497 | 1.336 | 248 | 1.088 | 42 | 1.737 |
| RF IDs baseline | 0,330 | 0,210 | 0,752 | 0,496 | 1.038 | 218 | 820 | 72 | 2.005 |

Leitura auditada:

- conceitos textuais agregam sinal: `RF IDs + conceitos` superou o baseline em PR-AUC, recall e F2;
- o ganho veio com mais falsos positivos: 936 FP contra 820 no baseline;
- `RF conceitos` sozinho também superou o baseline em F2, indicando que a normalização reduz
  fragmentação útil dos alarmes;
- adicionar flags simples de tipo aumentou precisão no cenário `IDs + conceitos + tipo`, mas reduziu
  recall e F2 contra `IDs + conceitos`;
- em escavadeiras, nenhum cenário recuperou os 2 positivos do teste; modelos com conceitos chegaram
  a gerar 1 falso positivo, mas recall permaneceu 0;
- portanto, conceitos justificam uma próxima etapa de mapa manual pequeno, mas separação pesada de
  modelo para escavadeiras ainda não é sustentada pelo target atual.

Conceitos mais importantes nos modelos com conceitos incluíram:

- `ENGINE COOLANT LEVEL ACTIVE/INACTIVE`;
- `DIPPER`, `LOAD`, `BODY UP`, `CYCLE`;
- `OEM INTERFACE NORMAL/TIMEOUT`;
- `PAYLOAD OVERLOAD ACTIVE/INACTIVE`;
- `RX CHANNEL A/B NOT RECEIVING MESSAGES`;
- `PARKING BRAKE ACTIVE/INACTIVE`;
- `MA BAIXA VOLTAGEM COM EQUIP DESLIGADO 24V`;
- temperaturas de escape/freio e `TIRE TAG TIMEOUT`.

Decisão:

- avançar para um mapa manual pequeno e auditável de conceitos/famílias, começando pelos conceitos
  que tiveram importância, apareceram nos erros e têm semântica técnica clara;
- manter o baseline com IDs como referência, mas testar `IDs + conceitos manuais`;
- repetir a investigação de erros do notebook 06 após o modelo com mapa manual;
- não usar flags simples de tipo como solução para escavadeiras neste momento;
- não separar modelo de escavadeira enquanto o target atual continuar com pouquíssimos positivos.
- quando houver valores reais de parada, perda de produção, manutenção corretiva e manutenção
  preditiva, reavaliar a métrica de decisão: pode ser racional aceitar mais falsos positivos se o
  custo esperado de uma quebra evitada for suficientemente maior que o custo de inspeções ou
  intervenções preventivas adicionais;
- essa mudança deve ser feita por função de custo ou simulação econômica auditável, não por ajuste
  subjetivo de threshold.

## 17. Mapa manual inicial de conceitos

O notebook `08_Modelo_Com_Mapa_Manual_De_Conceitos.ipynb` testou um primeiro agrupamento manual
pequeno, com famílias como:

- `COMUNICACAO_INTERFACE`;
- `OPERACAO_CARGA_BASCULAMENTO`;
- `PNEUS_MONITORAMENTO`;
- `MOTOR_ARREFECIMENTO`;
- `FREIOS`;
- `TREM_FORCA`;
- `DIRECAO`;
- `ELETRICO`;
- `MOTOR_LUBRIFICACAO`;
- `OPERACAO_VELOCIDADE`.

Limite metodológico:

- este é um experimento de desenvolvimento;
- como o mapa foi orientado pelos erros já auditados, inclusive no teste de junho, seus resultados não
  devem ser tratados como validação final independente;
- para validação final, o mapa deve ser congelado e avaliado em novo período, novo holdout ou
  validação temporal posterior.

Resultados no teste:

| Modelo | PR-AUC | Precisão | Recall | F2 | Predições positivas | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RF IDs + conceitos textuais | 0,346 | 0,205 | 0,834 | 0,518 | 1.178 | 242 | 936 | 48 | 1.889 |
| RF IDs + famílias manuais | 0,333 | 0,215 | 0,762 | 0,505 | 1.027 | 221 | 806 | 69 | 2.019 |
| RF IDs + conceitos manuais | 0,337 | 0,198 | 0,821 | 0,503 | 1.205 | 238 | 967 | 52 | 1.858 |
| RF IDs + conceitos e famílias manuais | 0,329 | 0,209 | 0,759 | 0,497 | 1.053 | 220 | 833 | 70 | 1.992 |
| RF IDs baseline | 0,330 | 0,210 | 0,752 | 0,496 | 1.038 | 218 | 820 | 72 | 2.005 |

Leitura auditada:

- o modelo com conceitos textuais continua sendo o melhor em F2 e recall;
- famílias manuais reduziram falsos positivos contra o modelo textual: 806 FP contra 936 FP;
- famílias manuais mantiveram F2 acima do baseline: 0,505 contra 0,496;
- conceitos manuais preservaram recall alto, mas aumentaram falsos positivos para 967;
- combinar conceitos e famílias manuais quase empatou o baseline e não justificou complexidade;
- nenhum cenário manual recuperou positivos de escavadeira; o problema continua ligado à escassez de
  target nesse tipo.

Decisão:

- manter `RF IDs + conceitos textuais` como melhor referência técnica até agora;
- preservar o mapa manual como ferramenta de controle de falsos positivos e interpretabilidade;
- refinar famílias manuais apenas onde houver evidência de redução de FP sem perda excessiva de
  recall;
- antes de expandir o mapa manual, repetir a auditoria de erros comparando textual versus famílias
  manuais;
- não tratar o resultado do notebook 08 como validação final limpa, por ter sido orientado por
  análise pós-teste.

## 18. Testes de gaps e janelas temporais

O notebook `09_Teste_Gaps_E_Janelas_Temporais.ipynb` avaliou gaps de sequência com janela fixa 8h/8h
e depois avaliou janelas usando o melhor gap escolhido na validação.

### Gaps de sequência

Gaps testados: 30s, 60s, 120s, 300s, 900s e 3600s.

Efeito na formação de sequências:

| Gap | Sequências | Sequências Dont Go |
|---:|---:|---:|
| 30s | 8.712.278 | 16.845 |
| 60s | 4.303.625 | 14.612 |
| 120s | 3.154.960 | 12.290 |
| 300s | 2.519.198 | 9.847 |
| 900s | 979.994 | 7.572 |
| 3600s | 422.227 | 4.689 |

Resultados no teste, mantendo observação/horizonte 8h/8h:

| Gap | PR-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30s | 0,325 | 0,197 | 0,828 | 0,504 | 240 | 980 | 50 | 1.845 |
| 900s | 0,343 | 0,215 | 0,751 | 0,501 | 217 | 792 | 72 | 2.034 |
| 300s | 0,334 | 0,192 | 0,821 | 0,496 | 238 | 1.001 | 52 | 1.824 |
| 120s | 0,343 | 0,210 | 0,748 | 0,494 | 217 | 818 | 73 | 2.007 |
| 60s | 0,328 | 0,210 | 0,745 | 0,493 | 216 | 813 | 74 | 2.012 |
| 3600s | 0,272 | 0,179 | 0,772 | 0,465 | 213 | 974 | 63 | 1.865 |

Leitura:

- o gap de 900s foi escolhido pela validação e teve o melhor equilíbrio operacional no teste entre F2,
  precisão e falsos positivos;
- 30s teve maior F2 no teste, mas não foi escolhido pela validação e gera muito mais sequências e FP;
- 3600s degrada PR-AUC e F2, sugerindo agrupamento excessivo;
- o gap inicial de 60s não é mais a melhor referência temporal.

### Janelas de observação e horizonte

Usando gap de 900s, foram testadas janelas 4h/4h, 8h/8h, 12h/8h, 24h/8h e 24h/24h.

Resultados no teste:

| Observação | Horizonte | Positivas | PR-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24h | 24h | 571 | 0,509 | 0,306 | 0,940 | 0,665 | 537 | 1.218 | 34 | 1.186 |
| 24h | 8h | 285 | 0,348 | 0,205 | 0,821 | 0,512 | 234 | 910 | 51 | 1.850 |
| 8h | 8h | 289 | 0,343 | 0,215 | 0,751 | 0,501 | 217 | 792 | 72 | 2.034 |
| 12h | 8h | 291 | 0,329 | 0,193 | 0,832 | 0,500 | 242 | 1.012 | 49 | 1.777 |
| 4h | 4h | 193 | 0,327 | 0,242 | 0,503 | 0,413 | 97 | 304 | 96 | 2.653 |

Leitura:

- 24h/24h tem o maior F2, mas muda muito a natureza do target: prevalência sobe para 571 positivos no
  teste e o horizonte deixa de ser uma previsão operacional curta;
- 24h/8h melhora F2 contra 8h/8h mantendo o mesmo horizonte de ação de 8h, mas aumenta FP de 792 para
  910;
- 12h/8h aumenta recall, mas também aumenta FP e não melhora F2 contra 24h/8h;
- 4h/4h reduz FP, mas perde recall demais;
- a próxima referência temporal recomendada é gap 900s com observação 24h e horizonte 8h.

Decisão:

- substituir a referência temporal de desenvolvimento de 60s + 8h/8h por 900s + 24h/8h;
- manter 8h/8h como baseline histórico para comparação;
- não adotar 24h/24h como baseline principal neste momento, pois o horizonte de 24h altera o problema
  e aumenta muito o número de positivos;
- reavaliar `IDs + conceitos textuais` e famílias manuais usando gap 900s e janela 24h/8h.

## 19. Refino do gap com janela 24h/8h

O notebook `10_Refino_Gap_Sequencia_24h8h.ipynb` refinou a busca de gap mantendo observação 24h e
horizonte 8h.

Gaps testados: 450s, 600s, 750s, 900s, 1200s, 1500s, 1800s e 2400s.

Resultados por validação:

| Gap | PR-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 450s | 0,310 | 0,196 | 0,780 | 0,489 | 224 | 920 | 63 | 1.943 |
| 1500s | 0,300 | 0,182 | 0,843 | 0,488 | 242 | 1.090 | 45 | 1.773 |
| 600s | 0,306 | 0,194 | 0,777 | 0,485 | 223 | 928 | 64 | 1.935 |
| 1200s | 0,293 | 0,184 | 0,787 | 0,475 | 226 | 1.005 | 61 | 1.858 |
| 1800s | 0,288 | 0,184 | 0,776 | 0,473 | 222 | 982 | 64 | 1.882 |
| 900s | 0,287 | 0,194 | 0,735 | 0,471 | 211 | 879 | 76 | 1.984 |
| 750s | 0,289 | 0,178 | 0,801 | 0,471 | 230 | 1.063 | 57 | 1.800 |
| 2400s | 0,265 | 0,159 | 0,879 | 0,461 | 247 | 1.310 | 34 | 1.559 |

Resultados no teste:

| Gap | PR-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 600s | 0,334 | 0,200 | 0,853 | 0,516 | 244 | 977 | 42 | 1.782 |
| 900s | 0,348 | 0,205 | 0,821 | 0,512 | 234 | 910 | 51 | 1.850 |
| 1200s | 0,340 | 0,195 | 0,856 | 0,510 | 244 | 1.007 | 41 | 1.753 |
| 1500s | 0,328 | 0,186 | 0,879 | 0,503 | 248 | 1.087 | 34 | 1.676 |
| 1800s | 0,328 | 0,195 | 0,826 | 0,502 | 233 | 960 | 49 | 1.803 |
| 450s | 0,335 | 0,194 | 0,829 | 0,501 | 237 | 986 | 49 | 1.773 |
| 750s | 0,346 | 0,182 | 0,874 | 0,496 | 250 | 1.124 | 36 | 1.635 |
| 2400s | 0,305 | 0,166 | 0,906 | 0,479 | 250 | 1.258 | 26 | 1.511 |

Leitura auditada:

- pela regra pré-definida, o gap escolhido formalmente é 450s, pois foi o melhor em F2 na validação;
- no teste, 600s, 900s e 1200s superaram 450s em F2;
- 900s manteve o melhor PR-AUC no teste e o menor FP entre os gaps competitivos de 450s a 1200s;
- 600s teve melhor F2 no teste, mas não foi o melhor na validação;
- 1500s, 1800s e 2400s aumentam recall, mas tendem a elevar FP ou degradar PR-AUC;
- a faixa 600s-1200s é a região útil mais provável; 900s continua sendo uma escolha conservadora por
  equilíbrio entre PR-AUC, FP e estabilidade com o notebook 09.

Decisão:

- não trocar automaticamente para 600s apenas porque foi melhor no teste, para evitar ajuste ao teste;
- manter 900s como referência operacional conservadora para a próxima rodada com conceitos textuais,
  mas registrar 450s como vencedor formal por validação neste refino;
- quando houver validação temporal adicional, retestar a faixa 450s-1200s;
- próxima etapa: reavaliar `IDs + conceitos textuais` e famílias manuais com janela 24h/8h,
  priorizando gap 900s e reportando sensibilidade para 450s/600s se o custo computacional permitir.

## 20. Conceitos e famílias com 24h/8h

O notebook `11_Conceitos_Familias_24h8h_Sensibilidade_Gap.ipynb` reavaliou as representações de
alarme com janela 24h/8h:

- gap principal: 900s;
- sensibilidade: 450s e 600s;
- modelos: `RF_ids`, `RF_ids_textual`, `RF_ids_manual_family` e
  `RF_ids_textual_manual_family`;
- features de 24h calculadas pela soma dos três buckets de 8h anteriores à previsão, para viabilizar
  a comparação com muitas features.

Resultados no gap principal 900s, teste:

| Modelo | PR-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RF IDs + conceitos textuais | 0,333 | 0,230 | 0,789 | 0,531 | 225 | 753 | 60 | 2.007 |
| RF IDs + conceitos textuais + famílias | 0,340 | 0,200 | 0,849 | 0,514 | 242 | 971 | 43 | 1.789 |
| RF IDs + famílias manuais | 0,352 | 0,192 | 0,842 | 0,501 | 240 | 1.013 | 45 | 1.747 |
| RF IDs | 0,336 | 0,182 | 0,828 | 0,485 | 236 | 1.059 | 49 | 1.701 |

Sensibilidade por gap, melhor modelo de cada gap no teste:

| Gap | Melhor modelo | PR-AUC | Precisão | Recall | F2 | FP | FN |
|---:|---|---:|---:|---:|---:|---:|---:|
| 450s | RF IDs + conceitos textuais | 0,332 | 0,221 | 0,780 | 0,517 | 788 | 63 |
| 600s | RF IDs | 0,332 | 0,208 | 0,832 | 0,521 | 904 | 48 |
| 900s | RF IDs + conceitos textuais | 0,333 | 0,230 | 0,789 | 0,531 | 753 | 60 |

Leitura auditada:

- no gap principal 900s, `RF IDs + conceitos textuais` é a melhor referência atual por F2 e reduz FP
  de 1.059 para 753 contra `RF IDs`;
- famílias manuais aumentam recall, mas elevam FP e reduzem precisão;
- `RF IDs + conceitos textuais + famílias` recupera mais positivos que `RF IDs + conceitos textuais`,
  porém adiciona 218 FP e perde F2;
- na sensibilidade, 600s teve melhor F2 com `RF_ids`, mas isso não deve substituir automaticamente a
  referência, pois a escolha por teste isolado introduziria ajuste ao teste;
- 900s + 24h/8h + conceitos textuais é a configuração de desenvolvimento mais forte até agora.

Decisão:

- adotar `gap=900s`, observação 24h, horizonte 8h e `IDs + conceitos textuais` como nova referência
  técnica;
- manter 450s e 600s apenas como sensibilidade documentada;
- usar famílias manuais como ferramenta de análise/interpretabilidade, não como feature principal
  nesta etapa;
- repetir a auditoria de FP/FN para a nova referência `900s + 24h/8h + conceitos textuais`.

## 21. Auditoria da nova referência 24h/8h

O notebook `12_Auditoria_Nova_Referencia_24h8h.ipynb` comparou a nova referência técnica contra o
baseline histórico:

- baseline histórico: `gap=60s`, observação 8h, horizonte 8h, `IDs`;
- nova referência: `gap=900s`, observação 24h, horizonte 8h, `IDs + conceitos textuais`;
- os thresholds foram escolhidos na validação, sem ajuste pelo teste;
- a auditoria foi segmentada por tipo de equipamento, `TAG`, faixas de probabilidade, falsos
  positivos e falsos negativos.

Resultado global no teste:

| Modelo | PR-AUC | ROC-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 60s 8h/8h IDs | 0,328 | 0,807 | 0,210 | 0,745 | 0,493 | 216 | 813 | 74 | 2.012 |
| Referência 900s 24h/8h IDs + conceitos | 0,333 | 0,821 | 0,227 | 0,730 | 0,505 | 208 | 710 | 77 | 2.050 |

Delta da nova referência contra o baseline:

| Métrica | Delta |
|---|---:|
| PR-AUC | +0,005 |
| Precisão | +0,017 |
| Recall | -0,015 |
| F2 | +0,012 |
| TP | -8 |
| FP | -103 |
| FN | +3 |
| TN | +38 |

Leitura auditada:

- a nova referência reduziu 103 falsos positivos e elevou precisão, PR-AUC, ROC-AUC e F2;
- a troca não é gratuita: houve perda de 8 verdadeiros positivos e aumento de 3 falsos negativos;
- como ainda não existe função econômica validada, a escolha da referência atual privilegia redução de
  alarm fatigue e melhor equilíbrio F2, sem afirmar que este é o threshold final de produção;
- quando forem incorporados custos reais de parada, manutenção e perda de produção, o threshold pode
  ser deslocado para mais recall, aceitando mais falsos positivos se o custo esperado justificar.

Segmentação por tipo de equipamento no teste:

| Modelo | Tipo | Amostras | Positivos reais | Predições positivas | TP | FP | FN | TN | Precisão | Recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | Caminhao | 2.670 | 288 | 1.029 | 216 | 813 | 72 | 1.569 | 0,210 | 0,750 |
| Baseline | Escavadeira | 445 | 2 | 0 | 0 | 0 | 2 | 443 | 0,000 | 0,000 |
| Referência | Caminhao | 2.610 | 283 | 918 | 208 | 710 | 75 | 1.617 | 0,227 | 0,735 |
| Referência | Escavadeira | 435 | 2 | 0 | 0 | 0 | 2 | 433 | 0,000 | 0,000 |

Conclusão sobre escavadeiras:

- os dois modelos tiveram recall zero para escavadeiras no teste;
- a nova referência não resolveu o problema de escavadeiras, porque há apenas 2 positivos reais no
  teste e nenhum caso foi previsto como positivo;
- os falsos negativos de menor probabilidade da nova referência incluem `PE3795` com probabilidade
  0,000 em 27/06/2025 e `PE3797` com probabilidade 0,008 em 02/06/2025;
- separar escavadeiras em modelo próprio continua prematuro com este target, mas a investigação deve
  permanecer aberta por causa do impacto operacional em cascata e do custo potencialmente maior.

Tags com mais falsos negativos na nova referência:

| TAG | FN |
|---|---:|
| CA65937 | 8 |
| CA65936 | 7 |
| CA65935 | 6 |
| CA65933 | 5 |
| CA65927 | 4 |
| CA5927 | 4 |
| CA65932 | 4 |
| CA65915 | 4 |
| CA65930 | 4 |
| CA65931 | 4 |

Tags com mais falsos positivos na nova referência:

| TAG | FP |
|---|---:|
| CA65792 | 70 |
| CA5927 | 57 |
| CA65927 | 41 |
| CA65936 | 35 |
| CA65924 | 35 |
| CA65932 | 35 |
| CA65929 | 34 |
| CA65933 | 33 |
| CA65921 | 33 |
| CA65926 | 32 |

Decisão:

- manter `gap=900s`, observação 24h, horizonte 8h e `IDs + conceitos textuais` como referência de
  desenvolvimento para a próxima fase;
- não considerar a questão de escavadeiras resolvida;
- priorizar agora testes mais amplos de entendimento de sequência e janelas multiescala, usando a
  nova referência como base comparativa;
- preservar o baseline 60s 8h/8h como referência histórica de comparação.

## 22. Teste de multijanelas temporais

O notebook `13_Teste_Multijanelas_Temporais.ipynb` avaliou se a forma de representar as 24h anteriores
melhora a referência técnica atual. Foram mantidos fixos:

- `gap=900s`;
- observação total 24h;
- horizonte 8h;
- target provisório por episódio futuro `Is_Dont_Go`;
- split temporal;
- Random Forest;
- seleção de threshold somente na validação.

Cenários testados:

| Cenário | Descrição | Features |
|---|---|---:|
| `referencia_24h_ids_textual` | IDs + conceitos textuais agregados em 24h | 416 |
| `multijanela_core_ids_textual` | buckets 0-8h, 8-16h e 16-24h para features gerais; IDs/conceitos agregados | 441 |
| `multijanela_ids_textual_buckets` | buckets para features gerais, IDs e conceitos | 1.241 |
| `multijanela_hibrida` | buckets gerais + IDs/conceitos agregados + conceitos por bucket | 1.041 |

Resultado no teste:

| Cenário | PR-AUC | ROC-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Multijanela core | 0,363 | 0,830 | 0,188 | 0,877 | 0,506 | 250 | 1.082 | 35 | 1.678 |
| Multijanela híbrida | 0,372 | 0,836 | 0,186 | 0,884 | 0,506 | 252 | 1.100 | 33 | 1.660 |
| Referência agregada 24h | 0,333 | 0,821 | 0,227 | 0,730 | 0,505 | 208 | 710 | 77 | 2.050 |
| Multijanela IDs/conceitos por bucket | 0,372 | 0,827 | 0,184 | 0,849 | 0,492 | 242 | 1.075 | 43 | 1.685 |

Resultado na validação:

| Cenário | PR-AUC | ROC-AUC | Precisão | Recall | F2 | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Multijanela core | 0,322 | 0,804 | 0,181 | 0,854 | 0,489 | 245 | 1.110 | 42 | 1.753 |
| Multijanela IDs/conceitos por bucket | 0,328 | 0,804 | 0,178 | 0,861 | 0,488 | 247 | 1.137 | 40 | 1.726 |
| Multijanela híbrida | 0,323 | 0,805 | 0,174 | 0,868 | 0,483 | 249 | 1.178 | 38 | 1.685 |
| Referência agregada 24h | 0,291 | 0,790 | 0,210 | 0,700 | 0,478 | 201 | 755 | 86 | 2.108 |

Delta da multijanela core contra a referência agregada no teste:

| Métrica | Delta |
|---|---:|
| PR-AUC | +0,030 |
| Precisão | -0,039 |
| Recall | +0,147 |
| F2 | +0,000 |
| TP | +42 |
| FP | +372 |
| FN | -42 |
| TN | -372 |

Leitura auditada:

- multijanelas capturam sinal real de recência, pois melhoram PR-AUC, ROC-AUC e recall na validação e
  no teste;
- o ganho operacional bruto é recuperar 42 a 44 positivos no teste, reduzindo FN de 77 para 35/33;
- o custo é alto em falsos positivos: a multijanela core adiciona 372 FP e a híbrida adiciona 390 FP;
- o F2 fica praticamente empatado com a referência agregada, portanto não há ganho robusto suficiente
  para substituir automaticamente a referência atual;
- a versão completa com IDs e conceitos por bucket tem mais features, pior F2 no teste e não justifica
  a complexidade nesta etapa;
- a multijanela core é o candidato mais interessante se a futura função econômica priorizar recall e
  aceitar mais inspeções/intervenções.

Segmentação por tipo no teste:

| Cenário | Tipo | TP | FP | FN | TN | Precisão | Recall | Taxa FP |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Multijanela core | Caminhao | 250 | 1.080 | 33 | 1.247 | 0,188 | 0,883 | 0,464 |
| Multijanela core | Escavadeira | 0 | 2 | 2 | 431 | 0,000 | 0,000 | 0,005 |
| Referência agregada 24h | Caminhao | 208 | 710 | 75 | 1.617 | 0,227 | 0,735 | 0,305 |
| Referência agregada 24h | Escavadeira | 0 | 0 | 2 | 433 | 0,000 | 0,000 | 0,000 |

Escavadeiras:

- seguem com recall zero;
- multijanelas geraram 2 falsos positivos em escavadeiras, mas não recuperaram os 2 positivos reais;
- os dois falsos negativos de menor probabilidade no melhor cenário continuam sendo `PE3797` e
  `PE3795`, ambos com probabilidade 0,000;
- a conclusão anterior permanece: o problema de escavadeiras não será resolvido apenas por
  multijanelas com o target atual.

Aviso de execução:

- o notebook gerou `PerformanceWarning` na criação de colunas derivadas por fragmentação de
  `DataFrame`;
- o aviso não representa erro de cálculo nem falha de execução;
- pode ser otimizado futuramente com `pd.concat(axis=1)` se o custo de execução passar a incomodar.

Decisão:

- manter a referência agregada `900s + 24h/8h + IDs + conceitos textuais` como baseline técnico
  principal por enquanto, pois entrega precisão maior e muito menos FP;
- registrar `multijanela_core_ids_textual` como candidato orientado a recall para a fase com função de
  custo;
- não adotar as versões com IDs/conceitos por bucket como referência neste momento por complexidade
  maior e ganho insuficiente;
- próxima etapa recomendada: testar controle explícito de threshold/curva de decisão entre a
  referência agregada e a multijanela core, antes de trocar algoritmo.

## 23. Próximos passos acordados

Ordem recomendada:

1. testar controle explícito de threshold/curva de decisão para referência agregada e multijanela
   core;
2. verificar especialmente escavadeiras, tags com FP alto e falsos negativos de baixa probabilidade;
3. comparar XGBoost/LightGBM após consolidar a escolha de representação e threshold;
4. retomar estados operacionais depois dos testes temporais multiescala;
5. procurar um target ligado a consequência operacional observável;
6. somente depois discutir produção, downtime ou ROI.

Decisão de ordem:

- pausar o refinamento manual de famílias neste momento;
- priorizar gaps de sequência e janelas porque a cadência dos alarmes é heterogênea e o limite atual
  de 60 segundos ainda é premissa inicial, não parâmetro validado;
- evitar superajustar taxonomia ao teste de junho antes de entender se FP/FN vêm de agrupamento
  temporal inadequado;
- depois de escolher desenhos temporais promissores, reavaliar conceitos textuais e famílias manuais
  sobre essa nova base.

## 24. Regras para futuras sessões

Antes de trabalhar:

1. ler este documento;
2. executar `git status --short --branch`;
3. verificar se notebooks e geradores estão sincronizados;
4. não editar arquivos brutos;
5. não usar split aleatório;
6. não selecionar features consultando validação ou teste;
7. não interpretar `Is_Dont_Go` como falha confirmada;
8. não excluir anomalias sem regra localizada e contagem antes/depois;
9. registrar novas decisões neste documento;
10. executar integralmente qualquer notebook alterado e verificar saídas de erro.

## 25. Estado local após multijanelas temporais

Arquivos criados após o commit `807a50d` e ainda não commitados:

```text
notebooks/04_Auditoria_Do_Baseline_8h.ipynb
scripts/create_baseline_audit_notebook.py
notebooks/05_Cenarios_Estados_Hibernando.ipynb
scripts/create_state_scenarios_notebook.py
notebooks/06_Investigacao_Erros_E_Familias.ipynb
scripts/create_error_investigation_notebook.py
notebooks/07_Modelo_Com_Conceitos_De_Alarme.ipynb
scripts/create_concept_model_notebook.py
notebooks/08_Modelo_Com_Mapa_Manual_De_Conceitos.ipynb
scripts/create_manual_concept_model_notebook.py
notebooks/09_Teste_Gaps_E_Janelas_Temporais.ipynb
scripts/create_temporal_grid_notebook.py
notebooks/10_Refino_Gap_Sequencia_24h8h.ipynb
scripts/create_gap_refinement_notebook.py
notebooks/11_Conceitos_Familias_24h8h_Sensibilidade_Gap.ipynb
scripts/create_temporal_concept_sensitivity_notebook.py
notebooks/12_Auditoria_Nova_Referencia_24h8h.ipynb
scripts/create_new_reference_error_audit_notebook.py
notebooks/13_Teste_Multijanelas_Temporais.ipynb
scripts/create_multwindow_temporal_notebook.py
docs/RELATORIO_DECISOES_PROJETO.md
docs/CONTINUIDADE_PROJETO.md
```

Os notebooks 04, 05, 06, 07, 08, 09, 10, 11, 12 e 13 e seus geradores devem ser commitados após
revisão dos achados.

O notebook 12 foi executado sem erros e confirmou que a nova referência reduz falsos positivos e
melhora F2/precisão contra o baseline histórico, mas ainda não aprende escavadeiras.

O notebook 13 foi executado. A multijanela core recupera mais positivos e melhora PR-AUC/recall, mas
adiciona muitos falsos positivos e empata em F2 com a referência agregada. A decisão atual é manter a
referência agregada como baseline técnico principal e preservar multijanela core como candidato para
cenário orientado a recall/custo.
