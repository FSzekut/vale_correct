# Premissas Econômicas Externas

Última atualização: 2 de julho de 2026.

Este documento registra as premissas econômicas externas usadas no notebook
`14_Threshold_Curva_Decisao_Custo.ipynb` e nos notebooks posteriores de valoração econômica.

## 1. Regra de auditoria

Nenhum valor abaixo é dado observado do projeto Vale Correct.

Uso permitido:

- análise de sensibilidade;
- comparação de thresholds sob cenários explícitos;
- documentação de hipóteses a validar com a operação.

Uso proibido:

- apresentar como ROI real;
- afirmar economia observada;
- afirmar custo real da Vale;
- substituir dados de manutenção, parada, produção ou custo aprovados pela operação.

Pesquisa complementar em 02/07/2026:

- não foi encontrada fonte pública confiável com custo real da Vale por hora de caminhão 793-D parado;
- não foi encontrada fonte pública confiável com custo real da Vale por hora de escavadeira
  `LeTourneau L 1850` parada;
- as fontes públicas sustentam apenas ordem de grandeza de preço do minério, custo caixa, capacidade
  de caminhões, papel operacional de carregadeiras/escavadeiras e custos aproximados de componentes;
- portanto, os valores continuam sendo cenários simulados e devem ser substituídos por dados internos
  de manutenção, despacho, produção e custos.

## 2. Fontes externas usadas

### Preço do minério de ferro

Fonte: World Bank Commodities Price Data, Pink Sheet, junho de 2026.

Valores relevantes:

- minério de ferro, 62% Fe, spot c.f.r. China;
- média 2025: US$ 100,2/dmt;
- maio de 2026: US$ 108,6/dmt.

Uso no cenário base:

- `preco_minerio_usd_t = 100`.

Justificativa:

- arredondamento conservador próximo da média de 2025;
- evita calibrar o cenário por um mês específico.

URL:

- <https://www.worldbank.org/en/research/commodity-markets>
- <https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Pink-Sheet-June-2026.pdf>

### Custo caixa / custo por tonelada

Fonte pública usada como aproximação: reportagem do Financial Times sobre guidance da Vale para 2026.

Valor reportado:

- guidance de custo de produção de minério de ferro da Vale para 2026: US$ 20 a US$ 21,5/t.

Uso no cenário base:

- `custo_caixa_usd_t = 21`.

Limite:

- fonte jornalística, não planilha operacional interna;
- precisa ser substituída por dado interno ou release oficial se disponível.

URL:

- <https://www.ft.com/content/e76c68c2-cfe3-441c-86f6-8035eda68e51>

### Equipamentos do projeto

Fonte interna do projeto:

- telemetria bruta em `data/raw/Base/datasets/telemetria/telemetry_*.parquet`.

Valores observados no projeto:

| Tipo | Frota | TAGs | Registros | Linhas Is_Dont_Go |
|---|---|---:|---:|---:|
| Caminhao | 793-D 2S/3S/4S/5S | 30 | 3.281.763 | 19.795 |
| Escavadeira | LeTourneau L 1850 | 5 | 33.882.291 | 167 |

Limite:

- o dado identifica frota/tipo, mas não traz payload, produtividade, ciclo de transporte,
  custo de manutenção nem custo de parada.

### Capacidade e ordem de grandeza de caminhões de mineração

Fonte oficial Caterpillar para caminhão de mineração 793:

- payload nominal: 265 short tons / 240 t;
- peso bruto: 890.668 lb / 404.000 kg;
- potência bruta: 2.650 hp / 1.976 kW;
- a página usa chamada de `Request A Price` e informa que preço/MSRP ou dealer price é informativo,
  pode variar por dealer e depende dos termos finais de venda.

Uso:

- referência oficial mais próxima da frota `793-D` observada no projeto;
- confirma escala produtiva do equipamento;
- não fornece custo em US$/h, custo de manutenção, custo de peça, custo de parada ou preço final
  auditável.

URL:

- <https://www.cat.com/en_US/products/new/equipment/off-highway-trucks/mining-trucks/116620.html>

Fonte oficial Caterpillar para caminhão de mineração 797F:

- payload nominal: 363 t;
- peso bruto: 623.690 kg.

Uso:

- referência de ordem de grandeza para caminhões de grande mineração;
- não é o mesmo modelo da frota `793-D` do projeto.
- a página traz benefícios relativos, como menor custo operacional e menor custo de manutenção, mas
  não publica valores em US$/h ou US$/evento.

URL:

- <https://www.cat.com/en_US/products/new/equipment/off-highway-trucks/mining-trucks/18093014.html>

Fonte secundária para Caterpillar 797:

- payload de 360 a 400 short tons;
- custo aproximado de pneu em 2009: US$ 42.500;
- custo aproximado do caminhão: US$ 5 milhões.

Uso:

- ordem de grandeza para custo de componentes e severidade de manutenção corretiva;
- não é valor auditado da frota `793-D`.

URL:

- <https://en.wikipedia.org/wiki/Caterpillar_797>

Fonte secundária para Caterpillar 789:

- pneu citado em cerca de US$ 50.000;
- capacidade de 177 t.

Uso:

- ordem de grandeza de pneus de caminhões fora de estrada;
- não é valor auditado da frota `793-D`.

URL:

- <https://en.wikipedia.org/wiki/Caterpillar_789>

### Escavadeiras / carregadeiras de grande porte

Fonte secundária disponível publicamente para LeTourneau/P&H L-2350:

- loader de mineração de superfície;
- projetado para carregar caminhões de até 400 short tons;
- payload operacional de 80 short tons.

Uso:

- referência de papel operacional: uma carregadeira/escavadeira alimenta vários caminhões;
- não é o mesmo modelo `LeTourneau L 1850`, portanto a premissa de escavadeira recebe menor
  confiança.

URL:

- <https://en.wikipedia.org/wiki/LeTourneau_L-2350>

### Estrutura econômica de manutenção preditiva

Fonte acadêmica:

- `Cost-Sensitive Learning for Predictive Maintenance`;
- mostra que selecionar modelo por F1/F2 pode não minimizar custo e que o modelo deve incorporar
  custos de negócio.

Uso:

- justificativa metodológica para otimizar threshold por custo;
- não fornece custos específicos de mineração.

URL:

- <https://arxiv.org/abs/1809.10979>

### Evidência pública sobre manutenção preditiva

Fontes gerais sobre manutenção preditiva indicam a lógica econômica usada aqui:

- transformar paradas não planejadas em intervenções planejadas;
- reduzir custo de indisponibilidade não planejada;
- selecionar modelo por custo de negócio, não apenas por F1/F2.

Limite:

- essas fontes não fornecem custos específicos de mineração de ferro da Vale;
- servem apenas para justificar a estrutura da função de custo.

URLs:

- <https://en.wikipedia.org/wiki/Predictive_maintenance>
- <https://arxiv.org/abs/1809.10979>

## 3. Premissas base adotadas

Moeda: US$.

### Margem operacional por tonelada

Fórmula:

```text
margem_usd_t = preco_minerio_usd_t - custo_caixa_usd_t
```

Valores:

```text
100 - 21 = 79 US$/t
```

Limite:

- usa preço de referência e custo caixa aproximado;
- não inclui prêmio/desconto por qualidade, frete, mistura, estoque, contrato, impostos,
  gargalos downstream ou custo de oportunidade específico.

### Derivação do impacto operacional por hora

O impacto por hora foi estimado pela margem por tonelada e pela capacidade produtiva plausível dos
equipamentos, não por dado interno da Vale.

#### Caminhão 793-D

Dados externos:

- payload oficial do Cat 793: 240 t;
- margem base adotada: 79 US$/t.

Faixa ilustrativa por ciclo efetivo:

| Ciclo efetivo | Toneladas/h | Margem/h |
|---:|---:|---:|
| 75 min | 192 | 15.168 |
| 60 min | 240 | 18.960 |
| 45 min | 320 | 25.280 |

Uso atual:

- `impacto_operacional_hora = 30.000` para caminhões.

Interpretação:

- o valor é uma premissa de cenário base-alto, próxima da ordem de grandeza obtida com payload do 793
  e margem/t;
- pode representar, além da carga direta perdida, alguma ineficiência de fila, deslocamento ou
  rearranjo operacional;
- para sensibilidade, usar faixa aproximada de `15.000` a `45.000` US$/h.

#### Escavadeira / carregadeira

Dados internos e externos:

- o projeto contém 30 caminhões e 5 escavadeiras, razão operacional média de 6 caminhões por
  escavadeira;
- fonte pública sobre carregadeira LeTourneau/P&H L-2350 indica papel operacional de carregar
  caminhões de grande porte, inclusive até 400 short tons;
- não foi encontrada fonte pública específica confiável para produtividade da `LeTourneau L 1850`.

Derivação por efeito cascata:

| Caminhões afetados equivalentes | Impacto por caminhão/h | Impacto/h |
|---:|---:|---:|
| 4 | 15.000 | 60.000 |
| 5 | 20.000 | 100.000 |
| 6 | 25.000 | 150.000 |

Uso atual:

- `impacto_operacional_hora = 100.000` para escavadeiras.

Interpretação:

- o valor representa efeito cascata parcial, não parada total da mina;
- a base de 100.000 US$/h é compatível com uma escavadeira impactando vários caminhões;
- para sensibilidade, usar faixa aproximada de `60.000` a `150.000` US$/h;
- confiança continua baixa sem despacho real, frente de lavra, equipamentos reserva e produção
  horária por escavadeira.

### Caminhão 793-D

Premissas:

| Campo | Valor base | Base |
|---|---:|---|
| `custo_intervencao_preditiva` | 10.000 | inspeção + pequena intervenção planejada; estimativa externa |
| `custo_manutencao_corretiva` | 50.000 | ordem de grandeza de pneu/componente de caminhão fora de estrada |
| `impacto_operacional_hora` | 30.000 | estimado por margem/t e perda parcial de capacidade de transporte |
| `horas_parada_preditiva` | 1 | janela curta planejada |
| `horas_parada_corretiva` | 4 | troca/reparo corretivo de curta duração |

Interpretação:

- representa parada de um caminhão em frota com redundância parcial;
- não assume parada total da mina;
- deve ser validado por despacho, produção horária e histórico de OS.
- a duração de manutenção preditiva de 1h é coerente com a mediana observada dos apontamentos
  `Manutenção` no projeto;
- a duração corretiva de 4h é uma premissa simulada de reparo curto/médio, não dado observado.

### Escavadeira / LeTourneau L 1850

Premissas:

| Campo | Valor base | Base |
|---|---:|---|
| `custo_intervencao_preditiva` | 25.000 | intervenção planejada mais cara e crítica que caminhão |
| `custo_manutencao_corretiva` | 150.000 | ordem de grandeza de componente/serviço crítico de carregadeira grande |
| `impacto_operacional_hora` | 100.000 | gargalo operacional alimentando múltiplos caminhões |
| `horas_parada_preditiva` | 2 | janela planejada maior |
| `horas_parada_corretiva` | 8 | corretiva crítica de curta/média duração |

Interpretação:

- representa equipamento com efeito cascata;
- não assume que toda mina para;
- valor tem menor confiança por falta de fonte pública específica para `L 1850`.
- a duração preditiva de 2h é uma premissa conservadora acima da mediana observada de manutenção;
- a duração corretiva de 8h é uma premissa simulada de corretiva crítica curta/média, não dado
  observado.

### Cenários recomendados para valoração dos modelos

Para evitar que a decisão dependa de um único conjunto de valores, usar ao menos três cenários:

| Tipo | Cenário | p ação confirmada | Intervenção preditiva | Manutenção corretiva | Impacto/h | Parada preditiva | Parada corretiva |
|---|---|---:|---:|---:|---:|---:|---:|
| Caminhão | Conservador | 0,40 | 15.000 | 40.000 | 15.000 | 1h | 3h |
| Caminhão | Base | 0,655 | 10.000 | 50.000 | 30.000 | 1h | 4h |
| Caminhão | Agressivo | 0,75 | 10.000 | 80.000 | 45.000 | 1h | 6h |
| Escavadeira | Conservador | 0,20 | 35.000 | 100.000 | 60.000 | 2h | 6h |
| Escavadeira | Base | 0,20 | 25.000 | 150.000 | 100.000 | 2h | 8h |
| Escavadeira | Agressivo | 0,40 | 25.000 | 250.000 | 150.000 | 2h | 12h |

Notas:

- para caminhões, `p_acao_confirmada = 0,655` vem do treino, usando a associação observada
  `Dont Go -> Manutenção em 8h`;
- para escavadeiras, `p_acao_confirmada` permanece premissa fraca porque há poucos episódios
  `Is_Dont_Go`;
- os cenários de escavadeira servem para mostrar sensibilidade do potencial econômico, não para
  recomendar operação com o target atual.

### Taxa de conversão do target

Campo:

```text
p_acao_confirmada
```

Valor base:

```text
0,20
```

Status:

- originalmente era uma premissa externa fraca;
- após o notebook `15_Validacao_Operacional_Target.ipynb`, há uma estimativa observada para
  caminhões usando a ligação `Dont Go -> Manutenção em 8h`;
- continua não provando causalidade, pois `Manutenção` é proxy operacional.

Estimativa observada para caminhões:

| Split | Episódios DG | Com Manutenção em 8h | Taxa |
|---|---:|---:|---:|
| Treino | 6.030 | 3.951 | 0,655 |
| Validação | 689 | 543 | 0,788 |
| Teste | 811 | 609 | 0,751 |

Uso recomendado:

- para evitar vazamento, usar `0,655` como premissa-base derivada do treino;
- usar `0,788` e `0,751` apenas como evidência de estabilidade em validação/teste;
- manter sensibilidade ampla porque `Is_Dont_Go` não é falha confirmada e manutenção não prova causa.

Escavadeiras:

- não usar uma taxa base confiável ainda;
- há poucos episódios `Is_Dont_Go`, então a estimativa é instável;
- manter valor conservador ou cenário separado até haver target operacional mais forte.

Faixa recomendada:

```text
0,20; 0,40; 0,655; 0,75
```

## 4. Nível de confiança

| Bloco | Confiança | Motivo |
|---|---|---|
| Preço do minério | Alta | fonte oficial World Bank |
| Custo caixa aproximado | Média | fonte pública jornalística; precisa de release oficial ou dado interno |
| Frota observada | Alta | vem dos dados locais do projeto |
| Payload de caminhões | Média | fonte oficial Caterpillar para 793 atual; frota local é `793-D` |
| Custo de manutenção de caminhões | Baixa | Caterpillar não publicou US$/h ou US$/evento nas páginas consultadas; valor segue estimado por ordem de grandeza |
| Escavadeira L 1850 | Baixa | fonte pública específica não encontrada; extrapolação por papel operacional |
| `p_acao_confirmada` caminhões | Média | estimada por associação observada `Dont Go -> Manutenção em 8h`, sem causalidade |
| `p_acao_confirmada` escavadeiras | Baixa | poucos episódios `Is_Dont_Go`; precisa de mais dados ou target próprio |
| Impacto/h caminhões | Baixa-média | derivado de payload público do Cat 793 e margem/t; falta ciclo real e despacho |
| Impacto/h escavadeiras | Baixa | derivado por efeito cascata caminhões/escavadeira; falta produção por frente |
| Duração manutenção preditiva | Média | mediana observada de manutenção apoia 1h para caminhões; escavadeira usa premissa conservadora |
| Duração manutenção corretiva | Baixa | não observada; deve vir de ordens de serviço ou apontamento de parada corretiva |

## 5. Próxima validação necessária

Para transformar cenário em ROI auditável, obter:

1. ordens de serviço ligadas aos alarmes;
2. tempo real de parada por evento;
3. custo real de peças, mão de obra e terceiros;
4. produção horária por equipamento ou frente;
5. presença de equipamento reserva ou gargalo;
6. taxa real de conversão de `Is_Dont_Go` em intervenção acionável.
