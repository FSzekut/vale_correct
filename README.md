# Predição de eventos críticos em equipamentos de mina

Projeto de análise avançada de telemetria para antecipar a recorrência de eventos críticos em
caminhões e escavadeiras de mineração.

O trabalho foi desenvolvido no Programa Desenvolver, com foco em transformar dados de alta
frequência em uma evidência temporal auditável para priorizar inspeções e intervenções.

## O problema

O projeto avalia se o histórico de telemetria e alarmes contém sinal suficiente para antecipar,
com até oito horas de antecedência, a recorrência de eventos classificados como `Is_Dont_Go`.

O objetivo não é afirmar que a flag representa uma falha mecânica confirmada. Ela é tratada como o
evento observado disponível nos dados. Essa distinção orienta todo o trabalho de modelagem e a
interpretação dos resultados.

## Principais decisões

- preservação dos dados brutos e aplicação das exclusões somente em camadas analíticas derivadas;
- auditoria de duplicatas, lacunas, anomalias e identificadores de alarme;
- construção de um target temporal baseado na recorrência futura do evento;
- separação entre treino, validação e teste respeitando a ordem cronológica;
- comparação de representações de alarmes, janelas temporais e famílias de modelos;
- calibração de probabilidades e escolha de threshold por valor econômico simulado;
- análise separada para caminhões e escavadeiras.

## Resultado principal

O candidato mais robusto no recorte analisado foi um CatBoost multijanela para caminhões, com
calibração e faixa candidata de threshold entre 0,390 e 0,440.

No cenário econômico base, o valor incremental médio simulado foi de aproximadamente US$ 2,99 milhões
por período de teste, com pior resultado temporal ainda positivo, de aproximadamente US$ 2,29 milhões.
Esses valores não são ROI realizado. São projeções dependentes de premissas externas sobre custos,
tempo de parada, produtividade e conversão de alertas em ações úteis.

Para escavadeiras, a quantidade de eventos positivos não foi suficiente para uma recomendação
operacional confiável. O projeto registra uma formulação futura com mais histórico e um target
ligado a ordens de serviço ou paradas reais.

## Estrutura

```text
docs/       relatórios, decisões, premissas e gráficos
notebooks/  auditorias, experimentos, modelagem e validação
scripts/    geradores dos notebooks mais recentes
```

Os notebooks numerados em `notebooks/` documentam o caminho desde a auditoria inicial até a
validação dos cenários econômicos. Os scripts em `scripts/` são a fonte preferencial dos notebooks
gerados.

## Dados

Os dados brutos não são distribuídos neste repositório. O código espera uma estrutura local
semelhante a:

```text
data/raw/Base/datasets/telemetria/
data/raw/Base/datasets/apontamentos/
```

Para reproduzir a análise, é necessário ter acesso autorizado à base original e ajustar os
caminhos locais nos notebooks ou em uma configuração própria. Nenhum arquivo de dados deve ser
adicionado ao controle de versão.

## Ambiente

O projeto foi desenvolvido em Python 3.12. As dependências estão em `requirements.txt`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Os notebooks podem ser executados com Jupyter. A execução completa depende da disponibilidade dos
dados locais, que não acompanham este repositório.

## Limitações

- O modelo antecipa a recorrência da flag `Is_Dont_Go`, não uma falha física confirmada.
- As premissas econômicas são aproximações e precisam ser substituídas por dados internos antes de
  qualquer decisão de implantação.
- O resultado para escavadeiras não é considerado operacionalmente confiável.
- Um piloto em modo sombra é o próximo passo adequado: medir conversão em ação útil, custo real de
  falso positivo, falhas evitadas e aderência à capacidade da manutenção.

## Relatórios

Os relatórios técnicos e o registro de decisões estão em `docs/`. O PDF final resume o problema,
a auditoria dos dados, a modelagem, a avaliação econômica e as recomendações de implantação.

## Segurança e publicação

O repositório não deve conter dados brutos, modelos serializados, credenciais, arquivos de ambiente,
artefatos de execução ou caminhos que revelem a estrutura pessoal de arquivos. Antes de cada
publicação, os notebooks e o histórico devem ser verificados novamente.
