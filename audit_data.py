from pathlib import Path

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "data" / "raw" / "Base"
TEL = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")
AP = str(BASE / "datasets" / "apontamentos" / "desenvolver_apontamentos.parquet")
REPORT = ROOT / "docs" / "auditoria_dados_detalhes.md"


def table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.sql(sql).df()


con = duckdb.connect()
con.execute("SET threads=4")
con.execute(f"CREATE VIEW tel AS SELECT * FROM read_parquet('{TEL}', union_by_name=true)")
con.execute(f"CREATE VIEW ap AS SELECT * FROM read_parquet('{AP}')")

sections = ["# Auditoria dos dados e resultados", ""]

overview = query(
    con,
    """
    SELECT
      count(*) AS registros,
      count(DISTINCT Id_Eventos_Telemetria) AS ids_distintos,
      min(Data_Evento) AS data_min,
      max(Data_Evento) AS data_max,
      count(DISTINCT TAG) AS tags,
      count(DISTINCT Alarme) AS alarmes,
      sum(Is_Dont_Go) AS linhas_dont_go,
      avg(Is_Dont_Go) * 100 AS pct_dont_go
    FROM tel
    """,
)
sections += ["## Telemetria bruta", "", table(overview), ""]

monthly = query(
    con,
    """
    SELECT
      strftime(Data_Evento, '%Y-%m') AS mes,
      count(*) AS registros,
      count(DISTINCT TAG) AS tags,
      sum(Is_Dont_Go) AS linhas_dont_go,
      min(Data_Evento) AS inicio,
      max(Data_Evento) AS fim
    FROM tel
    GROUP BY 1 ORDER BY 1
    """,
)
sections += [table(monthly), ""]

target_quality = query(
    con,
    """
    SELECT
      Is_Dont_Go,
      count(*) AS registros,
      count(DISTINCT Alarme) AS alarmes,
      count(DISTINCT TAG) AS tags
    FROM tel
    GROUP BY 1 ORDER BY 1
    """,
)
sections += ["### Qualidade do target", "", table(target_quality), ""]

duplicates = query(
    con,
    """
    SELECT
      count(*) - count(DISTINCT Id_Eventos_Telemetria) AS ids_repetidos_excedentes,
      count(*) - count(DISTINCT (Data_Evento, TAG, Id_Alarme, Is_Dont_Go)) AS eventos_logicos_repetidos_excedentes
    FROM tel
    """,
)
sections += ["### Duplicidades", "", table(duplicates), ""]

nulls = query(
    con,
    """
    SELECT
      sum(TAG IS NULL) AS tag_nulo,
      sum(Data_Evento IS NULL) AS data_nula,
      sum(Alarme IS NULL) AS alarme_nulo,
      sum(Tipo IS NULL) AS tipo_nulo,
      sum(Criticidade IS NULL) AS criticidade_nula,
      sum(Classe IS NULL) AS classe_nula,
      sum(Is_Dont_Go IS NULL) AS target_nulo
    FROM tel
    """,
)
sections += ["### Nulos em campos usados", "", table(nulls), ""]

tag_corrections = query(
    con,
    """
    SELECT TAG, count(*) AS registros, min(Data_Evento) AS inicio, max(Data_Evento) AS fim,
           count(DISTINCT Tipo) AS tipos, sum(Is_Dont_Go) AS linhas_dont_go
    FROM tel
    WHERE TAG IN ('CA5926', 'CA65926', 'CA5927', 'CA65927')
    GROUP BY TAG ORDER BY TAG
    """,
)
sections += ["### Correções manuais de TAG", "", table(tag_corrections), ""]

excluded = query(
    con,
    """
    WITH marked AS (
      SELECT *,
        CASE
          WHEN TAG = 'PE3798' AND month(Data_Evento)=6 AND day(Data_Evento)=29 THEN 'PE3798/06-29'
          WHEN TAG = 'PE3797' AND month(Data_Evento)=1 AND day(Data_Evento)=12 THEN 'PE3797/01-12'
          WHEN TAG = 'CA65932' AND month(Data_Evento)=3 AND day(Data_Evento)=26 THEN 'CA65932/03-26'
        END AS exclusao
      FROM tel
    )
    SELECT exclusao, count(*) AS registros, sum(Is_Dont_Go) AS linhas_dont_go,
           count(DISTINCT Data_Evento) AS timestamps_distintos,
           count(DISTINCT Alarme) AS alarmes_distintos,
           min(Data_Evento) AS inicio, max(Data_Evento) AS fim
    FROM marked WHERE exclusao IS NOT NULL
    GROUP BY exclusao ORDER BY exclusao
    """,
)
sections += ["## Regras de limpeza usadas nos notebooks", "", "### Três dias expurgados", "", table(excluded), ""]

top_tag_days = query(
    con,
    """
    SELECT TAG, cast(Data_Evento AS DATE) AS dia, count(*) AS registros,
           sum(Is_Dont_Go) AS linhas_dont_go,
           count(DISTINCT Data_Evento) AS timestamps_distintos,
           count(DISTINCT Alarme) AS alarmes_distintos
    FROM tel
    GROUP BY TAG, cast(Data_Evento AS DATE)
    ORDER BY registros DESC
    LIMIT 20
    """,
)
sections += ["### Maiores volumes por equipamento/dia", "", table(top_tag_days), ""]

ap_quality = query(
    con,
    """
    SELECT count(*) AS registros,
           count(DISTINCT Id) AS ids_distintos,
           count(DISTINCT Tag) AS tags,
           min(Inicio) AS inicio_min,
           max(Fim) AS fim_max,
           sum(Inicio IS NULL OR Fim IS NULL) AS datas_nulas,
           sum(Fim < Inicio) AS duracao_negativa,
           sum(Fim = Inicio) AS duracao_zero
    FROM ap
    """,
)
sections += ["## Apontamentos", "", table(ap_quality), ""]

ap_classes = query(
    con,
    """
    SELECT Classe, count(*) AS registros,
           avg(date_diff('second', Inicio, Fim))/60 AS duracao_media_min
    FROM ap GROUP BY Classe ORDER BY registros DESC
    """,
)
sections += [table(ap_classes), ""]

dg = query(
    con,
    """
    SELECT
      CASE WHEN TAG='CA5926' THEN 'CA65926'
           WHEN TAG='CA5927' THEN 'CA65927'
           ELSE TAG END AS TAG_Limpa,
      Data_Evento, Alarme
    FROM tel WHERE Is_Dont_Go=1
    ORDER BY TAG_Limpa, Data_Evento
    """,
)
ap_df = query(con, "SELECT Tag, Inicio, Fim, Classe FROM ap ORDER BY Tag, Inicio")
dg["Data_Evento"] = pd.to_datetime(dg["Data_Evento"]).astype("datetime64[ns]")
ap_df["Inicio"] = pd.to_datetime(ap_df["Inicio"]).astype("datetime64[ns]")
ap_df["Fim"] = pd.to_datetime(ap_df["Fim"]).astype("datetime64[ns]")

next_operating = pd.merge_asof(
    dg.sort_values("Data_Evento"),
    ap_df[ap_df["Classe"] == "Operando"].sort_values("Inicio")[["Tag", "Inicio"]],
    left_on="Data_Evento",
    right_on="Inicio",
    left_by="TAG_Limpa",
    right_by="Tag",
    direction="forward",
)
next_operating["horas_ate_proximo_operando"] = (
    next_operating["Inicio"] - next_operating["Data_Evento"]
).dt.total_seconds() / 3600
valid_dt = next_operating["horas_ate_proximo_operando"].dropna()

dg_sorted = dg.sort_values(["TAG_Limpa", "Data_Evento"]).copy()
dg_sorted["gap_h"] = (
    dg_sorted.groupby("TAG_Limpa")["Data_Evento"].diff().dt.total_seconds() / 3600
)
episode_summary = pd.DataFrame(
    {
        "linhas_dont_go": [len(dg_sorted)],
        "episodios_gap_1h": [(dg_sorted["gap_h"].isna() | (dg_sorted["gap_h"] > 1)).sum()],
        "episodios_gap_8h": [(dg_sorted["gap_h"].isna() | (dg_sorted["gap_h"] > 8)).sum()],
        "mediana_h_ate_proximo_operando": [valid_dt.median()],
        "media_h_ate_proximo_operando": [valid_dt.mean()],
        "sem_proximo_operando": [next_operating["Inicio"].isna().sum()],
    }
)
sections += ["## Auditoria do chamado “downtime real”", "", table(episode_summary), ""]

current_class = con.sql(
    """
    SELECT
      CASE WHEN t.TAG='CA5926' THEN 'CA65926'
           WHEN t.TAG='CA5927' THEN 'CA65927'
           ELSE t.TAG END AS TAG_Limpa,
      t.Data_Evento,
      max(a.Classe) AS classe_no_instante
    FROM tel t
    LEFT JOIN ap a
      ON (CASE WHEN t.TAG='CA5926' THEN 'CA65926'
               WHEN t.TAG='CA5927' THEN 'CA65927'
               ELSE t.TAG END) = a.Tag
     AND t.Data_Evento >= a.Inicio
     AND t.Data_Evento < a.Fim
    WHERE t.Is_Dont_Go=1
    GROUP BY 1, 2
    """
).df()
class_at_alert = (
    current_class["classe_no_instante"]
    .fillna("SEM_APONTAMENTO_NO_INSTANTE")
    .value_counts(dropna=False)
    .rename_axis("classe_no_instante")
    .reset_index(name="linhas_dont_go")
)
sections += ["### Classe operacional no instante do alerta", "", table(class_at_alert), ""]

rules = pd.read_excel(BASE / "Alarmes - Regra de Negocio.xlsx", sheet_name="CMA")
con.register("rules", rules)
rules_summary = query(
    con,
    """
    SELECT count(*) AS regras,
           count(DISTINCT EVENTO) AS eventos,
           count(DISTINCT TIPO) AS tipos,
           count(DISTINCT SITUACAO) AS situacoes,
           count(DISTINCT NIVEL) AS niveis
    FROM rules
    """,
)
sections += ["## Regras de negócio versus target entregue", "", table(rules_summary), ""]

rule_match = query(
    con,
    """
    SELECT
      count(*) AS linhas_dont_go,
      sum(r.EVENTO IS NOT NULL) AS evento_encontrado_nas_regras,
      sum(r.EVENTO IS NULL) AS evento_ausente_das_regras
    FROM tel t
    LEFT JOIN (SELECT DISTINCT EVENTO FROM rules) r ON t.Alarme = r.EVENTO
    WHERE t.Is_Dont_Go=1
    """,
)
sections += [table(rule_match), ""]

REPORT.write_text("\n".join(sections), encoding="utf-8")
print(f"Relatório salvo em {REPORT}")
