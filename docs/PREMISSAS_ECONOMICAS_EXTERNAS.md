# Premissas Econômicas Externas

Última atualização: 29 de junho de 2026.

Este documento registra as premissas econômicas externas usadas no notebook
`14_Threshold_Curva_Decisao_Custo.ipynb`.

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

## 5. Próxima validação necessária

Para transformar cenário em ROI auditável, obter:

1. ordens de serviço ligadas aos alarmes;
2. tempo real de parada por evento;
3. custo real de peças, mão de obra e terceiros;
4. produção horária por equipamento ou frente;
5. presença de equipamento reserva ou gargalo;
6. taxa real de conversão de `Is_Dont_Go` em intervenção acionável.
