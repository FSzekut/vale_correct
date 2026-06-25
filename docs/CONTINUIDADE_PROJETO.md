# Continuidade do Projeto Vale Correct

Última atualização: 18 de junho de 2026.

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

O notebook 03, seu gerador e este documento ainda precisam ser commitados e enviados ao GitHub.

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

## 13. Próximos passos acordados

Ordem recomendada:

1. auditar detalhadamente o baseline por TAG, tipo de equipamento e período;
2. analisar falsos positivos e falsos negativos;
3. comparar outros limites de sequência, mantendo a base e o split fixos;
4. comparar outras janelas de observação e horizontes;
5. criar mapa auditável `Id_Alarme -> conceito_alarme -> familia_alarme`;
6. testar modelo com famílias e depois features multijanelas;
7. executar os cinco experimentos de estados operacionais;
8. comparar Random Forest e XGBoost usando exatamente a mesma base;
9. procurar um target ligado a consequência operacional observável;
10. somente depois discutir produção, downtime ou ROI.

## 14. Regras para futuras sessões

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

## 15. Estado local ao criar este documento

Arquivos ainda não publicados:

```text
notebooks/03_Baseline_Episodios_8h.ipynb
scripts/create_baseline_notebook.py
docs/CONTINUIDADE_PROJETO.md
```

Também houve atualização do `.gitignore` para ignorar `notebooks/.tmp/`, diretório temporário do
DuckDB.
