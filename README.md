# Vale Correct

Projeto de analise avancada de telemetria para antecipacao de eventos criticos em equipamentos de
mina, com foco em auditoria dos dados, construcao de target temporal, comparacao de modelos e
valoracao economica de alertas preditivos.

## Visao Geral

O projeto trabalha com dados de operacao de mina, incluindo telemetria de veiculos, alarmes por
equipamento e apontamentos operacionais. O objetivo e avaliar se existe sinal temporal suficiente
para antecipar novos episodios associados a `Is_Dont_Go`, respeitando a ordem do tempo e separando
evidencias observadas de premissas externas.

Principio central:

- os dados brutos nao sao alterados;
- anomalias nao sao tratadas como erro sem evidencia;
- exclusoes ocorrem somente em camadas analiticas derivadas;
- toda decisao relevante possui contagem, regra e justificativa;
- custos e impactos economicos sao simulacoes de cenario ate validacao por dados internos.

## Artefatos Finais

Os documentos finais da entrega estao em `docs/`:

- `docs/Relatorio_Final_Analise_Avancada_Telemetria_Vale.docx`: versao editavel final.
- `docs/Predição de Eventos Críticos em Equipamentos de Mina por Análise Avançada de Telemetria — Vale.pdf`: versao final em PDF.
- `docs/RELATORIO_FINAL.md`: versao Markdown estruturada do relatorio.
- `docs/RELATORIO_DECISOES_PROJETO.md`: resumo das decisoes tecnicas e economicas.
- `docs/CONTINUIDADE_PROJETO.md`: historico operacional completo para continuidade.
- `docs/PREMISSAS_ECONOMICAS_EXTERNAS.md`: fontes e limites das premissas economicas simuladas.

## Principais Decisoes Auditadas

- `Is_Dont_Go` foi tratado como flag fornecida, nao como falha mecanica confirmada.
- O target provisiorio passou a ser o inicio de ao menos um novo episodio `Is_Dont_Go` no horizonte futuro.
- Splits de treino, validacao e teste sempre respeitam nexo temporal.
- A lacuna global de `31/05/2025` foi tratada como ausencia de observacao, nao como zero alarmes.
- A anomalia `PE3798` em `29/06/2025` foi expurgada somente para os dois alarmes Remote PTO identificados.
- Duplicatas exatas foram removidas apenas da camada analitica, preservando rastreabilidade dos IDs brutos.
- TAGs semelhantes, como `CA5926` e `CA65926`, nao foram fundidas por ausencia de evidencia.
- O modelo para escavadeiras nao foi recomendado para operacao com o target atual por escassez de positivos.

## Resultado Modelado

O baseline auditavel para relatorio e:

- `referencia_24h_ids_textual + RandomForest`.

O melhor candidato operacional sob as premissas economicas estimadas e:

- `multijanela_core_ids_textual + CatBoost`, no recorte de caminhoes;
- faixa candidata de threshold: `0,390-0,440`;
- valor medio estimado no cenario base: `2.990.200` na validacao de cenarios.

Interpretacao obrigatoria:

- os valores monetarios sao simulacoes baseadas em premissas publicas e aproximadas;
- para implantacao produtiva, a empresa deve substituir essas premissas por custos reais de ERP,
  manutencao, despacho, producao horaria, duracao de paradas e taxa de conversao de alerta em acao util.

## Estrutura

```text
docs/       Relatorios, premissas, graficos e documentos finais
notebooks/  Auditorias, experimentos, modelagem e valoracao
scripts/    Geradores reprodutiveis dos notebooks
data/       Dados locais nao versionados
models/     Modelos locais nao versionados
outputs/    Saidas locais nao versionadas
```

## Dados

Os dados brutos esperados ficam localmente em:

```text
data/raw/Base
```

Essa pasta nao e versionada. O repositorio preserva codigo, notebooks, documentacao e artefatos
finais, mas nao distribui a base bruta.

## Ambiente

Recomendado: Python 3.12.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Para executar notebooks pela linha de comando:

```bash
.venv/bin/jupyter execute notebooks/22_Validacao_JunJul_Valoracao_Modelos.ipynb
```

## Notebooks Principais

- `01_Auditoria_e_Preparacao_Dos_Dados.ipynb`: auditoria estrutural e preparacao inicial.
- `02_Aprofundamento_Das_Decisoes_Pendentes.ipynb`: duplicatas, nomes, anomalias e regras.
- `03_Baseline_Episodios_8h.ipynb`: primeiro baseline temporal auditado.
- `04_Auditoria_Do_Baseline_8h.ipynb`: auditoria dos erros e recortes do baseline.
- `05_Cenarios_Estados_Hibernando.ipynb`: avaliacao de estados operacionais.
- `06_Investigacao_Erros_E_Familias.ipynb`: investigacao de erros e familias de alarmes.
- `07_Modelo_Com_Conceitos_De_Alarme.ipynb`: conceitos textuais normalizados.
- `08_Modelo_Com_Mapa_Manual_De_Conceitos.ipynb`: mapa manual exploratorio.
- `09_Teste_Gaps_E_Janelas_Temporais.ipynb`: gaps e janelas temporais.
- `10_Refino_Gap_Sequencia_24h8h.ipynb`: refino de gap para 24h/8h.
- `11_Conceitos_Familias_24h8h_Sensibilidade_Gap.ipynb`: conceitos/familias na nova janela.
- `12_Auditoria_Nova_Referencia_24h8h.ipynb`: auditoria da nova referencia.
- `13_Teste_Multijanelas_Temporais.ipynb`: features multijanelas sem vazamento futuro.
- `14_Threshold_Curva_Decisao_Custo.ipynb`: decisao por custo.
- `15` a `19`: refinamentos de candidatos e modelos finais.
- `20_Explicabilidade_E_Politica_Final.ipynb`: explicabilidade e politica final.
- `21_Valoracao_Cenarios_Economicos.ipynb`: valoracao economica por cenario.
- `22_Validacao_JunJul_Valoracao_Modelos.ipynb`: validacao comparavel dos cenarios.

## Reprodutibilidade

Os notebooks mais recentes sao gerados por scripts em `scripts/`. Exemplos:

```bash
.venv/bin/python scripts/create_explainability_final_policy_notebook.py
.venv/bin/python scripts/create_economic_valuation_scenarios_notebook.py
.venv/bin/python scripts/create_june_july_valuation_validation_notebook.py
```

Quando houver alteracao permanente de notebook, a preferencia e alterar o script gerador, regenerar o
notebook e executar a validacao.

## Limitacoes

O modelo atual antecipa recorrencia da flag `Is_Dont_Go`, nao falha fisica confirmada. A recomendacao
economica depende diretamente de premissas de custo, tempo de parada e taxa de acao confirmada. Por
isso, a entrada em producao exige validacao com dados internos da empresa.
