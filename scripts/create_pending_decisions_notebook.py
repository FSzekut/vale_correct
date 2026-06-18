from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "02_Aprofundamento_Das_Decisoes_Pendentes.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 02 — Aprofundamento das Decisões Pendentes

## Princípio orientador

> **Este notebook estabelece uma base de investigação sem remover registros e sem converter
> anomalias em erros por suposição. Os resultados devem orientar a preparação da base auditada.**

Este notebook aprofunda os pontos que ainda não possuem evidência suficiente para uma decisão
definitiva. Cada seção apresenta dados, gráficos, interpretação permitida e condição necessária
para aprovação.

Nenhuma transformação destrutiva é executada.
"""
    ),
    code(
        """
from pathlib import Path
import re
import unicodedata

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 100)
pd.set_option("display.max_rows", 120)

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
BASE = ROOT / "data" / "raw" / "Base"
TEL_GLOB = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")
AP_PATH = str(BASE / "datasets" / "apontamentos" / "desenvolver_apontamentos.parquet")
RULES_PATH = BASE / "Alarmes - Regra de Negocio.xlsx"

con = duckdb.connect()
con.execute("SET threads=4")
con.execute(f"CREATE OR REPLACE VIEW tel AS SELECT * FROM read_parquet('{TEL_GLOB}', union_by_name=true)")
con.execute(f"CREATE OR REPLACE VIEW ap AS SELECT * FROM read_parquet('{AP_PATH}')")

def query(sql):
    return con.sql(sql).df()

print(f"Raiz do projeto: {ROOT}")
"""
    ),
    md(
        """
## 1. Conflitos entre ID e nome do alarme

Um `Id_Alarme` associado a nomes diferentes pode resultar de:

- espaços externos;
- variação de capitalização ou sufixo;
- problema de codificação de caracteres;
- mudança legítima de nomenclatura;
- reutilização indevida do identificador.

Primeiro medimos o efeito de normalizações progressivas. Normalizar não significa substituir
automaticamente: a análise serve para separar conflitos puramente textuais de conflitos semânticos.
"""
    ),
    code(
        """
alarm_names = query(
    '''
    SELECT Id_Alarme, Alarme, count(*) AS registros,
           min(Data_Evento) AS inicio, max(Data_Evento) AS fim
    FROM tel GROUP BY 1, 2
    '''
)

def normalize_text(value, remove_suffix=False):
    value = str(value).strip().casefold()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\\s+", " ", value)
    if remove_suffix:
        value = re.sub(r"\\s*\\(l-1850\\)$", "", value)
    return value

alarm_names["nome_trim"] = alarm_names["Alarme"].str.strip()
alarm_names["nome_normalizado"] = alarm_names["Alarme"].map(normalize_text)
alarm_names["nome_sem_sufixo_modelo"] = alarm_names["Alarme"].map(
    lambda value: normalize_text(value, remove_suffix=True)
)

conflict_summary = pd.DataFrame([
    {"criterio": "Nome bruto", "ids_conflitantes": (alarm_names.groupby("Id_Alarme")["Alarme"].nunique() > 1).sum()},
    {"criterio": "Após trim", "ids_conflitantes": (alarm_names.groupby("Id_Alarme")["nome_trim"].nunique() > 1).sum()},
    {"criterio": "Unicode/capitalização/espaços", "ids_conflitantes": (alarm_names.groupby("Id_Alarme")["nome_normalizado"].nunique() > 1).sum()},
    {"criterio": "Também sem sufixo L-1850", "ids_conflitantes": (alarm_names.groupby("Id_Alarme")["nome_sem_sufixo_modelo"].nunique() > 1).sum()},
])
display(conflict_summary)

ax = sns.barplot(data=conflict_summary, x="ids_conflitantes", y="criterio", color="#4C78A8")
ax.set(title="IDs de alarme ainda conflitantes após cada normalização", xlabel="IDs conflitantes", ylabel="")
plt.show()
"""
    ),
    code(
        """
remaining_conflicts = (
    alarm_names.groupby("Id_Alarme")
    .filter(lambda group: group["nome_sem_sufixo_modelo"].nunique() > 1)
    .sort_values(["Id_Alarme", "registros"], ascending=[True, False])
)
display(remaining_conflicts.head(80))

print(
    "Decisão pendente: normalizações textuais podem compor uma coluna derivada, "
    "mas conflitos restantes não devem ser consolidados sem catálogo mestre."
)
"""
    ),
    code(
        """
conflict_table = (
    remaining_conflicts.groupby("Id_Alarme")
    .agg(
        nomes=("nome_sem_sufixo_modelo", "nunique"),
        variantes=("Alarme", lambda s: list(dict.fromkeys(s.tolist()))),
        registros=("registros", "sum"),
    )
    .reset_index()
    .sort_values(["nomes", "registros"], ascending=[False, False])
)
display(conflict_table)

print(
    "Leitura prática: os 11 casos remanescentes representam 11 Id_Alarme com mais de uma "
    "descrição normalizada. Dois grupos são variações por caractere/encoding e nove pertencem "
    "à família TESTE-OP ENTRADA ARTICULADA, que podem ser consolidados em uma descrição oficial "
    "sem afetar o treinamento se a chave operacional permanecer o Id_Alarme."
)
"""
    ),
    md(
        """
## 2. Repetições lógicas que não são cópias exatas

A maior parte das repetições lógicas é cópia exata em todas as colunas, exceto ID. Restam poucos
casos em que timestamp, TAG, alarme, valor, classe e target coincidem, mas algum campo contextual
difere.

Esses casos são apresentados individualmente porque uma regra automática ampla seria desproporcional.
"""
    ),
    code(
        """
logical_nonexact = query(
    '''
    WITH logical_groups AS (
      SELECT Data_Evento, TAG, Id_Alarme, Valor, Classe, Is_Dont_Go, count(*) AS repeticoes
      FROM tel GROUP BY ALL HAVING count(*) > 1
    )
    SELECT t.Data_Evento, t.TAG, t.Id_Alarme, t.Alarme, t.Valor, t.Classe, t.Is_Dont_Go,
           count(*) AS linhas,
           count(DISTINCT (t.Inicio_Turno, t.Fim_Turno, t.Nome_Operador_Anon,
                           t.Matricula_Operador_Hash, t.Id_Criticidade, t.Criticidade)) AS variantes_contextuais,
           list(DISTINCT t.Inicio_Turno ORDER BY t.Inicio_Turno) AS turnos,
           list(DISTINCT t.Nome_Operador_Anon ORDER BY t.Nome_Operador_Anon) AS operadores
    FROM tel t
    JOIN logical_groups g USING (Data_Evento, TAG, Id_Alarme, Valor, Classe, Is_Dont_Go)
    GROUP BY 1, 2, 3, 4, 5, 6, 7
    HAVING variantes_contextuais > 1
    ORDER BY variantes_contextuais DESC, Data_Evento
    '''
)
display(logical_nonexact)

logical_nonexact["em_fronteira_turno"] = logical_nonexact["Data_Evento"].dt.hour.isin([6, 18])
display(logical_nonexact["em_fronteira_turno"].value_counts().rename_axis("fronteira_turno").reset_index(name="grupos"))

print(
    "Leitura prática: estas linhas não são cópias exatas; são o mesmo alarme para o mesmo "
    "equipamento em outro momento, às vezes na troca de turno ou com operador diferente. "
    "Como são raras e não representam Don't Go, a decisão conservadora é preservá-las sem alterações."
)
"""
    ),
    md(
        """
## 3. Perfil das anomalias de volume

O objetivo é identificar se os candidatos formam um único tipo de problema ou vários fenômenos.
Para cada TAG/dia marcado pelo critério `mediana + 10 × MAD`, medimos:

- razão entre volume observado e mediana da TAG;
- concentração do alarme dominante;
- proporção de timestamps distintos;
- presença de linhas `Is_Dont_Go`;
- diversidade de alarmes.

Alta concentração em um único sinal sugere investigação localizada. Baixa concentração pode indicar
atividade geral elevada ou múltiplos fenômenos simultâneos.
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
volume_candidates = query(
    '''
    WITH med AS (
      SELECT TAG, median(registros) AS mediana FROM tag_day GROUP BY TAG
    ), stats AS (
      SELECT d.TAG, m.mediana,
             median(abs(d.registros - m.mediana)) AS mad
      FROM tag_day d JOIN med m USING (TAG)
      GROUP BY d.TAG, m.mediana
    ), flagged AS (
      SELECT d.*, s.mediana, s.mad,
             d.registros / s.mediana AS razao_mediana
      FROM tag_day d JOIN stats s USING (TAG)
      WHERE d.registros > s.mediana + 10 * greatest(s.mad, 1)
    ), alarm_counts AS (
      SELECT t.TAG, cast(t.Data_Evento AS DATE) AS data, trim(t.Alarme) AS alarme,
             count(*) AS registros_alarme
      FROM tel t JOIN flagged f
        ON t.TAG = f.TAG AND cast(t.Data_Evento AS DATE) = f.data
      GROUP BY 1, 2, 3
    ), ranked AS (
      SELECT *, row_number() OVER (PARTITION BY TAG, data ORDER BY registros_alarme DESC) AS ordem
      FROM alarm_counts
    )
    SELECT f.*, r.alarme AS alarme_dominante, r.registros_alarme,
           r.registros_alarme / f.registros AS concentracao_dominante,
           f.timestamps_distintos / f.registros AS proporcao_timestamps_distintos
    FROM flagged f JOIN ranked r USING (TAG, data)
    WHERE r.ordem = 1
    ORDER BY razao_mediana DESC
    '''
)
display(volume_candidates.head(30))
"""
    ),
    code(
        """
fig, axes = plt.subplots(1, 2, figsize=(16, 6))
sns.scatterplot(
    data=volume_candidates, x="razao_mediana", y="concentracao_dominante",
    hue="TAG", size="registros", sizes=(30, 350), ax=axes[0], legend=False
)
axes[0].set(
    title="Magnitude versus concentração do sinal dominante",
    xlabel="Volume / mediana diária da TAG",
    ylabel="Participação do alarme dominante",
)

sns.scatterplot(
    data=volume_candidates, x="alarmes_distintos", y="proporcao_timestamps_distintos",
    hue="linhas_dont_go", palette="viridis", size="registros", sizes=(30, 350), ax=axes[1]
)
axes[1].set(
    title="Diversidade e unicidade temporal dos candidatos",
    xlabel="Alarmes distintos",
    ylabel="Timestamps distintos / registros",
)
plt.tight_layout()
plt.show()

candidate_classes = pd.cut(
    volume_candidates["concentracao_dominante"],
    bins=[-0.01, 0.25, 0.50, 0.80, 1.0],
    labels=["distribuído", "moderadamente concentrado", "concentrado", "altamente concentrado"],
)
display(candidate_classes.value_counts().rename_axis("perfil").reset_index(name="candidatos"))

print(
    "Leitura do gráfico 1: pontos no canto superior direito são candidatos com volume muito acima "
    "da própria mediana e forte concentração em um único alarme. Isso sugere um fenômeno localizado, "
    "não um aumento geral de atividade."
)
print(
    "Leitura do gráfico 2: quanto maior a proporção de timestamps distintos, mais o volume se parece "
    "com uma sequência contínua de eventos reais; quanto menor essa proporção, maior a chance de "
    "repetição mecânica do mesmo estado. O eixo de alarmes distintos ajuda a separar um pico "
    "monotemático de um pico espalhado por vários alarmes."
)
"""),
    md(
        """
## 4. Sobreposições dos apontamentos da CA65789

As sobreposições estão concentradas em uma única TAG. Investigamos pares de classe, duração e
distribuição temporal.

Sobreposições entre `Hibernando` e outros estados podem indicar uma regra de registro paralela, e não
necessariamente linhas incorretas. Sem compreender essa semântica, escolher arbitrariamente uma classe
apagaria informação.
"""
    ),
    code(
        """
overlaps = query(
    '''
    WITH ordered AS (
      SELECT *,
             lag(Fim) OVER (PARTITION BY Tag ORDER BY Inicio, Fim, Id) AS fim_anterior,
             lag(Classe) OVER (PARTITION BY Tag ORDER BY Inicio, Fim, Id) AS classe_anterior
      FROM ap
    )
    SELECT Tag, Inicio, Fim, Classe, classe_anterior, fim_anterior,
           date_diff('second', Inicio, fim_anterior) AS sobreposicao_s
    FROM ordered
    WHERE Inicio < fim_anterior
    ORDER BY Inicio
    '''
)
display(overlaps.head(30))

overlap_pairs = (
    overlaps.groupby(["classe_anterior", "Classe"])
    .agg(casos=("sobreposicao_s", "size"), mediana_s=("sobreposicao_s", "median"), max_s=("sobreposicao_s", "max"))
    .reset_index()
    .sort_values("casos", ascending=False)
)
display(overlap_pairs)

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
sns.barplot(data=overlap_pairs, y="casos", x="classe_anterior", hue="Classe", ax=axes[0])
axes[0].set(title="Pares de classes nas sobreposições", xlabel="Classe anterior", ylabel="Casos")
sns.histplot(overlaps["sobreposicao_s"] / 60, bins=30, ax=axes[1])
axes[1].set(title="Duração das sobreposições", xlabel="Minutos sobrepostos")
plt.tight_layout()
plt.show()

print("Decisão pendente: confirmar se Hibernando é um estado paralelo antes de resolver sobreposições.")
"""
    ),
    md(
        """
## 5. Sensibilidade da definição de episódios

Uma linha positiva não equivale necessariamente a um episódio independente. Para visualizar a
sensibilidade, calculamos o número de episódios para diversos intervalos mínimos entre ocorrências
consecutivas da mesma TAG e alarme.

O gráfico ajuda a identificar regiões de estabilidade, mas a escolha final exige justificativa
operacional.
"""
    ),
    code(
        """
positive_gaps = query(
    '''
    SELECT date_diff(
             'second',
             lag(Data_Evento) OVER (PARTITION BY TAG, Alarme ORDER BY Data_Evento),
             Data_Evento
           ) AS gap_s
    FROM tel WHERE Is_Dont_Go = 1
    '''
)
thresholds = [
    ("1 min", 60), ("5 min", 300), ("15 min", 900), ("30 min", 1800),
    ("1 h", 3600), ("2 h", 7200), ("4 h", 14400), ("8 h", 28800), ("24 h", 86400),
]
episode_curve = pd.DataFrame([
    {"intervalo": label, "segundos": seconds, "episodios": int(positive_gaps["gap_s"].isna().sum() + (positive_gaps["gap_s"] > seconds).sum())}
    for label, seconds in thresholds
])
episode_curve["reducao_vs_linhas_pct"] = (1 - episode_curve["episodios"] / len(positive_gaps)) * 100
display(episode_curve)

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(episode_curve["intervalo"], episode_curve["episodios"], marker="o")
ax.set(title="Sensibilidade da contagem de episódios", xlabel="Separação mínima", ylabel="Episódios candidatos")
plt.show()

print("Decisão pendente: intervalo de episódio depende de validação operacional e das regras do catálogo.")
"""
    ),
    md(
        """
## 6. Aplicabilidade das regras de negócio

O catálogo mistura regras simples e regras temporais. Padronizamos `NIVEL` apenas para análise textual
e mostramos a distribuição de `SITUACAO`, `QTD` e `TEMPO`.

Regras com `QTD = 1` e `TEMPO = 0` são candidatas a aplicação direta, mas ainda dependem da
interpretação de `SITUACAO` e `NIVEL`. Regras consecutivas exigem definição explícita de sequência.
"""
    ),
    code(
        """
rules = pd.read_excel(RULES_PATH, sheet_name="CMA")
rules["NIVEL_NORMALIZADO"] = rules["NIVEL"].astype(str).str.strip().str.casefold()
rules["regra_direta_candidata"] = (rules["QTD"] == 1) & (rules["TEMPO"] == 0)

display(rules["SITUACAO"].value_counts().rename_axis("situacao").reset_index(name="regras"))
display(rules.groupby(["QTD", "TEMPO"]).size().reset_index(name="regras").sort_values("regras", ascending=False))
display(rules.groupby(["NIVEL", "NIVEL_NORMALIZADO"]).size().reset_index(name="regras"))

fig, axes = plt.subplots(1, 2, figsize=(16, 6))
rules["SITUACAO"].value_counts().head(12).sort_values().plot.barh(ax=axes[0])
axes[0].set(title="Principais situações do catálogo", xlabel="Regras", ylabel="")
sns.scatterplot(data=rules, x="TEMPO", y="QTD", hue="NIVEL_NORMALIZADO", style="regra_direta_candidata", ax=axes[1])
axes[1].set(title="Quantidade e tempo exigidos pelas regras")
plt.tight_layout()
plt.show()

display(rules[rules["regra_direta_candidata"]].head(30))
print(f"Regras candidatas a aplicação direta: {rules['regra_direta_candidata'].sum()} de {len(rules)}")
"""
    ),
    md(
        """
## 7. Matriz atual de decisão

| Tema | Evidência atual | Decisão possível agora | Pendência |
|---|---|---|---|
| Espaços externos em alarmes | Diferença puramente textual | Criar coluna normalizada com `trim` | Preservar bruto |
| Conflitos ID/nome | Parte explicada por texto; parte semântica | Não consolidar conflitos restantes | Catálogo mestre |
| Duplicatas exatas | Iguais em todas as colunas exceto ID | Deduplicar na camada analítica | Guardar mapa de IDs |
| Repetições não exatas | Poucos casos, associados a contexto | Preservar | Regra de fronteira de turno |
| PE3798 29/06 | Alternância Remote PTO em milissegundos | Marcar sinais/intervalo, não remover dia | Validação operacional |
| Outros volumes anômalos | Perfis heterogêneos | Manter flags | Drill-down por perfil |
| Sobreposições CA65789 | Hibernando domina os pares | Preservar estados | Confirmar semântica |
| Episódios | Contagem altamente sensível ao intervalo | Não fixar intervalo ainda | Validação operacional |
| Regras CMA | Regras diretas e temporais misturadas | Implementar somente após formalização | Interpretar situações |

O próximo passo técnico recomendado é construir uma camada auditada **sem exclusões irreversíveis**,
contendo colunas normalizadas, flags e tabelas de rastreabilidade.
"""
    ),
]

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"display_name": "Python 3 (.venv)", "language": "python", "name": "python3"}
nb["metadata"]["language_info"] = {"name": "python", "version": "3.12"}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUTPUT)
print(f"Notebook criado em {OUTPUT}")
