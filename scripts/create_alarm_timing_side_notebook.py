from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "SIDE_Destrinchar_Tempos_Dos_Alarmes.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Estudo lateral — Tempos dos Alarmes

## Princípio orientador

> **Este notebook estabelece uma base de investigação sem remover registros e sem converter
> anomalias em erros por suposição. Os resultados devem orientar a preparação da base auditada.**

Este é um estudo lateral, não uma etapa numerada da preparação dos dados. Seu objetivo é separar e
relacionar dois conceitos:

- **cadência de emissão:** tempo observado entre registros consecutivos do mesmo alarme;
- **janela da regra de negócio:** período no qual uma quantidade de ocorrências deve ser avaliada.

Uma cadência frequente não prova que registros próximos pertençam ao mesmo episódio. Da mesma forma,
o campo `TEMPO` de uma regra não deve ser adotado automaticamente como separação entre episódios.
Nenhum registro é removido ou reclassificado neste notebook.
"""
    ),
    code(
        """
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 100)
pd.set_option("display.max_rows", 150)

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
BASE = ROOT / "data" / "raw" / "Base"
TEL_GLOB = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")
RULES_PATH = BASE / "Alarmes - Regra de Negocio.xlsx"

con = duckdb.connect()
con.execute("SET threads=4")
con.execute(f"CREATE OR REPLACE VIEW tel AS SELECT * FROM read_parquet('{TEL_GLOB}', union_by_name=true)")

def query(sql):
    return con.sql(sql).df()

rules = pd.read_excel(RULES_PATH, sheet_name="CMA")
print(f"Raiz do projeto: {ROOT}")
print(f"Regras CMA: {len(rules):,}")
"""
    ),
    md(
        """
## 1. O que as regras temporais exigem

As regras combinam `QTD` e `TEMPO`. Por exemplo, `QTD = 5` e `TEMPO = 360` descreve uma decisão
dependente de cinco ocorrências dentro de uma janela de 360 minutos, sujeita também à interpretação
de `SITUACAO` e `NIVEL`.

### Regra de negócio associada ao gráfico

- `QTD = 1` e `TEMPO = 0`: candidata a avaliação por ocorrência isolada;
- `QTD > 1` ou `TEMPO > 0`: exige uma definição executável de contagem, janela e consecutividade;
- regras com o mesmo evento podem possuir condições diferentes e devem permanecer distintas.
"""
    ),
    code(
        """
rule_pairs = (
    rules.groupby(["QTD", "TEMPO"], dropna=False)
    .size().reset_index(name="regras")
    .sort_values("regras", ascending=False)
)
display(rule_pairs)

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
sns.scatterplot(
    data=rules, x="TEMPO", y="QTD", hue="NIVEL", size="QTD",
    sizes=(50, 180), alpha=.8, ax=axes[0]
)
axes[0].set(title="Quantidade e janela exigidas pelas regras", xlabel="TEMPO informado", ylabel="QTD")
sns.barplot(data=rule_pairs, x="regras", y=rule_pairs.apply(lambda x: f"{int(x.QTD)} em {int(x.TEMPO)}", axis=1), ax=axes[1])
axes[1].set(title="Combinações QTD/TEMPO", xlabel="Regras", ylabel="QTD em TEMPO")
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 2. Cadência global observada

Calculamos o intervalo entre registros consecutivos da mesma combinação `TAG + Id_Alarme`.
O agrupamento inclui todos os registros porque a finalidade é compreender o comportamento de
emissão, não apenas os eventos classificados como `Dont Go`.

### Regra de negócio associada ao gráfico

Não existe justificativa para assumir emissão a cada segundo. Uma janela temporal precisa tolerar
cadências distintas sem confundir repetição de transmissão com novas ocorrências operacionais.
"""
    ),
    code(
        """
global_gaps = query(
    '''
    WITH gaps AS (
        SELECT date_diff(
                   'millisecond',
                   lag(Data_Evento) OVER (PARTITION BY TAG, Id_Alarme ORDER BY Data_Evento),
                   Data_Evento
               ) AS gap_ms
        FROM tel
    )
    SELECT gap_ms FROM gaps WHERE gap_ms IS NOT NULL AND gap_ms >= 0
    '''
)

quantiles = global_gaps["gap_ms"].quantile([.10, .25, .50, .75, .90, .95, .99]).rename("gap_ms").reset_index()
quantiles.columns = ["quantil", "gap_ms"]
display(quantiles)

bins = [-1, 0, 99, 999, 4_999, 9_999, 59_999, 299_999, 3_599_999, np.inf]
labels = ["0 ms", "1–99 ms", "100–999 ms", "1–<5 s", "5–<10 s", "10–<60 s", "1–<5 min", "5–<60 min", "≥1 h"]
global_gaps["faixa"] = pd.cut(global_gaps["gap_ms"], bins=bins, labels=labels)
gap_bands = global_gaps["faixa"].value_counts(sort=False).rename_axis("faixa").reset_index(name="intervalos")
gap_bands["percentual"] = 100 * gap_bands["intervalos"] / gap_bands["intervalos"].sum()
display(gap_bands)

fig, ax = plt.subplots(figsize=(13, 5))
sns.barplot(data=gap_bands, x="percentual", y="faixa", color="#4C78A8", ax=ax)
ax.set(title="Distribuição global dos intervalos consecutivos", xlabel="% dos intervalos", ylabel="")
plt.show()
"""
    ),
    md(
        """
## 3. Perfil temporal por alarme

O mapa preferencial deve ser definido por `Id_Alarme`, pois esse identificador pode generalizar para
novos equipamentos. Para reduzir conclusões baseadas em amostras pequenas, o gráfico mostra apenas
alarmes com pelo menos 100 intervalos observados.

### Regra de negócio associada ao gráfico

O tempo típico por alarme é evidência para interpretar contagens em uma janela. Ele ainda não define
sozinho o encerramento de um episódio. Alarmes com poucos dados devem usar uma referência mais geral,
nunca um parâmetro específico estimado sem suporte.
"""
    ),
    code(
        """
alarm_timing = query(
    '''
    WITH gaps AS (
        SELECT Id_Alarme, Alarme, TAG,
               date_diff('millisecond',
                   lag(Data_Evento) OVER (PARTITION BY TAG, Id_Alarme ORDER BY Data_Evento),
                   Data_Evento
               ) AS gap_ms
        FROM tel
    )
    SELECT Id_Alarme, any_value(Alarme) AS Alarme,
           count(*) AS intervalos, count(DISTINCT TAG) AS tags,
           median(gap_ms) AS mediana_ms,
           quantile_cont(gap_ms, .90) AS p90_ms,
           quantile_cont(gap_ms, .99) AS p99_ms
    FROM gaps
    WHERE gap_ms IS NOT NULL AND gap_ms >= 0
    GROUP BY Id_Alarme
    '''
)
eligible_alarm_timing = alarm_timing[alarm_timing["intervalos"] >= 100].copy()
display(alarm_timing.sort_values("intervalos", ascending=False).head(30))

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
sns.histplot(np.log10(eligible_alarm_timing["mediana_ms"].clip(lower=1)), bins=35, ax=axes[0])
axes[0].set(title="Medianas por alarme", xlabel="log10 da mediana em ms")
sns.scatterplot(data=eligible_alarm_timing, x="mediana_ms", y="p90_ms", size="intervalos", hue="tags", alpha=.7, ax=axes[1])
axes[1].set(xscale="log", yscale="log", title="Tempo típico e cauda por alarme", xlabel="Mediana (ms)", ylabel="P90 (ms)")
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 4. O mesmo alarme mantém a cadência entre equipamentos?

Para cada `Id_Alarme + TAG`, calculamos a mediana dos intervalos. Em seguida, medimos a razão entre
as medianas mais alta e mais baixa observadas entre TAGs do mesmo alarme. O gráfico considera apenas
combinações com pelo menos 100 intervalos e alarmes presentes em pelo menos três TAGs.

### Regra de negócio associada ao gráfico

- baixa variação entre TAGs favorece um parâmetro por `Id_Alarme`;
- alta variação exige investigação antes de criar parâmetro por `Id_Alarme + TAG`;
- parâmetros por TAG são último recurso, pois não generalizam para equipamentos novos.
"""
    ),
    code(
        """
tag_alarm_timing = query(
    '''
    WITH gaps AS (
        SELECT TAG, Id_Alarme,
               date_diff('millisecond',
                   lag(Data_Evento) OVER (PARTITION BY TAG, Id_Alarme ORDER BY Data_Evento),
                   Data_Evento
               ) AS gap_ms
        FROM tel
    )
    SELECT TAG, Id_Alarme, count(*) AS intervalos, median(gap_ms) AS mediana_ms
    FROM gaps
    WHERE gap_ms IS NOT NULL AND gap_ms >= 0
    GROUP BY TAG, Id_Alarme
    '''
)
stable_samples = tag_alarm_timing[tag_alarm_timing["intervalos"] >= 100].copy()
between_tags = (
    stable_samples.groupby("Id_Alarme")
    .agg(tags=("TAG", "nunique"), mediana_min_ms=("mediana_ms", "min"),
         mediana_max_ms=("mediana_ms", "max"), mediana_das_tags_ms=("mediana_ms", "median"))
    .reset_index()
)
between_tags = between_tags[between_tags["tags"] >= 3].copy()
between_tags["razao_max_min"] = between_tags["mediana_max_ms"] / between_tags["mediana_min_ms"].clip(lower=1)
display(between_tags.sort_values("razao_max_min", ascending=False).head(40))

fig, axes = plt.subplots(1, 2, figsize=(16, 5))
sns.histplot(data=between_tags, x="razao_max_min", bins=35, ax=axes[0])
axes[0].set(xscale="log", title="Variação da mediana entre TAGs do mesmo alarme", xlabel="Maior mediana / menor mediana")
sns.scatterplot(data=between_tags, x="tags", y="razao_max_min", size="mediana_das_tags_ms", alpha=.7, ax=axes[1])
axes[1].set(yscale="log", title="Variação versus cobertura de equipamentos", xlabel="TAGs", ylabel="Maior / menor mediana")
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 5. Relação entre catálogo e telemetria

As regras são descritas pelo nome `EVENTO`, enquanto a telemetria dispõe de `Id_Alarme` e `Alarme`.
Antes de confrontar cadências com `QTD/TEMPO`, medimos a cobertura do vínculo nominal exato.

### Regra de negócio associada ao gráfico

Uma regra somente pode ser executada automaticamente depois que seu evento estiver vinculado de
forma verificável ao identificador da telemetria. Ausência de correspondência nominal não significa
ausência do evento: pode indicar diferença de nomenclatura ou catálogo.
"""
    ),
    code(
        """
telemetry_names = query("SELECT DISTINCT Id_Alarme, trim(Alarme) AS EVENTO FROM tel")
rule_link = rules.merge(telemetry_names, how="left", on="EVENTO")
coverage = pd.DataFrame({
    "metrica": ["Regras", "Eventos distintos nas regras", "Eventos com correspondência nominal", "Regras vinculadas nominalmente"],
    "valor": [len(rules), rules["EVENTO"].nunique(), rule_link.loc[rule_link["Id_Alarme"].notna(), "EVENTO"].nunique(), rule_link["Id_Alarme"].notna().sum()]
})
display(coverage)

linked_rules = rule_link.merge(alarm_timing, how="left", on="Id_Alarme", suffixes=("_regra", "_telemetria"))
display(
    linked_rules[linked_rules["Id_Alarme"].notna()][
        ["EVENTO", "SITUACAO", "QTD", "TEMPO", "NIVEL", "Id_Alarme", "intervalos", "tags", "mediana_ms", "p90_ms", "p99_ms"]
    ].sort_values(["TEMPO", "QTD"], ascending=False)
)
"""
    ),
    md(
        """
## 6. Hierarquia proposta para o mapa de tempos

Os resultados deste estudo devem orientar uma hierarquia, e não produzir automaticamente um único
limite:

1. parâmetro por `Id_Alarme`, quando houver volume e estabilidade entre equipamentos;
2. parâmetro por família ou tipo, quando o alarme for novo ou tiver poucos dados;
3. parâmetro global como fallback documentado;
4. parâmetro por `Id_Alarme + TAG` somente após evidência de variação persistente e operacionalmente
   explicável.

## Decisões ainda pendentes

- interpretar formalmente se `TEMPO` está em minutos para todas as regras;
- definir o significado executável de “consecutivos”;
- construir e validar o vínculo entre `EVENTO` do catálogo e `Id_Alarme`;
- escolher critérios mínimos de volume e estabilidade para o mapa;
- distinguir silêncio temporário do encerramento real de um episódio;
- validar a hierarquia em equipamentos conhecidos e simular equipamentos novos.

Nenhum limite de episódio é aprovado por este notebook isoladamente.
"""
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, OUTPUT)
print(f"Notebook criado: {OUTPUT}")
