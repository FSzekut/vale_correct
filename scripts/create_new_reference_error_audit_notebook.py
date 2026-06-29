from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "12_Auditoria_Nova_Referencia_24h8h.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 12 — Auditoria da Nova Referência 24h/8h

## Objetivo

Auditar falsos positivos e falsos negativos da nova referência técnica:

> gap 900s, observação 24h, horizonte 8h, Random Forest com IDs + conceitos textuais.

Comparação principal:

- baseline histórico: gap 60s, observação 8h, horizonte 8h, `RF_ids`;
- nova referência: gap 900s, observação 24h, horizonte 8h, `RF_ids_textual`.

## Limites

- `Is_Dont_Go` continua sendo target provisório, não falha confirmada;
- os resultados com buckets de 8h servem para comparar cenários de desenvolvimento;
- o teste não participa da seleção de threshold;
- a auditoria orienta próximos experimentos, não produção.
"""
    ),
    code(
        """
from pathlib import Path
import re
import time
import unicodedata

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from IPython.display import display
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score, balanced_accuracy_score, f1_score, fbeta_score,
    precision_score, recall_score, roc_auc_score,
)

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 250)
pd.set_option("display.max_rows", 250)

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
BASE = ROOT / "data" / "raw" / "Base"
TEL_GLOB = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")

TOP_ALARM_IDS = 200
TOP_TEXT_CONCEPTS = 200
LOOP_TAG = "PE3798"
LOOP_DAY = pd.Timestamp("2025-06-29")
LOOP_ALARM_IDS = (1241582851, 1241582848)
MISSING_START = pd.Timestamp("2025-05-31 00:00:00")
MISSING_END = pd.Timestamp("2025-06-01 00:00:00")

SCENARIOS = [
    {
        "cenario": "baseline_60s_8h8h_ids",
        "gap_s": 60,
        "observacao_h": 8,
        "horizonte_h": 8,
        "use_text_concepts": False,
    },
    {
        "cenario": "referencia_900s_24h8h_ids_textual",
        "gap_s": 900,
        "observacao_h": 24,
        "horizonte_h": 8,
        "use_text_concepts": True,
    },
]

con = duckdb.connect()
con.execute("SET threads=4")
con.execute("SET preserve_insertion_order=false")
con.execute(f"CREATE OR REPLACE VIEW tel AS SELECT * FROM read_parquet('{TEL_GLOB}', union_by_name=true)")

def query(sql):
    return con.sql(sql).df()

def normalize_alarm_name(value):
    if pd.isna(value):
        return "SEM_DESCRICAO"
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\\s*\\(L-?\\d+\\)\\s*$", "", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text or "SEM_DESCRICAO"

def is_excavator(series):
    return series.fillna("").str.contains("ESCAV", case=False, regex=True)

print(f"Raiz do projeto: {ROOT}")
"""
    ),
    md("## 1. Camada analítica congelada"),
    code(
        """
start = time.time()
con.execute(
    f'''
    CREATE OR REPLACE TEMP TABLE analytic_events AS
    SELECT
        min(Id_Eventos_Telemetria) AS Id_Eventos_Telemetria_referencia,
        Data_Evento, Inicio_Turno, Fim_Turno, Dia, Localidade, TAG, Tag_Frota, Tipo,
        Nome_Operador_Anon, Matricula_Operador_Hash, Id_Alarme, Alarme,
        Id_Criticidade, Criticidade, Valor, Classe, Is_Dont_Go,
        count(*) AS ids_evento_no_grupo
    FROM tel
    WHERE NOT (
        TAG = '{LOOP_TAG}'
        AND CAST(Data_Evento AS DATE) = DATE '{LOOP_DAY.date()}'
        AND Id_Alarme IN {LOOP_ALARM_IDS}
    )
    GROUP BY
        Data_Evento, Inicio_Turno, Fim_Turno, Dia, Localidade, TAG, Tag_Frota, Tipo,
        Nome_Operador_Anon, Matricula_Operador_Hash, Id_Alarme, Alarme,
        Id_Criticidade, Criticidade, Valor, Classe, Is_Dont_Go
    '''
)

base_audit = query(
    '''
    SELECT
        count(*) AS registros_analiticos,
        sum(ids_evento_no_grupo - 1) AS duplicatas_retiradas,
        sum(Is_Dont_Go) AS linhas_dont_go
    FROM analytic_events
    '''
)
base_audit["tempo_s"] = round(time.time() - start, 1)
display(base_audit)
"""
    ),
    md("## 2. Funções"),
    code(
        """
def build_sequences(gap_s):
    con.execute(
        f'''
        CREATE OR REPLACE TEMP TABLE alarm_sequences AS
        WITH ordered AS (
            SELECT *,
                   lag(Data_Evento) OVER (
                       PARTITION BY TAG, Id_Alarme ORDER BY Data_Evento, Id_Eventos_Telemetria_referencia
                   ) AS evento_anterior
            FROM analytic_events
        ), flagged AS (
            SELECT *,
                   CASE
                       WHEN evento_anterior IS NULL THEN 1
                       WHEN date_diff('millisecond', evento_anterior, Data_Evento) > {gap_s * 1000} THEN 1
                       ELSE 0
                   END AS nova_sequencia
            FROM ordered
        ), numbered AS (
            SELECT *,
                   sum(nova_sequencia) OVER (
                       PARTITION BY TAG, Id_Alarme
                       ORDER BY Data_Evento, Id_Eventos_Telemetria_referencia
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                   ) AS numero_sequencia
            FROM flagged
        )
        SELECT
            TAG, any_value(Tag_Frota) AS Tag_Frota, any_value(Tipo) AS Tipo,
            Id_Alarme, any_value(Alarme) AS Alarme,
            numero_sequencia,
            min(Data_Evento) AS inicio,
            max(Data_Evento) AS fim,
            time_bucket(INTERVAL '8 hours', min(Data_Evento)) AS bin_start,
            date_diff('millisecond', min(Data_Evento), max(Data_Evento)) AS duracao_ms,
            count(*) AS registros_analiticos,
            sum(ids_evento_no_grupo) AS registros_brutos_representados,
            max(Is_Dont_Go) AS is_dont_go,
            max(CASE WHEN Id_Criticidade = 1 THEN 1 ELSE 0 END) AS possui_critico,
            max(CASE WHEN Classe = 'Activate' THEN 1 ELSE 0 END) AS possui_activate,
            max(CASE WHEN Classe = 'Inactive' THEN 1 ELSE 0 END) AS possui_inactive,
            max(CASE WHEN Classe IS NULL THEN 1 ELSE 0 END) AS possui_classe_nula
        FROM numbered
        GROUP BY TAG, Id_Alarme, numero_sequencia
        '''
    )
    return query(
        '''
        SELECT
            count(*) AS sequencias,
            sum(is_dont_go) AS sequencias_dont_go,
            avg(registros_analiticos) AS registros_por_sequencia_media,
            max(registros_analiticos) AS maior_sequencia
        FROM alarm_sequences
        '''
    )

def create_catalog():
    catalog = query(
        '''
        SELECT Id_Alarme, any_value(Alarme) AS Alarme, count(*) AS sequencias
        FROM alarm_sequences
        GROUP BY 1
        ORDER BY sequencias DESC
        '''
    )
    catalog["conceito_textual"] = catalog["Alarme"].map(normalize_alarm_name)
    con.register("alarm_concepts", catalog[["Id_Alarme", "conceito_textual"]])
    return catalog

def build_sample_grid(observation_h, horizon_h):
    con.execute(
        f'''
        CREATE OR REPLACE TEMP TABLE sample_grid AS
        WITH tags AS (
            SELECT DISTINCT TAG FROM analytic_events
        ), prediction_bins AS (
            SELECT * FROM generate_series(
                TIMESTAMP '2025-01-01 00:00:00' + INTERVAL '{observation_h} hours',
                TIMESTAMP '2025-07-01 00:00:00' - INTERVAL '{horizon_h} hours',
                INTERVAL '8 hours'
            ) AS t(prediction_time)
        )
        SELECT
            row_number() OVER () AS sample_id,
            tags.TAG,
            prediction_time - INTERVAL '{observation_h} hours' AS feature_start,
            prediction_time,
            prediction_time + INTERVAL '{horizon_h} hours' AS target_end
        FROM tags CROSS JOIN prediction_bins
        WHERE prediction_time - INTERVAL '{observation_h} hours' >= TIMESTAMP '2025-01-01 00:00:00'
        '''
    )

def build_bins():
    con.execute(
        '''
        CREATE OR REPLACE TEMP TABLE sequence_bins AS
        SELECT
            TAG, bin_start,
            count(*) AS sequencias_total,
            count(DISTINCT Id_Alarme) AS alarmes_distintos,
            sum(registros_analiticos) AS registros_analiticos,
            sum(registros_brutos_representados) AS registros_brutos_representados,
            sum(duracao_ms) AS duracao_soma_ms,
            max(duracao_ms) AS duracao_max_ms,
            max(registros_analiticos) AS maior_sequencia_registros,
            sum(possui_critico) AS sequencias_com_critico,
            sum(possui_activate) AS sequencias_com_activate,
            sum(possui_inactive) AS sequencias_com_inactive,
            sum(possui_classe_nula) AS sequencias_com_classe_nula,
            sum(is_dont_go) AS episodios_dont_go
        FROM alarm_sequences
        GROUP BY 1, 2
        '''
    )

def build_samples():
    samples = query(
        f'''
        WITH feature_agg AS (
            SELECT
                g.sample_id,
                coalesce(sum(b.sequencias_total), 0) AS sequencias_total,
                coalesce(sum(b.alarmes_distintos), 0) AS alarmes_distintos,
                coalesce(sum(b.registros_analiticos), 0) AS registros_analiticos,
                coalesce(sum(b.registros_brutos_representados), 0) AS registros_brutos_representados,
                CASE
                    WHEN coalesce(sum(b.sequencias_total), 0) > 0
                    THEN coalesce(sum(b.duracao_soma_ms), 0) / sum(b.sequencias_total)
                    ELSE 0
                END AS duracao_media_ms,
                coalesce(max(b.duracao_max_ms), 0) AS duracao_max_ms,
                coalesce(max(b.maior_sequencia_registros), 0) AS maior_sequencia_registros,
                coalesce(sum(b.sequencias_com_critico), 0) AS sequencias_com_critico,
                coalesce(sum(b.sequencias_com_activate), 0) AS sequencias_com_activate,
                coalesce(sum(b.sequencias_com_inactive), 0) AS sequencias_com_inactive,
                coalesce(sum(b.sequencias_com_classe_nula), 0) AS sequencias_com_classe_nula
            FROM sample_grid g
            LEFT JOIN sequence_bins b
              ON b.TAG = g.TAG
             AND b.bin_start >= g.feature_start
             AND b.bin_start < g.prediction_time
            GROUP BY 1
        ), target_agg AS (
            SELECT
                g.sample_id,
                coalesce(sum(b.episodios_dont_go), 0) AS episodios_dont_go_target
            FROM sample_grid g
            LEFT JOIN sequence_bins b
              ON b.TAG = g.TAG
             AND b.bin_start >= g.prediction_time
             AND b.bin_start < g.target_end
            GROUP BY 1
        )
        SELECT
            g.TAG, g.feature_start, g.prediction_time, g.target_end,
            f.* EXCLUDE(sample_id),
            y.episodios_dont_go_target,
            CASE WHEN y.episodios_dont_go_target > 0 THEN 1 ELSE 0 END AS target,
            CASE
                WHEN g.feature_start < TIMESTAMP '{MISSING_END}'
                 AND g.target_end > TIMESTAMP '{MISSING_START}'
                THEN 0 ELSE 1
            END AS amostra_valida
        FROM sample_grid g
        JOIN feature_agg f USING(sample_id)
        JOIN target_agg y USING(sample_id)
        ORDER BY g.prediction_time, g.TAG
        '''
    )
    samples = samples[samples["amostra_valida"] == 1].copy()
    tag_profile = query(
        '''
        SELECT TAG, any_value(Tipo) AS Tipo, any_value(Tag_Frota) AS Tag_Frota
        FROM analytic_events
        GROUP BY 1
        '''
    )
    samples = samples.merge(tag_profile, how="left", on="TAG")
    samples = samples.assign(split=np.select(
        [
            samples["prediction_time"] < pd.Timestamp("2025-05-01"),
            samples["prediction_time"] < pd.Timestamp("2025-05-31"),
            samples["prediction_time"] >= pd.Timestamp("2025-06-01"),
        ],
        ["treino", "validacao", "teste"],
        default="fora_do_split",
    ))
    return samples[samples["split"].isin(["treino", "validacao", "teste"])].copy()
"""
    ),
    code(
        """
def add_id_features(samples):
    top_ids = query(
        f'''
        SELECT Id_Alarme, count(*) AS sequencias
        FROM alarm_sequences
        WHERE inicio < TIMESTAMP '2025-05-01 00:00:00'
        GROUP BY 1
        ORDER BY sequencias DESC, Id_Alarme
        LIMIT {TOP_ALARM_IDS}
        '''
    )["Id_Alarme"].astype(int).tolist()
    expr = ",\\n".join(
        f"sum(CASE WHEN Id_Alarme = {alarm_id} THEN 1 ELSE 0 END) AS alarm_{alarm_id}"
        for alarm_id in top_ids
    )
    con.execute(
        f'''
        CREATE OR REPLACE TEMP TABLE alarm_bin_features AS
        SELECT TAG, bin_start, {expr}
        FROM alarm_sequences
        GROUP BY 1, 2
        '''
    )
    sum_expr = ", ".join(
        f"coalesce(sum(b.alarm_{alarm_id}), 0) AS alarm_{alarm_id}" for alarm_id in top_ids
    )
    wide = query(
        f'''
        SELECT g.TAG, g.feature_start, {sum_expr}
        FROM sample_grid g
        LEFT JOIN alarm_bin_features b
          ON b.TAG = g.TAG
         AND b.bin_start >= g.feature_start
         AND b.bin_start < g.prediction_time
        GROUP BY 1, 2
        '''
    )
    features = [f"alarm_{alarm_id}" for alarm_id in top_ids]
    samples = samples.merge(wide, how="left", on=["TAG", "feature_start"])
    samples[features] = samples[features].fillna(0).astype("int32")
    return samples, features

def add_text_features(samples):
    top = query(
        f'''
        SELECT c.conceito_textual AS valor, count(*) AS sequencias
        FROM alarm_sequences s
        JOIN alarm_concepts c USING(Id_Alarme)
        WHERE s.inicio < TIMESTAMP '2025-05-01 00:00:00'
        GROUP BY 1
        ORDER BY sequencias DESC, valor
        LIMIT {TOP_TEXT_CONCEPTS}
        '''
    )
    values = top["valor"].tolist()
    name_map = {value: f"textconcept_{i:03d}" for i, value in enumerate(values)}
    def lit(value):
        return "'" + str(value).replace("'", "''") + "'"
    expr = ",\\n".join(
        f"sum(CASE WHEN c.conceito_textual = {lit(value)} THEN 1 ELSE 0 END) AS {name_map[value]}"
        for value in values
    )
    con.execute(
        f'''
        CREATE OR REPLACE TEMP TABLE text_bin_features AS
        SELECT s.TAG, s.bin_start, {expr}
        FROM alarm_sequences s
        LEFT JOIN alarm_concepts c USING(Id_Alarme)
        GROUP BY 1, 2
        '''
    )
    sum_expr = ", ".join(
        f"coalesce(sum(b.{name_map[value]}), 0) AS {name_map[value]}" for value in values
    )
    wide = query(
        f'''
        SELECT g.TAG, g.feature_start, {sum_expr}
        FROM sample_grid g
        LEFT JOIN text_bin_features b
          ON b.TAG = g.TAG
         AND b.bin_start >= g.feature_start
         AND b.bin_start < g.prediction_time
        GROUP BY 1, 2
        '''
    )
    features = [name_map[value] for value in values]
    samples = samples.merge(wide, how="left", on=["TAG", "feature_start"])
    samples[features] = samples[features].fillna(0).astype("int32")
    return samples, features

def add_base_features(samples):
    samples = pd.concat([
        samples,
        pd.DataFrame({
            "feature_has_events": (samples["sequencias_total"] > 0).astype("int8"),
            "prediction_hour_sin": np.sin(2 * np.pi * samples["prediction_time"].dt.hour / 24),
            "prediction_hour_cos": np.cos(2 * np.pi * samples["prediction_time"].dt.hour / 24),
            "prediction_dow_sin": np.sin(2 * np.pi * samples["prediction_time"].dt.dayofweek / 7),
            "prediction_dow_cos": np.cos(2 * np.pi * samples["prediction_time"].dt.dayofweek / 7),
        }, index=samples.index)
    ], axis=1).copy()
    base = [
        "sequencias_total", "alarmes_distintos", "registros_analiticos",
        "registros_brutos_representados", "duracao_media_ms", "duracao_max_ms",
        "maior_sequencia_registros", "sequencias_com_critico",
        "sequencias_com_activate", "sequencias_com_inactive",
        "sequencias_com_classe_nula", "feature_has_events",
        "prediction_hour_sin", "prediction_hour_cos",
        "prediction_dow_sin", "prediction_dow_cos",
    ]
    return samples, base
"""
    ),
    code(
        """
def select_threshold(y_true, probability):
    rows = []
    for threshold in np.linspace(0.01, 0.99, 197):
        pred = probability >= threshold
        rows.append({
            "threshold": threshold,
            "f2": fbeta_score(y_true, pred, beta=2, zero_division=0),
            "precision": precision_score(y_true, pred, zero_division=0),
            "recall": recall_score(y_true, pred, zero_division=0),
        })
    scores = pd.DataFrame(rows)
    best = scores.sort_values(["f2", "precision", "threshold"], ascending=[False, False, False]).iloc[0]
    return float(best["threshold"])

def metric_row(cenario, split, y_true, prob, threshold, extra):
    pred = (prob >= threshold).astype(int)
    row = {
        "cenario": cenario,
        "split": split,
        "threshold": threshold,
        "amostras": len(y_true),
        "positivas": int(y_true.sum()),
        "pr_auc": average_precision_score(y_true, prob),
        "roc_auc": roc_auc_score(y_true, prob),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "f2": fbeta_score(y_true, pred, beta=2, zero_division=0),
        "balanced_accuracy": balanced_accuracy_score(y_true, pred),
        "predicoes_positivas": int(pred.sum()),
        "TP": int(((y_true == 1) & (pred == 1)).sum()),
        "FP": int(((y_true == 0) & (pred == 1)).sum()),
        "FN": int(((y_true == 1) & (pred == 0)).sum()),
        "TN": int(((y_true == 0) & (pred == 0)).sum()),
    }
    row.update(extra)
    return row

def fit_model(samples, features, cenario, extra):
    train = samples[samples["split"] == "treino"]
    val = samples[samples["split"] == "validacao"]
    test = samples[samples["split"] == "teste"]
    model = RandomForestClassifier(
        n_estimators=300,
        max_features="sqrt",
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[features].astype("float32"), train["target"].astype("int8"))
    val_prob = model.predict_proba(val[features].astype("float32"))[:, 1]
    threshold = select_threshold(val["target"].astype("int8"), val_prob)
    test_prob = model.predict_proba(test[features].astype("float32"))[:, 1]
    metrics = pd.DataFrame([
        metric_row(cenario, "validacao", val["target"].astype("int8"), val_prob, threshold, extra),
        metric_row(cenario, "teste", test["target"].astype("int8"), test_prob, threshold, extra),
    ])
    pred = test[["TAG", "Tipo", "Tag_Frota", "feature_start", "prediction_time", "target_end", "target"]].copy()
    pred["cenario"] = cenario
    pred["probabilidade"] = test_prob
    pred["predito"] = (test_prob >= threshold).astype("int8")
    pred["erro"] = np.select(
        [
            (pred["target"] == 1) & (pred["predito"] == 1),
            (pred["target"] == 0) & (pred["predito"] == 1),
            (pred["target"] == 1) & (pred["predito"] == 0),
            (pred["target"] == 0) & (pred["predito"] == 0),
        ],
        ["TP", "FP", "FN", "TN"],
        default="indefinido",
    )
    return metrics, pred

def summarize_group(df, group_cols):
    out = (
        df.assign(
            TP=(df["erro"] == "TP").astype(int),
            FP=(df["erro"] == "FP").astype(int),
            FN=(df["erro"] == "FN").astype(int),
            TN=(df["erro"] == "TN").astype(int),
        )
        .groupby(group_cols, dropna=False)
        .agg(
            amostras=("target", "size"),
            positivos_reais=("target", "sum"),
            positivos_previstos=("predito", "sum"),
            TP=("TP", "sum"),
            FP=("FP", "sum"),
            FN=("FN", "sum"),
            TN=("TN", "sum"),
            prob_media=("probabilidade", "mean"),
            prob_p90=("probabilidade", lambda x: x.quantile(.90)),
        )
        .reset_index()
    )
    out["precision"] = out["TP"] / (out["TP"] + out["FP"]).replace(0, np.nan)
    out["recall"] = out["TP"] / (out["TP"] + out["FN"]).replace(0, np.nan)
    out["taxa_fp"] = out["FP"] / (out["FP"] + out["TN"]).replace(0, np.nan)
    out["prevalencia"] = out["positivos_reais"] / out["amostras"]
    return out
"""
    ),
    md("## 3. Treino dos cenários"),
    code(
        """
all_metrics = []
all_predictions = []
scenario_audits = []

for cfg in SCENARIOS:
    print(f"Executando {cfg['cenario']}")
    start = time.time()
    seq_audit = build_sequences(cfg["gap_s"])
    create_catalog()
    build_sample_grid(cfg["observacao_h"], cfg["horizonte_h"])
    build_bins()
    samples = build_samples()
    samples, base_features = add_base_features(samples)
    samples, id_features = add_id_features(samples)
    feature_columns = base_features + id_features
    if cfg["use_text_concepts"]:
        samples, text_features = add_text_features(samples)
        feature_columns = feature_columns + text_features
    metrics, pred = fit_model(
        samples,
        feature_columns,
        cfg["cenario"],
        {
            "gap_s": cfg["gap_s"],
            "observacao_h": cfg["observacao_h"],
            "horizonte_h": cfg["horizonte_h"],
            "features": len(feature_columns),
            "sequencias": int(seq_audit.loc[0, "sequencias"]),
            "sequencias_dont_go": int(seq_audit.loc[0, "sequencias_dont_go"]),
        },
    )
    metrics["tempo_s"] = round(time.time() - start, 1)
    all_metrics.append(metrics)
    all_predictions.append(pred)
    split_audit = (
        samples.groupby(["split", "Tipo"], dropna=False)
        .agg(amostras=("target", "size"), positivas=("target", "sum"), prevalencia=("target", "mean"))
        .reset_index()
    )
    split_audit["cenario"] = cfg["cenario"]
    scenario_audits.append(split_audit)

metrics = pd.concat(all_metrics, ignore_index=True)
predictions = pd.concat(all_predictions, ignore_index=True)
scenario_audits = pd.concat(scenario_audits, ignore_index=True)

display(scenario_audits)
display(metrics.sort_values(["split", "f2"], ascending=[True, False]))
"""
    ),
    md("## 4. Comparação geral"),
    code(
        """
test_metrics = metrics[metrics["split"] == "teste"].copy()
display(test_metrics[[
    "cenario", "gap_s", "observacao_h", "horizonte_h", "threshold",
    "pr_auc", "precision", "recall", "f2", "TP", "FP", "FN", "TN", "features", "tempo_s"
]])

compare = test_metrics.set_index("cenario")
if set(compare.index) == {c["cenario"] for c in SCENARIOS}:
    old = compare.loc["baseline_60s_8h8h_ids"]
    new = compare.loc["referencia_900s_24h8h_ids_textual"]
    delta = pd.DataFrame([{
        "delta_pr_auc": new["pr_auc"] - old["pr_auc"],
        "delta_precision": new["precision"] - old["precision"],
        "delta_recall": new["recall"] - old["recall"],
        "delta_f2": new["f2"] - old["f2"],
        "delta_TP": new["TP"] - old["TP"],
        "delta_FP": new["FP"] - old["FP"],
        "delta_FN": new["FN"] - old["FN"],
        "delta_TN": new["TN"] - old["TN"],
    }])
    display(delta)
"""
    ),
    md("## 5. Auditoria por tipo e TAG"),
    code(
        """
type_audit = summarize_group(predictions, ["cenario", "Tipo"])
display(type_audit.sort_values(["cenario", "FN"], ascending=[True, False]))

tag_audit = summarize_group(predictions, ["cenario", "TAG", "Tipo", "Tag_Frota"])
print("TAGs com mais FN por cenário")
display(tag_audit.sort_values(["cenario", "FN", "positivos_reais"], ascending=[True, False, False]).groupby("cenario").head(15))
print("TAGs com mais FP por cenário")
display(tag_audit.sort_values(["cenario", "FP", "positivos_previstos"], ascending=[True, False, False]).groupby("cenario").head(15))

fig, axes = plt.subplots(1, 2, figsize=(16, 6))
top_fn = tag_audit.sort_values(["cenario", "FN"], ascending=[True, False]).groupby("cenario").head(10)
sns.barplot(data=top_fn, x="FN", y="TAG", hue="cenario", ax=axes[0])
axes[0].set(title="Top TAGs por falso negativo")
top_fp = tag_audit.sort_values(["cenario", "FP"], ascending=[True, False]).groupby("cenario").head(10)
sns.barplot(data=top_fp, x="FP", y="TAG", hue="cenario", ax=axes[1])
axes[1].set(title="Top TAGs por falso positivo")
plt.tight_layout()
plt.show()
"""
    ),
    md("## 6. Auditoria temporal e por probabilidade"),
    code(
        """
predictions["data"] = predictions["prediction_time"].dt.date
predictions["semana"] = predictions["prediction_time"].dt.to_period("W").astype(str)
predictions["hora"] = predictions["prediction_time"].dt.hour

daily_audit = summarize_group(predictions, ["cenario", "data"])
week_audit = summarize_group(predictions, ["cenario", "semana"])
hour_audit = summarize_group(predictions, ["cenario", "hora"])
display(daily_audit.sort_values(["cenario", "FN"], ascending=[True, False]).groupby("cenario").head(10))
display(week_audit)
display(hour_audit)

prob_audit = (
    predictions.assign(faixa_probabilidade=pd.cut(predictions["probabilidade"], np.linspace(0, 1, 11), include_lowest=True))
    .groupby(["cenario", "faixa_probabilidade"], observed=False)
    .agg(amostras=("target", "size"), positivos=("target", "sum"), taxa_positiva=("target", "mean"))
    .reset_index()
)
display(prob_audit)
"""
    ),
    md("## 7. Drill down de casos"),
    code(
        """
for cenario in predictions["cenario"].unique():
    part = predictions[predictions["cenario"] == cenario]
    print(f"\\n=== {cenario} ===")
    print("FN de maior probabilidade")
    display(part[part["erro"] == "FN"].sort_values("probabilidade", ascending=False).head(20))
    print("FN de menor probabilidade")
    display(part[part["erro"] == "FN"].sort_values("probabilidade", ascending=True).head(20))
    print("FP de maior probabilidade")
    display(part[part["erro"] == "FP"].sort_values("probabilidade", ascending=False).head(20))
"""
    ),
    md(
        """
## 8. Leitura auditada

Critérios:

- se a nova referência reduz FP e mantém recall, ela substitui o baseline histórico como base de
  desenvolvimento;
- se melhora apenas por mudar prevalência ou target, registrar essa diferença explicitamente;
- escavadeiras continuam exigindo leitura separada por escassez de positivos;
- próximos experimentos devem partir da nova referência apenas se os erros residuais forem
  compreensíveis e documentados.
"""
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3 (.venv)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, OUTPUT)
print(f"Notebook criado: {OUTPUT}")
