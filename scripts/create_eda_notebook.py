from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "01_Auditoria_e_Preparacao_Dos_Dados.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 01 — Auditoria e Preparação dos Dados

## Objetivo

Este notebook inicia o projeto pela etapa mais importante: compreender e auditar os dados antes
de qualquer limpeza, engenharia de atributos ou modelagem.

O objetivo não é procurar evidências para confirmar uma hipótese previamente escolhida. O objetivo
é testar sistematicamente a integridade das fontes, identificar comportamentos incomuns e separar:

- **erro confirmado**: viola uma regra verificável dos dados ou do domínio;
- **anomalia**: comportamento raro que merece investigação, mas pode ser legítimo;
- **hipótese operacional**: interpretação que depende de confirmação externa;
- **dado válido**: comportamento consistente com as evidências disponíveis.

### Princípios adotados

1. Os arquivos brutos são imutáveis.
2. Nenhum registro será removido apenas por apresentar volume elevado ou comportamento incomum.
3. Toda decisão deve seguir a sequência **evidência → interpretação → decisão → impacto**.
4. Ausência de evidência não será tratada como evidência de falha, parada ou defeito de sensor.
5. Alterações futuras deverão apresentar contagens antes/depois e uma justificativa reproduzível.
6. `Is_Dont_Go` será inicialmente tratado conforme sua descrição no dicionário, sem assumir que
   representa uma falha física ou parada confirmada.

> **Escopo desta etapa:** detectar, quantificar e documentar. As análises abaixo criam candidatos
> para tratamento, mas preservam os dados até que exista justificativa suficiente.
"""
    ),
    md(
        """
## 1. Configuração reproduzível

Todos os caminhos são relativos à raiz do projeto. DuckDB é usado para consultar os arquivos
Parquet sem carregar dezenas de milhões de linhas integralmente na memória. Pandas é reservado
para tabelas pequenas, resultados agregados e leitura dos arquivos Excel.

Também registramos as versões das bibliotecas. Isso permite investigar diferenças caso o notebook
seja executado futuramente em outro ambiente.
"""
    ),
    code(
        """
from pathlib import Path
import platform

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 100)
pd.set_option("display.max_rows", 100)

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent

BASE = ROOT / "data" / "raw" / "Base"
TEL_GLOB = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")
AP_PATH = str(BASE / "datasets" / "apontamentos" / "desenvolver_apontamentos.parquet")
DICT_PATH = BASE / "Dicionario_Dados.xlsx"
RULES_PATH = BASE / "Alarmes - Regra de Negocio.xlsx"

required = [BASE, Path(AP_PATH), DICT_PATH, RULES_PATH]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise FileNotFoundError(f"Fontes obrigatórias ausentes: {missing}")

con = duckdb.connect()
con.execute("SET threads=4")
con.execute(f"CREATE OR REPLACE VIEW tel AS SELECT * FROM read_parquet('{TEL_GLOB}', union_by_name=true)")
con.execute(f"CREATE OR REPLACE VIEW ap AS SELECT * FROM read_parquet('{AP_PATH}')")

def query(sql: str) -> pd.DataFrame:
    return con.sql(sql).df()

versions = pd.DataFrame({
    "componente": ["Python", "pandas", "numpy", "duckdb"],
    "versao": [platform.python_version(), pd.__version__, np.__version__, duckdb.__version__],
})
display(versions)
print(f"Raiz do projeto: {ROOT}")
"""
    ),
    md(
        """
## 2. Inventário das fontes e contrato de dados

Antes de analisar conteúdo, verificamos se as colunas entregues correspondem ao dicionário de dados.
Uma coluna ausente, inesperada ou com tipo divergente pode indicar mudança de esquema entre arquivos.

O catálogo de regras também é inspecionado nesta etapa, mas ainda não é aplicado. Primeiro precisamos
entender quais condições ele exige e quais campos realmente existem na telemetria.
"""
    ),
    code(
        """
tel_schema = query("DESCRIBE SELECT * FROM tel")
ap_schema = query("DESCRIBE SELECT * FROM ap")
dict_tel = pd.read_excel(DICT_PATH, sheet_name="Telemetria")
dict_ap = pd.read_excel(DICT_PATH, sheet_name="Apontamentos")
rules = pd.read_excel(RULES_PATH, sheet_name="CMA")

inventory = pd.DataFrame([
    {"fonte": "Telemetria", "colunas_arquivo": len(tel_schema), "colunas_dicionario": len(dict_tel)},
    {"fonte": "Apontamentos", "colunas_arquivo": len(ap_schema), "colunas_dicionario": len(dict_ap)},
    {"fonte": "Regras CMA", "colunas_arquivo": len(rules.columns), "colunas_dicionario": np.nan},
])
display(inventory)

def compare_contract(schema: pd.DataFrame, dictionary: pd.DataFrame) -> pd.DataFrame:
    actual = set(schema["column_name"])
    documented = set(dictionary["Nome da Feature"])
    return pd.DataFrame({
        "teste": ["documentada_e_ausente", "presente_e_nao_documentada"],
        "colunas": [sorted(documented - actual), sorted(actual - documented)],
    })

print("Contrato — Telemetria")
display(compare_contract(tel_schema, dict_tel))
print("Contrato — Apontamentos")
display(compare_contract(ap_schema, dict_ap))
print("Estrutura das regras CMA")
display(rules.head())
"""
    ),
    md(
        """
## 3. Integridade estrutural e cobertura

Os primeiros testes procuram erros objetivos:

- IDs ausentes ou repetidos;
- datas ausentes;
- valores de target fora de `{0, 1}`;
- período e cardinalidade das fontes;
- colunas essenciais nulas.

Esses testes não interpretam o negócio. Eles verificam propriedades básicas necessárias para qualquer
análise posterior.
"""
    ),
    code(
        """
overview_tel = query(
    '''
    SELECT count(*) AS registros,
           count(DISTINCT Id_Eventos_Telemetria) AS ids_distintos,
           min(Data_Evento) AS inicio,
           max(Data_Evento) AS fim,
           count(DISTINCT TAG) AS tags,
           count(DISTINCT Id_Alarme) AS ids_alarme,
           count(DISTINCT Alarme) AS alarmes,
           sum(Is_Dont_Go) AS linhas_dont_go
    FROM tel
    '''
)
overview_ap = query(
    '''
    SELECT count(*) AS registros,
           count(DISTINCT Id) AS ids_distintos,
           min(Inicio) AS inicio,
           max(Fim) AS fim,
           count(DISTINCT Tag) AS tags
    FROM ap
    '''
)
display(overview_tel)
display(overview_ap)

essential_nulls = query(
    '''
    SELECT
      sum(Id_Eventos_Telemetria IS NULL) AS id_nulo,
      sum(Data_Evento IS NULL) AS data_nula,
      sum(TAG IS NULL) AS tag_nula,
      sum(Id_Alarme IS NULL) AS id_alarme_nulo,
      sum(Alarme IS NULL) AS alarme_nulo,
      sum(Is_Dont_Go IS NULL) AS target_nulo,
      sum(Is_Dont_Go NOT IN (0, 1)) AS target_fora_dominio
    FROM tel
    '''
)
display(essential_nulls)

# O resumo abaixo cobre todas as colunas, não apenas as essenciais. Nulos podem ser
# legítimos, mas precisam ser conhecidos antes de qualquer seleção de atributos.
null_expressions = ", ".join(
    f"sum({column} IS NULL) AS {column}" for column in tel_schema["column_name"]
)
null_profile_tel = query(f"SELECT {null_expressions} FROM tel").T.reset_index()
null_profile_tel.columns = ["coluna", "nulos"]
null_profile_tel["pct_nulos"] = null_profile_tel["nulos"] / int(overview_tel.loc[0, "registros"]) * 100
display(null_profile_tel.sort_values("pct_nulos", ascending=False))
"""
    ),
    md(
        """
## 4. Consistência semântica entre colunas

Alguns erros não aparecem como nulos. Por exemplo, o mesmo `Id_Alarme` pode estar associado a nomes
diferentes, uma TAG pode aparecer com frotas incompatíveis ou a coluna `Dia` pode discordar da data.

Testamos relações esperadas sem assumir antecipadamente que qualquer divergência é erro. Divergências
são apresentadas para investigação; algumas podem representar mudanças legítimas ao longo do tempo.
"""
    ),
    code(
        """
semantic_tests = query(
    '''
    SELECT
      sum(Dia <> day(Data_Evento)) AS dia_incompativel_com_data,
      sum(trim(TAG) <> TAG) AS tag_com_espacos_externos,
      sum(trim(Alarme) <> Alarme) AS alarme_com_espacos_externos,
      sum(TAG !~ '^[A-Za-z]{2}[0-9]+$') AS tag_fora_padrao_observado
    FROM tel
    '''
)
display(semantic_tests)

alarm_mapping_conflicts = query(
    '''
    SELECT Id_Alarme, count(DISTINCT Alarme) AS nomes,
           list(DISTINCT Alarme ORDER BY Alarme) AS valores
    FROM tel
    GROUP BY Id_Alarme
    HAVING count(DISTINCT Alarme) > 1
    ORDER BY nomes DESC, Id_Alarme
    '''
)
tag_profile_conflicts = query(
    '''
    SELECT TAG,
           count(DISTINCT Tag_Frota) AS tag_frotas,
           count(DISTINCT Tipo) AS tipos,
           count(DISTINCT Localidade) AS localidades,
           list(DISTINCT Tag_Frota ORDER BY Tag_Frota) AS valores_frota,
           list(DISTINCT Tipo ORDER BY Tipo) AS valores_tipo
    FROM tel
    GROUP BY TAG
    HAVING count(DISTINCT Tag_Frota) > 1 OR count(DISTINCT Tipo) > 1
    ORDER BY TAG
    '''
)
print(f"IDs de alarme associados a múltiplos nomes: {len(alarm_mapping_conflicts)}")
display(alarm_mapping_conflicts.head(20))
print(f"TAGs com mais de uma frota ou tipo: {len(tag_profile_conflicts)}")
display(tag_profile_conflicts)

# Espaços externos são um problema de padronização confirmado porque duas strings
# semanticamente iguais passam a ser tratadas como categorias diferentes.
alarm_whitespace = query(
    '''
    SELECT Alarme, trim(Alarme) AS alarme_sem_espacos,
           count(*) AS registros,
           count(DISTINCT Id_Alarme) AS ids_alarme
    FROM tel
    WHERE trim(Alarme) <> Alarme
    GROUP BY 1, 2
    ORDER BY registros DESC
    LIMIT 30
    '''
)
display(alarm_whitespace)

# Também verificamos se a normalização por trim reduz conflitos entre ID e nome.
# Isso mede o impacto da inconsistência sem alterar os dados brutos.
mapping_impact = query(
    '''
    SELECT
      count(*) FILTER (WHERE nomes_originais > 1) AS ids_conflitantes_original,
      count(*) FILTER (WHERE nomes_sem_espacos > 1) AS ids_conflitantes_apos_trim
    FROM (
      SELECT Id_Alarme,
             count(DISTINCT Alarme) AS nomes_originais,
             count(DISTINCT trim(Alarme)) AS nomes_sem_espacos
      FROM tel GROUP BY Id_Alarme
    )
    '''
)
display(mapping_impact)
"""
    ),
    md(
        """
## 5. Coerência temporal e continuidade

Verificamos a cobertura diária e a coerência dos turnos. Uma data sem registros confirma uma lacuna
na fonte, mas não permite concluir sua causa. Da mesma forma, eventos fora do intervalo declarado
do turno podem indicar erro de atribuição, formato inesperado ou regra de borda.

Por isso, a decisão nesta etapa é apenas registrar e quantificar as inconsistências.
"""
    ),
    code(
        """
temporal_checks = query(
    '''
    WITH parsed AS (
      SELECT Data_Evento,
             try_cast(Inicio_Turno AS TIMESTAMP) AS inicio_turno_ts,
             try_cast(Fim_Turno AS TIMESTAMP) AS fim_turno_ts
      FROM tel
    )
    SELECT
      sum(inicio_turno_ts IS NULL) AS inicio_turno_nao_convertivel,
      sum(fim_turno_ts IS NULL) AS fim_turno_nao_convertivel,
      sum(fim_turno_ts <= inicio_turno_ts) AS turno_duracao_invalida,
      sum(Data_Evento < inicio_turno_ts OR Data_Evento > fim_turno_ts) AS evento_fora_turno
    FROM parsed
    '''
)
display(temporal_checks)

daily = query(
    '''
    SELECT cast(Data_Evento AS DATE) AS data,
           count(*) AS registros,
           count(DISTINCT TAG) AS tags,
           sum(Is_Dont_Go) AS linhas_dont_go
    FROM tel GROUP BY 1 ORDER BY 1
    '''
)
calendar = pd.DataFrame({"data": pd.date_range(daily["data"].min(), daily["data"].max(), freq="D")})
daily_complete = calendar.merge(daily, on="data", how="left").fillna(0)
missing_days = daily_complete[daily_complete["registros"] == 0]
display(missing_days)

fig, ax = plt.subplots(figsize=(15, 4))
ax.plot(daily_complete["data"], daily_complete["registros"], linewidth=1)
ax.scatter(missing_days["data"], missing_days["registros"], color="red", label="dia sem registros")
ax.set(title="Cobertura diária da telemetria", ylabel="Registros", xlabel="Data")
ax.legend()
plt.show()
"""
    ),
    md(
        """
## 6. Investigação de TAGs potencialmente inconsistentes

Erros de digitação em identificadores são comuns, portanto procuramos TAGs parecidas e comparamos
seus históricos. Entretanto, semelhança textual não autoriza a fusão de equipamentos.

Uma fusão só seria justificável se múltiplas evidências fossem compatíveis, como ausência de
coexistência temporal, mesma frota, mesmo tipo e continuidade operacional. Se TAGs semelhantes
coexistem ou possuem perfis próprios, elas devem ser preservadas como equipamentos distintos.
"""
    ),
    code(
        """
tag_profiles = query(
    '''
    SELECT TAG, Tag_Frota, Tipo,
           count(*) AS registros,
           min(Data_Evento) AS inicio,
           max(Data_Evento) AS fim,
           sum(Is_Dont_Go) AS linhas_dont_go
    FROM tel
    GROUP BY TAG, Tag_Frota, Tipo
    ORDER BY TAG, Tag_Frota, Tipo
    '''
)

from difflib import SequenceMatcher

tags = sorted(tag_profiles["TAG"].unique())
similar_pairs = []
for i, left in enumerate(tags):
    for right in tags[i + 1:]:
        score = SequenceMatcher(None, left, right).ratio()
        if score >= 0.75:
            similar_pairs.append({"tag_a": left, "tag_b": right, "similaridade": score})

similar_pairs = pd.DataFrame(similar_pairs).sort_values("similaridade", ascending=False)
display(similar_pairs.head(30))

similar_tags = sorted(set(similar_pairs["tag_a"]).union(similar_pairs["tag_b"]))
display(tag_profiles[tag_profiles["TAG"].isin(similar_tags)])

print("Decisão desta etapa: preservar todas as TAGs. Similaridade textual é apenas um sinal para investigação.")
"""
    ),
    md(
        """
## 7. Duplicidades e repetições temporais

Distinguimos dois fenômenos:

- **ID repetido:** erro objetivo, pois o identificador deveria ser único.
- **evento lógico repetido:** mesmas informações essenciais em mais de uma linha, mas IDs diferentes.

Eventos lógicos repetidos podem ser duplicação de ingestão, retransmissão ou comportamento legítimo
do equipamento. Portanto, serão quantificados e marcados, não excluídos automaticamente.
"""
    ),
    code(
        """
duplicates = query(
    '''
    SELECT
      count(*) - count(DISTINCT Id_Eventos_Telemetria) AS ids_repetidos_excedentes,
      count(*) - count(DISTINCT (Data_Evento, TAG, Id_Alarme, Valor, Classe, Is_Dont_Go))
        AS eventos_logicos_repetidos_excedentes
    FROM tel
    '''
)
display(duplicates)

duplicate_groups = query(
    '''
    SELECT TAG, Data_Evento, Id_Alarme, Alarme, Valor, Classe, Is_Dont_Go,
           count(*) AS repeticoes
    FROM tel
    GROUP BY ALL
    HAVING count(*) > 1
    ORDER BY repeticoes DESC, TAG, Data_Evento
    LIMIT 30
    '''
)
display(duplicate_groups)

positive_repetition = query(
    '''
    WITH gaps AS (
      SELECT TAG, Alarme, Data_Evento,
             date_diff('second',
               lag(Data_Evento) OVER (PARTITION BY TAG, Alarme ORDER BY Data_Evento),
               Data_Evento) AS gap_s
      FROM tel WHERE Is_Dont_Go = 1
    )
    SELECT count(*) AS linhas_positivas,
           sum(gap_s BETWEEN 0 AND 60) AS repeticao_ate_1_min,
           sum(gap_s BETWEEN 0 AND 3600) AS repeticao_ate_1_h,
           median(gap_s) AS mediana_gap_s
    FROM gaps
    '''
)
display(positive_repetition)
"""
    ),
    md(
        """
### 7.1 Separação entre duplicata exata e repetição lógica

O critério lógico anterior ignora campos contextuais como operador, turno e criticidade. Para evitar
remover registros legitimamente distintos, comparamos também todas as colunas da telemetria, exceto
o identificador `Id_Eventos_Telemetria`.

Quando duas linhas são iguais em todas as demais colunas e diferem somente pelo ID, há evidência
suficiente para classificá-las como duplicatas exatas na camada analítica. Os dados brutos continuam
preservados e o ID removido deve permanecer registrado em uma tabela de controle.
"""
    ),
    code(
        """
exact_duplicates = query(
    '''
    SELECT
      count(*) - count(DISTINCT (
        Data_Evento, Inicio_Turno, Fim_Turno, Dia, Localidade, TAG, Tag_Frota, Tipo,
        Nome_Operador_Anon, Matricula_Operador_Hash, Id_Alarme, Alarme, Id_Criticidade,
        Criticidade, Valor, Classe, Is_Dont_Go
      )) AS duplicatas_exatas_excedentes,
      count(*) - count(DISTINCT (
        Data_Evento, TAG, Id_Alarme, Valor, Classe, Is_Dont_Go
      )) AS repeticoes_logicas_excedentes
    FROM tel
    '''
)
display(exact_duplicates)

exact_duplicate_summary = query(
    '''
    WITH groups AS (
      SELECT
        Data_Evento, Inicio_Turno, Fim_Turno, Dia, Localidade, TAG, Tag_Frota, Tipo,
        Nome_Operador_Anon, Matricula_Operador_Hash, Id_Alarme, Alarme, Id_Criticidade,
        Criticidade, Valor, Classe, Is_Dont_Go, count(*) AS repeticoes
      FROM tel
      GROUP BY ALL
      HAVING count(*) > 1
    )
    SELECT count(*) AS grupos_duplicados,
           sum(repeticoes - 1) AS duplicatas_exatas_excedentes,
           sum(CASE WHEN Is_Dont_Go = 1 THEN repeticoes - 1 ELSE 0 END)
             AS duplicatas_exatas_positivas
    FROM groups
    '''
)
display(exact_duplicate_summary)

print(
    "Decisão: deduplicação exata aprovada somente para a futura camada analítica. "
    "Repetições lógicas não exatas permanecem preservadas para investigação."
)
"""
    ),
    md(
        """
## 8. Anomalias de volume por equipamento e dia

Volume elevado pode indicar repetição anormal, operação intensa, mudança de configuração ou outra
condição legítima. Para evitar seleção manual, usamos um critério reproduzível por equipamento:

- calculamos mediana e MAD (*median absolute deviation*) do volume diário de cada TAG;
- marcamos como candidato o dia cujo volume excede `mediana + 10 × MAD`;
- mostramos composição, timestamps distintos, alarmes distintos e target.

O multiplicador 10 é deliberadamente conservador. A flag identifica candidatos para investigação;
ela não classifica automaticamente um sensor como defeituoso e não remove linhas.
"""
    ),
    code(
        """
con.execute(
    '''
    CREATE OR REPLACE TEMP TABLE tag_day AS
    SELECT TAG, cast(Data_Evento AS DATE) AS data,
           count(*) AS registros,
           count(DISTINCT Data_Evento) AS timestamps_distintos,
           count(DISTINCT Alarme) AS alarmes_distintos,
           sum(Is_Dont_Go) AS linhas_dont_go
    FROM tel GROUP BY 1, 2
    '''
)
volume_anomalies = query(
    '''
    WITH med AS (
      SELECT TAG, median(registros) AS mediana_registros
      FROM tag_day GROUP BY TAG
    ), stats AS (
      SELECT d.TAG, m.mediana_registros,
             median(abs(d.registros - m.mediana_registros)) AS mad_registros
      FROM tag_day d JOIN med m USING (TAG)
      GROUP BY d.TAG, m.mediana_registros
    )
    SELECT d.*, s.mediana_registros, s.mad_registros,
           d.registros > s.mediana_registros + 10 * greatest(s.mad_registros, 1)
             AS flag_volume_anomalo
    FROM tag_day d JOIN stats s USING (TAG)
    ORDER BY d.registros DESC
    '''
)
print(f"Combinações TAG/dia marcadas: {volume_anomalies['flag_volume_anomalo'].sum():,}")
display(volume_anomalies.head(30))
"""
    ),
    md(
        """
### 8.1 Composição dos maiores candidatos

A composição ajuda a distinguir cenários. Muitos registros com poucos alarmes alternando rapidamente
é diferente de muitos registros distribuídos entre diversos alarmes. Ainda assim, nenhuma dessas
características prova isoladamente defeito de sensor.

Selecionamos os maiores candidatos derivados pelo critério anterior, sem escolher datas manualmente.
"""
    ),
    code(
        """
top_candidates = volume_anomalies[volume_anomalies["flag_volume_anomalo"]].head(10)[["TAG", "data"]]
con.register("top_candidates", top_candidates)

candidate_composition = query(
    '''
    SELECT t.TAG, cast(t.Data_Evento AS DATE) AS data, t.Alarme, t.Valor,
           count(*) AS registros, sum(t.Is_Dont_Go) AS linhas_dont_go
    FROM tel t
    JOIN top_candidates c
      ON t.TAG = c.TAG AND cast(t.Data_Evento AS DATE) = c.data
    GROUP BY 1, 2, 3, 4
    QUALIFY row_number() OVER (PARTITION BY t.TAG, cast(t.Data_Evento AS DATE)
                              ORDER BY count(*) DESC) <= 5
    ORDER BY t.TAG, data, registros DESC
    '''
)
display(candidate_composition)

print("Decisão desta etapa: manter os registros e carregar a flag de anomalia para análises posteriores.")
"""
    ),
    md(
        """
### 8.2 Drill-down do maior candidato: PE3798 em 29/06/2025

O maior volume identificado pelo critério reproduzível foi a TAG `PE3798` em **29/06/2025**.
Não existe telemetria de julho na fonte analisada; portanto, qualquer referência a 29/07 deve ser
tratada como possível erro de data até que outra fonte seja disponibilizada.

Para decidir se o volume representa atividade legítima, duplicação ou emissão anormal, avaliamos:

1. magnitude em relação ao próprio histórico da TAG;
2. contribuição de cada alarme;
3. unicidade de IDs e eventos lógicos;
4. cadência e alternância dos sinais dominantes;
5. distribuição ao longo do dia e entre operadores;
6. situação operacional registrada nos apontamentos.

O objetivo não é decidir antecipadamente que houve falha de sensor. Procuramos localizar exatamente
qual componente explica a discrepância e qual tratamento seria proporcional às evidências.
"""
    ),
    code(
        """
pe3798_day_comparison = query(
    '''
    WITH daily AS (
      SELECT cast(Data_Evento AS DATE) AS data, count(*) AS registros
      FROM tel WHERE TAG = 'PE3798' GROUP BY 1
    ), reference AS (
      SELECT median(registros) AS mediana_outros_dias,
             quantile_cont(registros, 0.95) AS p95_outros_dias,
             max(registros) AS max_outros_dias
      FROM daily WHERE data <> DATE '2025-06-29'
    ), target_day AS (
      SELECT registros AS registros_29_06
      FROM daily WHERE data = DATE '2025-06-29'
    )
    SELECT *,
           registros_29_06 / mediana_outros_dias AS razao_mediana,
           registros_29_06 / max_outros_dias AS razao_max_anterior
    FROM reference, target_day
    '''
)
display(pe3798_day_comparison)

pe3798_top_signals = query(
    '''
    SELECT trim(Alarme) AS alarme, Valor, Criticidade,
           count(*) AS registros,
           count(DISTINCT Data_Evento) AS timestamps_distintos,
           sum(Is_Dont_Go) AS linhas_dont_go,
           min(Data_Evento) AS inicio,
           max(Data_Evento) AS fim
    FROM tel
    WHERE TAG = 'PE3798' AND cast(Data_Evento AS DATE) = DATE '2025-06-29'
    GROUP BY 1, 2, 3
    ORDER BY registros DESC
    LIMIT 20
    '''
)
display(pe3798_top_signals)

pe3798_duplicate_check = query(
    '''
    SELECT count(*) AS registros,
           count(*) - count(DISTINCT Id_Eventos_Telemetria) AS ids_repetidos_excedentes,
           count(*) - count(DISTINCT (Data_Evento, TAG, Id_Alarme, Valor, Classe, Is_Dont_Go))
             AS eventos_logicos_repetidos_excedentes
    FROM tel
    WHERE TAG = 'PE3798' AND cast(Data_Evento AS DATE) = DATE '2025-06-29'
    '''
)
display(pe3798_duplicate_check)
"""
    ),
    md(
        """
#### Cadência e alternância dos sinais dominantes

Dois sinais Remote PTO respondem por quase todo o excesso. Para verificar se são eventos independentes
ou estados alternando rapidamente, calculamos a transição para o próximo registro considerando somente
esse par.

Uma alternância persistente em dezenas de milissegundos é evidência objetiva de **emissão anormal de
telemetria** em relação ao restante da fonte. Ainda assim, os dados não permitem distinguir sozinhos
entre defeito físico do sensor, configuração, firmware, lógica de aquisição ou outro mecanismo.
"""
    ),
    code(
        """
REMOTE_PTO_SIGNALS = (
    "Remote PTO Preprogrammed Speed Control Switch - Not Configured",
    "Remote PTO Preprogrammed Speed Control Switch - Switch Off",
)

pe3798_transitions = query(
    f'''
    WITH ordered AS (
      SELECT Data_Evento, trim(Alarme) AS alarme,
             lead(Data_Evento) OVER (ORDER BY Data_Evento, Id_Eventos_Telemetria) AS proximo_ts,
             lead(trim(Alarme)) OVER (ORDER BY Data_Evento, Id_Eventos_Telemetria) AS proximo_alarme
      FROM tel
      WHERE TAG = 'PE3798'
        AND cast(Data_Evento AS DATE) = DATE '2025-06-29'
        AND trim(Alarme) IN {REMOTE_PTO_SIGNALS}
    )
    SELECT alarme, proximo_alarme,
           count(*) AS transicoes,
           median(date_diff('millisecond', Data_Evento, proximo_ts)) AS mediana_ms,
           avg(date_diff('millisecond', Data_Evento, proximo_ts)) AS media_ms
    FROM ordered
    WHERE proximo_alarme IS NOT NULL
    GROUP BY 1, 2
    ORDER BY transicoes DESC
    '''
)
display(pe3798_transitions)

pe3798_hourly = query(
    '''
    SELECT date_trunc('hour', Data_Evento) AS hora,
           count(*) AS registros,
           count(DISTINCT Data_Evento) AS timestamps_distintos,
           count(DISTINCT Alarme) AS alarmes
    FROM tel
    WHERE TAG = 'PE3798' AND cast(Data_Evento AS DATE) = DATE '2025-06-29'
    GROUP BY 1 ORDER BY 1
    '''
)
display(pe3798_hourly)

fig, ax = plt.subplots(figsize=(14, 4))
ax.plot(pe3798_hourly["hora"], pe3798_hourly["registros"], marker="o")
ax.set(title="PE3798 — volume horário em 29/06/2025", xlabel="Hora", ylabel="Registros")
plt.xticks(rotation=45)
plt.show()
"""
    ),
    md(
        """
#### Relação com a operação

Os registros são cruzados com os apontamentos do mesmo instante. Se o padrão ocorresse apenas durante
um estado específico, isso poderia apoiar uma interpretação operacional. A presença durante estados
distintos mostra que a taxa elevada não é explicada apenas pela classificação `Operando` ou `Parado`.

Também verificamos operadores e turnos para avaliar se o pico está restrito a uma pessoa ou troca de
turno. O padrão atravessa múltiplos operadores, reduzindo a plausibilidade de uma causa exclusivamente
associada a um operador.
"""
    ),
    code(
        """
pe3798_operational = query(
    '''
    SELECT coalesce(a.Classe, 'SEM_APONTAMENTO_NO_INSTANTE') AS classe_operacional,
           count(*) AS registros,
           count(DISTINCT t.Data_Evento) AS timestamps_distintos,
           count(DISTINCT t.Alarme) AS alarmes
    FROM tel t
    LEFT JOIN ap a
      ON t.TAG = a.Tag
     AND t.Data_Evento >= a.Inicio
     AND t.Data_Evento < a.Fim
    WHERE t.TAG = 'PE3798' AND cast(t.Data_Evento AS DATE) = DATE '2025-06-29'
    GROUP BY 1 ORDER BY registros DESC
    '''
)
pe3798_operators = query(
    '''
    SELECT Nome_Operador_Anon, count(*) AS registros,
           min(Data_Evento) AS inicio, max(Data_Evento) AS fim,
           count(DISTINCT Alarme) AS alarmes
    FROM tel
    WHERE TAG = 'PE3798' AND cast(Data_Evento AS DATE) = DATE '2025-06-29'
    GROUP BY 1 ORDER BY registros DESC
    '''
)
display(pe3798_operational)
display(pe3798_operators)
"""
    ),
    md(
        """
#### Conclusão do drill-down e decisão proporcional

**Evidências confirmadas**

- O volume de 29/06 é aproximadamente 32 vezes a mediana diária da própria PE3798 e 17,5 vezes
  maior que seu segundo maior dia.
- IDs e eventos lógicos são únicos; portanto, o pico não é explicado por duplicação exata.
- Dois estados Remote PTO somam aproximadamente 1,29 milhão de registros.
- Esses estados alternam quase perfeitamente, com intervalos medianos de dezenas de milissegundos.
- O padrão atravessa horas, operadores e estados operacionais.
- Não há linha `Is_Dont_Go = 1` nesse dia.

**Interpretação permitida pelos dados**

Existe emissão anormal e altamente repetitiva dos dois sinais Remote PTO. A fonte disponível não
permite afirmar se a causa foi sensor físico, configuração, firmware ou aquisição.

**Decisão**

Não remover o dia inteiro. Outros alarmes do período podem conter informação operacional válida.
Na preparação dos dados, criar uma flag específica para o par Remote PTO no intervalo observado e
avaliar estratégias como limitar sua contribuição por janela ou removê-lo apenas de features de
volume. A decisão final permanece pendente de validação operacional.
"""
    ),
    md(
        """
## 9. Auditoria dos apontamentos operacionais

Os apontamentos descrevem intervalos de estado operacional. Verificamos:

- IDs e datas ausentes;
- duração zero ou negativa;
- sobreposições dentro da mesma TAG;
- relações entre TAG, frota e tipo.

Sobreposição é uma inconsistência temporal relevante porque um equipamento não deveria ocupar dois
estados mutuamente exclusivos ao mesmo tempo. Porém, antes de corrigir, precisamos identificar se
o problema é duplicidade, granularidade, atraso de registro ou outra regra operacional.
"""
    ),
    code(
        """
ap_quality = query(
    '''
    SELECT count(*) AS registros,
           count(*) - count(DISTINCT Id) AS ids_repetidos_excedentes,
           sum(Inicio IS NULL OR Fim IS NULL) AS datas_nulas,
           sum(Fim < Inicio) AS duracao_negativa,
           sum(Fim = Inicio) AS duracao_zero
    FROM ap
    '''
)
display(ap_quality)

ap_overlaps = query(
    '''
    WITH ordered AS (
      SELECT *,
             lag(Fim) OVER (PARTITION BY Tag ORDER BY Inicio, Fim, Id) AS fim_anterior,
             lag(Id) OVER (PARTITION BY Tag ORDER BY Inicio, Fim, Id) AS id_anterior
      FROM ap
    )
    SELECT Tag, count(*) AS sobreposicoes,
           sum(date_diff('second', Inicio, fim_anterior)) AS segundos_sobrepostos
    FROM ordered
    WHERE Inicio < fim_anterior
    GROUP BY Tag ORDER BY sobreposicoes DESC
    '''
)
display(ap_overlaps)

ap_profile_conflicts = query(
    '''
    SELECT Tag, count(DISTINCT Frota) AS frotas, count(DISTINCT Tipo) AS tipos,
           list(DISTINCT Frota ORDER BY Frota) AS valores_frota,
           list(DISTINCT Tipo ORDER BY Tipo) AS valores_tipo
    FROM ap GROUP BY Tag
    HAVING count(DISTINCT Frota) > 1 OR count(DISTINCT Tipo) > 1
    ORDER BY Tag
    '''
)
display(ap_profile_conflicts)
"""
    ),
    md(
        """
## 10. Significado observado de `Is_Dont_Go`

O dicionário define `Is_Dont_Go` como uma flag associada à lista Don't Go. Para avaliar o que a flag
representa nos dados, examinamos criticidade, classe da telemetria e estado operacional no instante
do evento.

O cruzamento temporal utiliza somente linhas positivas, reduzindo o custo computacional. Quando há
sobreposição de apontamentos, mais de uma classe pode coincidir com o mesmo instante; esses casos
devem permanecer explicitamente identificados.
"""
    ),
    code(
        """
positive_profile = query(
    '''
    SELECT Criticidade, Classe, count(*) AS linhas,
           count(DISTINCT TAG) AS tags,
           count(DISTINCT Alarme) AS alarmes
    FROM tel WHERE Is_Dont_Go = 1
    GROUP BY Criticidade, Classe
    ORDER BY linhas DESC
    '''
)
display(positive_profile)

operational_at_positive = query(
    '''
    WITH matched AS (
      SELECT t.Id_Eventos_Telemetria, t.TAG, t.Data_Evento,
             count(a.Id) AS apontamentos_coincidentes,
             string_agg(DISTINCT a.Classe, ', ' ORDER BY a.Classe) AS classes_operacionais
      FROM tel t
      LEFT JOIN ap a
        ON t.TAG = a.Tag
       AND t.Data_Evento >= a.Inicio
       AND t.Data_Evento < a.Fim
      WHERE t.Is_Dont_Go = 1
      GROUP BY 1, 2, 3
    )
    SELECT coalesce(classes_operacionais, 'SEM_APONTAMENTO_NO_INSTANTE') AS classes_operacionais,
           count(*) AS linhas_dont_go,
           sum(apontamentos_coincidentes > 1) AS com_sobreposicao
    FROM matched
    GROUP BY 1 ORDER BY linhas_dont_go DESC
    '''
)
display(operational_at_positive)

print("Interpretação limitada aos dados: a flag identifica linhas marcadas, mas não confirma sozinha parada ou falha física.")
"""
    ),
    md(
        """
## 11. Linhas positivas versus episódios candidatos

Alertas consecutivos podem representar repetição do mesmo episódio. Para mostrar a sensibilidade da
contagem, agrupamos linhas positivas por TAG e alarme usando diferentes intervalos de separação.

Não escolhemos ainda um intervalo definitivo. Essa escolha deve considerar a dinâmica operacional
dos alarmes e, idealmente, validação com especialistas ou eventos de manutenção confirmados.
"""
    ),
    code(
        """
episode_sensitivity = query(
    '''
    WITH gaps AS (
      SELECT TAG, Alarme, Data_Evento,
             date_diff('second',
               lag(Data_Evento) OVER (PARTITION BY TAG, Alarme ORDER BY Data_Evento),
               Data_Evento) AS gap_s
      FROM tel WHERE Is_Dont_Go = 1
    )
    SELECT count(*) AS linhas_positivas,
           sum(gap_s IS NULL OR gap_s > 3600) AS episodios_gap_1h,
           sum(gap_s IS NULL OR gap_s > 14400) AS episodios_gap_4h,
           sum(gap_s IS NULL OR gap_s > 28800) AS episodios_gap_8h
    FROM gaps
    '''
)
display(episode_sensitivity)
"""
    ),
    md(
        """
## 12. Catálogo de regras de negócio

O catálogo contém mais condições do que o nome do evento: tipo, situação, quantidade, tempo e nível.
Primeiro avaliamos cobertura nominal, isto é, se o nome dos alarmes positivos aparece no catálogo.

Cobertura nominal não prova que a regra completa foi satisfeita. A aplicação correta dependerá da
interpretação de `SITUACAO`, `QTD` e `TEMPO`, além da disponibilidade dos campos necessários.
"""
    ),
    code(
        """
rules_summary = pd.DataFrame({
    "metrica": ["regras", "eventos", "tipos", "situacoes", "niveis", "qtd_nula", "tempo_nulo"],
    "valor": [
        len(rules), rules["EVENTO"].nunique(), rules["TIPO"].nunique(),
        rules["SITUACAO"].nunique(), rules["NIVEL"].nunique(),
        rules["QTD"].isna().sum(), rules["TEMPO"].isna().sum(),
    ],
})
display(rules_summary)

con.register("rules_cma", rules)
rule_coverage = query(
    '''
    SELECT count(*) AS linhas_positivas,
           sum(r.EVENTO IS NOT NULL) AS evento_presente_catalogo,
           sum(r.EVENTO IS NULL) AS evento_ausente_catalogo
    FROM tel t
    LEFT JOIN (SELECT DISTINCT EVENTO FROM rules_cma) r ON t.Alarme = r.EVENTO
    WHERE t.Is_Dont_Go = 1
    '''
)
display(rule_coverage)

unavailable_rule_fields = pd.DataFrame({
    "condicao_regra": ["TIPO", "EVENTO", "SITUACAO", "QTD", "TEMPO", "NIVEL"],
    "campo_direto_na_telemetria": ["Tipo", "Alarme", "Não identificado diretamente",
                                    "Exige agregação temporal", "Exige interpretação temporal",
                                    "Não identificado diretamente"],
    "status": ["Disponível", "Disponível", "Requer investigação", "Derivável após definição",
               "Derivável após definição", "Requer investigação"],
})
display(unavailable_rule_fields)
"""
    ),
    md(
        """
## 13. Registro de decisões desta etapa

O registro abaixo diferencia decisões já sustentadas pelos dados de decisões ainda pendentes.
Nenhuma limpeza destrutiva foi aplicada neste notebook.
"""
    ),
    code(
        """
decision_log = pd.DataFrame([
    {
        "tema": "Arquivos brutos",
        "evidencia": "Fontes consultadas diretamente em data/raw",
        "decisao": "Preservar sem alterações",
        "status": "Aprovada",
    },
    {
        "tema": "TAGs semelhantes",
        "evidencia": "Perfis e coexistência temporal apresentados na seção 6",
        "decisao": "Preservar identificadores originais; não fundir por similaridade textual",
        "status": "Aprovada",
    },
    {
        "tema": "Duplicatas lógicas",
        "evidencia": "Separação entre duplicatas exatas e repetições contextualmente diferentes",
        "decisao": "Deduplicar apenas cópias exatas na camada analítica; investigar as demais",
        "status": "Parcialmente aprovada",
    },
    {
        "tema": "Espaços externos em nomes de alarme",
        "evidencia": "Linhas e categorias afetadas apresentadas na seção 4",
        "decisao": "Tratar como erro de padronização em camada derivada, preservando o valor bruto",
        "status": "Aprovada",
    },
    {
        "tema": "ID de alarme associado a múltiplos nomes",
        "evidencia": "Conflitos antes e após normalização por trim apresentados na seção 4",
        "decisao": "Investigar codificação e semântica antes de consolidar nomes",
        "status": "Pendente de validação",
    },
    {
        "tema": "Volume anômalo",
        "evidencia": "Critério mediana + 10×MAD por TAG e composição dos candidatos",
        "decisao": "Criar flag; não classificar automaticamente como falha de sensor",
        "status": "Pendente de validação",
    },
    {
        "tema": "PE3798 em 29/06/2025",
        "evidencia": "Dois sinais Remote PTO alternam em dezenas de milissegundos e explicam o excesso",
        "decisao": "Não remover o dia; marcar o par de sinais e avaliar tratamento localizado",
        "status": "Pendente de validação operacional",
    },
    {
        "tema": "Is_Dont_Go",
        "evidencia": "Criticidade, estado operacional e catálogo de regras",
        "decisao": "Não interpretar isoladamente como falha ou parada confirmada",
        "status": "Aprovada",
    },
    {
        "tema": "Downtime e ROI",
        "evidencia": "Target ainda não representa parada confirmada",
        "decisao": "Não calcular até definir episódios e vínculo operacional válido",
        "status": "Aprovada",
    },
])
display(decision_log)
"""
    ),
    md(
        """
## 14. Conclusão e próximos requisitos

Este notebook estabelece uma base de investigação sem remover registros e sem converter anomalias em
erros por suposição. Os resultados devem orientar a preparação da base auditada.

### Próximas decisões necessárias

1. Definir a interpretação executável das regras `SITUACAO`, `QTD`, `TEMPO` e `NIVEL`.
2. Avaliar a origem das duplicatas lógicas e decidir se representam retransmissão ou eventos válidos.
3. Investigar operacionalmente os candidatos de volume anômalo antes de qualquer exclusão.
4. Resolver ou representar explicitamente sobreposições dos apontamentos.
5. Definir episódios de alerta com critério operacional validado.
6. Somente depois dessas decisões, construir uma variável alvo e uma base de modelagem.

### Regra para a próxima etapa

Qualquer tratamento deverá incluir uma tabela de controle com registros antes, registros afetados,
registros depois, regra aplicada e justificativa baseada nas evidências deste notebook.
"""
    ),
]

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {
    "display_name": "Python 3 (.venv)",
    "language": "python",
    "name": "python3",
}
nb["metadata"]["language_info"] = {"name": "python", "version": "3.12"}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUTPUT)
print(f"Notebook criado em {OUTPUT}")
