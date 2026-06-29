from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "08_Modelo_Com_Mapa_Manual_De_Conceitos.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 08 — Modelo com Mapa Manual de Conceitos

## Objetivo

Testar um primeiro mapa manual pequeno de `conceito_alarme` e `familia_alarme`, construído a partir
dos achados dos notebooks 06 e 07.

## Limite metodológico

Este é um experimento de desenvolvimento. Como os candidatos foram orientados por auditorias dos
erros já observados, inclusive no teste de junho, os resultados deste notebook não devem ser tratados
como validação final independente. A utilidade aqui é medir se o mapa manual reduz falsos positivos,
preserva recall e organiza melhor os alarmes para a próxima rodada.

Para validação final, será necessário congelar o mapa e avaliar em novo período, novo holdout ou
validação temporal posterior.
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
pd.set_option("display.max_rows", 200)

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
BASE = ROOT / "data" / "raw" / "Base"
TEL_GLOB = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")

SEQUENCE_GAP_SECONDS = 60
TOP_ALARM_IDS = 200
TOP_TEXT_CONCEPTS = 200
TOP_MANUAL_CONCEPTS = 120
TOP_MANUAL_FAMILIES = 60
MISSING_DAY = pd.Timestamp("2025-05-31")
LOOP_TAG = "PE3798"
LOOP_DAY = pd.Timestamp("2025-06-29")
LOOP_ALARM_IDS = (1241582851, 1241582848)

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

def manual_concept_family(text):
    t = normalize_alarm_name(text)

    if t.startswith("OEM INTERFACE"):
        return "OEM_INTERFACE", "COMUNICACAO_INTERFACE"
    if t.startswith("RX CHANNEL") and "NOT RECEIVING MESSAGES" in t:
        return "RX_CHANNEL_SEM_MENSAGEM", "COMUNICACAO_INTERFACE"
    if "TIRE TAG TIMEOUT" in t:
        return "TIRE_TAG_TIMEOUT", "PNEUS_MONITORAMENTO"

    if t in {"DIPPER", "CYCLE", "BODY UP", "LOAD"}:
        return f"CICLO_{t.replace(' ', '_')}", "OPERACAO_CARGA_BASCULAMENTO"
    if "PAYLOAD OVERLOAD" in t:
        return "PAYLOAD_OVERLOAD", "OPERACAO_CARGA_BASCULAMENTO"
    if "TRUCK LOAD WEIGHT" in t or "BUCKET LOAD WEIGHT" in t:
        return "LOAD_WEIGHT", "OPERACAO_CARGA_BASCULAMENTO"
    if "BUCKET ANGLE" in t:
        return "BUCKET_ANGLE", "OPERACAO_CARGA_BASCULAMENTO"
    if "HOIST" in t or "LIFT ARMS" in t or "DUMP WHEEL" in t or "ROLLBACK" in t:
        return "LIMITE_MOVIMENTO_CARGA", "OPERACAO_CARGA_BASCULAMENTO"

    if "COOLANT LEVEL" in t or "ARREF" in t:
        return "ARREFECIMENTO_MOTOR", "MOTOR_ARREFECIMENTO"
    if "ENGINE PRELUBE" in t or "OLEO MOTOR" in t:
        return "LUBRIFICACAO_MOTOR", "MOTOR_LUBRIFICACAO"
    if "ENGINE AT HIGH THROTTLE" in t or "ENGINE AT LOW THROTTLE" in t:
        return "REGIME_MOTOR", "MOTOR_OPERACAO"
    if "EXHAUST TEMPERATURE" in t or "TEMP EXAUST" in t:
        return "TEMPERATURA_ESCAPE", "MOTOR_OPERACAO"

    if "PARKING BRAKE" in t or "FREIO" in t or "BRAKE" in t:
        return "SISTEMA_FREIO", "FREIOS"
    if "STEERING" in t or "DIRECAO" in t or "STEER" in t:
        return "SISTEMA_DIRECAO", "DIRECAO"
    if "TRANSMISSION OIL" in t or "DIFFERENTIAL" in t or "FINAL DRIVE" in t:
        return "TREM_FORCA_OLEO_FILTRO", "TREM_FORCA"
    if "SYSTEM VOLTAGE" in t or "VOLTAGE" in t or "VOLTAGEM" in t or "BATTERY" in t:
        return "SISTEMA_ELETRICO_TENSAO", "ELETRICO"
    if "VEHICLE SPEED" in t or "LIMITE DE VELOCIDADE" in t:
        return "VELOCIDADE_EQUIPAMENTO", "OPERACAO_VELOCIDADE"
    if "TESTE OP ENTRADA" in t:
        return "TESTE_OP_ENTRADA", "TESTE_OPERACIONAL"

    return t, "OUTROS"

print(f"Raiz do projeto: {ROOT}")
"""
    ),
    md("## 1. Reconstituição da base congelada"),
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
                   WHEN date_diff('millisecond', evento_anterior, Data_Evento)
                        > {SEQUENCE_GAP_SECONDS * 1000} THEN 1
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

base_audit = query(
    '''
    SELECT
        (SELECT count(*) FROM analytic_events) AS registros_analiticos,
        (SELECT sum(ids_evento_no_grupo - 1) FROM analytic_events) AS duplicatas_retiradas,
        (SELECT sum(Is_Dont_Go) FROM analytic_events) AS linhas_dont_go,
        (SELECT count(*) FROM alarm_sequences) AS sequencias,
        (SELECT sum(is_dont_go) FROM alarm_sequences) AS sequencias_dont_go
    '''
)
base_audit["tempo_s"] = round(time.time() - start, 1)
display(base_audit)
"""
    ),
    md("## 2. Catálogo manual inicial"),
    code(
        """
alarm_catalog = query(
    '''
    SELECT Id_Alarme, any_value(Alarme) AS Alarme, count(*) AS sequencias, sum(is_dont_go) AS sequencias_dont_go
    FROM alarm_sequences
    GROUP BY 1
    ORDER BY sequencias DESC
    '''
)
alarm_catalog["conceito_textual"] = alarm_catalog["Alarme"].map(normalize_alarm_name)
manual = alarm_catalog["Alarme"].map(manual_concept_family)
alarm_catalog["conceito_manual"] = [x[0] for x in manual]
alarm_catalog["familia_manual"] = [x[1] for x in manual]

manual_audit = (
    alarm_catalog.groupby(["familia_manual", "conceito_manual"])
    .agg(
        ids=("Id_Alarme", "nunique"),
        sequencias=("sequencias", "sum"),
        sequencias_dont_go=("sequencias_dont_go", "sum"),
        exemplos=("Alarme", lambda x: " | ".join(sorted(set(map(str, x)))[:4])),
    )
    .reset_index()
    .sort_values(["sequencias_dont_go", "sequencias"], ascending=False)
)
display(manual_audit.head(80))
display(
    alarm_catalog.groupby("familia_manual")
    .agg(ids=("Id_Alarme", "nunique"), sequencias=("sequencias", "sum"), sequencias_dont_go=("sequencias_dont_go", "sum"))
    .reset_index()
    .sort_values("sequencias_dont_go", ascending=False)
)
con.register("alarm_concepts", alarm_catalog[["Id_Alarme", "conceito_textual", "conceito_manual", "familia_manual"]])
"""
    ),
    md("## 3. Janelas e features"),
    code(
        """
con.execute(
    '''
    CREATE OR REPLACE TEMP TABLE sequence_bins AS
    SELECT
        TAG,
        time_bucket(INTERVAL '8 hours', inicio) AS bin_start,
        count(*) AS sequencias_total,
        count(DISTINCT Id_Alarme) AS alarmes_distintos,
        sum(registros_analiticos) AS registros_analiticos,
        sum(registros_brutos_representados) AS registros_brutos_representados,
        avg(duracao_ms) AS duracao_media_ms,
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

con.execute(
    '''
    CREATE OR REPLACE TEMP TABLE sample_grid AS
    WITH tags AS (
        SELECT DISTINCT TAG FROM analytic_events
    ), feature_bins AS (
        SELECT * FROM generate_series(
            TIMESTAMP '2025-01-01 00:00:00',
            TIMESTAMP '2025-06-30 08:00:00',
            INTERVAL '8 hours'
        ) AS t(feature_start)
    )
    SELECT
        tags.TAG,
        feature_start,
        feature_start + INTERVAL '8 hours' AS prediction_time,
        feature_start + INTERVAL '16 hours' AS target_end
    FROM tags CROSS JOIN feature_bins
    '''
)

samples = query(
    f'''
    SELECT
        g.TAG, g.feature_start, g.prediction_time, g.target_end,
        coalesce(f.sequencias_total, 0) AS sequencias_total,
        coalesce(f.alarmes_distintos, 0) AS alarmes_distintos,
        coalesce(f.registros_analiticos, 0) AS registros_analiticos,
        coalesce(f.registros_brutos_representados, 0) AS registros_brutos_representados,
        coalesce(f.duracao_media_ms, 0) AS duracao_media_ms,
        coalesce(f.duracao_max_ms, 0) AS duracao_max_ms,
        coalesce(f.maior_sequencia_registros, 0) AS maior_sequencia_registros,
        coalesce(f.sequencias_com_critico, 0) AS sequencias_com_critico,
        coalesce(f.sequencias_com_activate, 0) AS sequencias_com_activate,
        coalesce(f.sequencias_com_inactive, 0) AS sequencias_com_inactive,
        coalesce(f.sequencias_com_classe_nula, 0) AS sequencias_com_classe_nula,
        coalesce(y.episodios_dont_go, 0) AS episodios_dont_go_target,
        CASE WHEN coalesce(y.episodios_dont_go, 0) > 0 THEN 1 ELSE 0 END AS target,
        CASE
            WHEN CAST(g.feature_start AS DATE) = DATE '{MISSING_DAY.date()}'
              OR CAST(g.prediction_time AS DATE) = DATE '{MISSING_DAY.date()}'
            THEN 0 ELSE 1
        END AS amostra_valida
    FROM sample_grid g
    LEFT JOIN sequence_bins f
      ON g.TAG = f.TAG AND g.feature_start = f.bin_start
    LEFT JOIN sequence_bins y
      ON g.TAG = y.TAG AND g.prediction_time = y.bin_start
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
samples = samples[samples["split"].isin(["treino", "validacao", "teste"])].copy()

base_feature_columns = [
    "sequencias_total", "alarmes_distintos", "registros_analiticos",
    "registros_brutos_representados", "duracao_media_ms", "duracao_max_ms",
    "maior_sequencia_registros", "sequencias_com_critico",
    "sequencias_com_activate", "sequencias_com_inactive",
    "sequencias_com_classe_nula",
]
samples = pd.concat([
    samples,
    pd.DataFrame({
        "feature_has_events": (samples["sequencias_total"] > 0).astype("int8"),
        "prediction_hour_sin": np.sin(2 * np.pi * samples["prediction_time"].dt.hour / 24),
        "prediction_hour_cos": np.cos(2 * np.pi * samples["prediction_time"].dt.hour / 24),
        "prediction_dow_sin": np.sin(2 * np.pi * samples["prediction_time"].dt.dayofweek / 7),
        "prediction_dow_cos": np.cos(2 * np.pi * samples["prediction_time"].dt.dayofweek / 7),
    }, index=samples.index)
], axis=1)
base_feature_columns += ["feature_has_events", "prediction_hour_sin", "prediction_hour_cos", "prediction_dow_sin", "prediction_dow_cos"]
display(samples.groupby(["split", "Tipo"]).agg(amostras=("target", "size"), positivas=("target", "sum"), prevalencia=("target", "mean")).reset_index())
"""
    ),
    code(
        """
def add_top_count_features(samples, key_col, prefix, top_n):
    top_values = query(
        f'''
        SELECT c.{key_col} AS valor, count(*) AS sequencias
        FROM alarm_sequences s
        JOIN alarm_concepts c USING (Id_Alarme)
        WHERE s.inicio < TIMESTAMP '2025-05-01 00:00:00'
        GROUP BY 1
        ORDER BY sequencias DESC, valor
        LIMIT {top_n}
        '''
    )["valor"].tolist()
    name_map = {value: f"{prefix}_{i:03d}" for i, value in enumerate(top_values)}
    long = query(
        f'''
        SELECT
            s.TAG,
            time_bucket(INTERVAL '8 hours', s.inicio) AS feature_start,
            c.{key_col} AS valor,
            count(*) AS sequencias
        FROM alarm_sequences s
        JOIN alarm_concepts c USING (Id_Alarme)
        GROUP BY 1, 2, 3
        '''
    )
    long = long[long["valor"].isin(top_values)].copy()
    wide = (
        long.pivot_table(index=["TAG", "feature_start"], columns="valor", values="sequencias", aggfunc="sum", fill_value=0)
        .rename(columns=name_map)
        .reset_index()
    )
    wide.columns.name = None
    feature_names = [name_map[value] for value in top_values]
    return wide, feature_names, pd.DataFrame({"valor": top_values, "feature": feature_names})

top_alarm_ids = query(
    f'''
    SELECT Id_Alarme, count(*) AS sequencias
    FROM alarm_sequences
    WHERE inicio < TIMESTAMP '2025-05-01 00:00:00'
    GROUP BY 1
    ORDER BY sequencias DESC, Id_Alarme
    LIMIT {TOP_ALARM_IDS}
    '''
)
alarm_ids = top_alarm_ids["Id_Alarme"].astype(int).tolist()
alarm_columns = ",\\n".join(f"sum(CASE WHEN Id_Alarme = {alarm_id} THEN 1 ELSE 0 END) AS alarm_{alarm_id}" for alarm_id in alarm_ids)
alarm_features = query(
    f'''
    SELECT TAG, time_bucket(INTERVAL '8 hours', inicio) AS feature_start,
           {alarm_columns}
    FROM alarm_sequences
    GROUP BY 1, 2
    '''
)
samples = samples.merge(alarm_features, how="left", on=["TAG", "feature_start"])
alarm_feature_names = [f"alarm_{alarm_id}" for alarm_id in alarm_ids]
samples[alarm_feature_names] = samples[alarm_feature_names].fillna(0).astype("int32")

text_wide, text_features, text_lookup = add_top_count_features(samples, "conceito_textual", "textconcept", TOP_TEXT_CONCEPTS)
manual_wide, manual_features, manual_lookup = add_top_count_features(samples, "conceito_manual", "manualconcept", TOP_MANUAL_CONCEPTS)
family_wide, family_features, family_lookup = add_top_count_features(samples, "familia_manual", "manualfamily", TOP_MANUAL_FAMILIES)

for wide, features in [(text_wide, text_features), (manual_wide, manual_features), (family_wide, family_features)]:
    samples = samples.merge(wide, how="left", on=["TAG", "feature_start"])
    samples[features] = samples[features].fillna(0).astype("int32")

display(text_lookup.head(20))
display(manual_lookup.head(40))
display(family_lookup.head(40))
"""
    ),
    md("## 4. Modelos"),
    code(
        """
def get_split(name, columns):
    part = samples[samples["split"] == name].copy()
    return part[columns].astype("float32"), part["target"].astype("int8"), part

def select_threshold(y_true, probability):
    scores = pd.DataFrame([
        {
            "threshold": threshold,
            "f2": fbeta_score(y_true, probability >= threshold, beta=2, zero_division=0),
            "precision": precision_score(y_true, probability >= threshold, zero_division=0),
            "recall": recall_score(y_true, probability >= threshold, zero_division=0),
        }
        for threshold in np.linspace(0.01, 0.99, 197)
    ])
    best = scores.sort_values(["f2", "precision", "threshold"], ascending=[False, False, False]).iloc[0]["threshold"]
    return float(best)

def metric_row(model_name, split, y_true, probability, threshold):
    pred = (probability >= threshold).astype(int)
    return {
        "modelo": model_name,
        "split": split,
        "threshold": threshold,
        "amostras": len(y_true),
        "positivas": int(y_true.sum()),
        "pr_auc": average_precision_score(y_true, probability),
        "roc_auc": roc_auc_score(y_true, probability),
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

def fit_rf(model_name, columns):
    X_train, y_train, _ = get_split("treino", columns)
    X_val, y_val, _ = get_split("validacao", columns)
    X_test, y_test, test_meta = get_split("teste", columns)
    model = RandomForestClassifier(
        n_estimators=400,
        max_features="sqrt",
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    val_prob = model.predict_proba(X_val)[:, 1]
    threshold = select_threshold(y_val, val_prob)
    test_prob = model.predict_proba(X_test)[:, 1]
    rows = [
        metric_row(model_name, "validacao", y_val, val_prob, threshold),
        metric_row(model_name, "teste", y_test, test_prob, threshold),
    ]
    pred = test_meta[["TAG", "Tipo", "Tag_Frota", "feature_start", "prediction_time", "target"]].copy()
    pred["probabilidade"] = test_prob
    pred["predito"] = (test_prob >= threshold).astype("int8")
    pred["modelo"] = model_name
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
    return pd.DataFrame(rows), pred, model

feature_sets = {
    "RF_ids": base_feature_columns + alarm_feature_names,
    "RF_ids_textual": base_feature_columns + alarm_feature_names + text_features,
    "RF_ids_manual_concepts": base_feature_columns + alarm_feature_names + manual_features,
    "RF_ids_manual_family": base_feature_columns + alarm_feature_names + family_features,
    "RF_ids_manual_both": base_feature_columns + alarm_feature_names + manual_features + family_features,
}

metrics_parts = []
prediction_parts = []
models = {}
for name, columns in feature_sets.items():
    print(f"Treinando {name}: {len(columns)} features")
    m, p, model = fit_rf(name, columns)
    metrics_parts.append(m)
    prediction_parts.append(p)
    models[name] = model

metrics = pd.concat(metrics_parts, ignore_index=True)
predictions = pd.concat(prediction_parts, ignore_index=True)
display(metrics.sort_values(["split", "f2"], ascending=[True, False]))
"""
    ),
    md("## 5. Comparação no teste"),
    code(
        """
test_metrics = metrics[metrics["split"] == "teste"].copy()
display(
    test_metrics[[
        "modelo", "threshold", "pr_auc", "precision", "recall", "f2",
        "predicoes_positivas", "TP", "FP", "FN", "TN"
    ]].sort_values("f2", ascending=False)
)

type_rows = []
for (model_name, tipo), part in predictions.groupby(["modelo", "Tipo"], dropna=False):
    y = part["target"].to_numpy()
    pred = part["predito"].to_numpy()
    type_rows.append({
        "modelo": model_name,
        "Tipo": tipo,
        "amostras": len(part),
        "positivas": int(y.sum()),
        "predicoes_positivas": int(pred.sum()),
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f2": fbeta_score(y, pred, beta=2, zero_division=0),
        "FP": int(((y == 0) & (pred == 1)).sum()),
        "FN": int(((y == 1) & (pred == 0)).sum()),
    })
type_metrics = pd.DataFrame(type_rows)
display(type_metrics.sort_values(["Tipo", "f2"], ascending=[True, False]))

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
sns.barplot(data=test_metrics.sort_values("f2", ascending=False), x="f2", y="modelo", ax=axes[0], color="#4C78A8")
axes[0].set(title="F2 no teste")
sns.barplot(data=test_metrics.sort_values("FP", ascending=True), x="FP", y="modelo", ax=axes[1], color="#F58518")
axes[1].set(title="Falsos positivos no teste")
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 6. Leitura auditada

Critérios:

- se o mapa manual reduzir falsos positivos mantendo recall próximo ao modelo textual, ele merece
  refinamento;
- se piorar F2 ou recall, manter conceitos textuais por enquanto;
- se escavadeiras continuarem com recall zero, o problema segue sendo target escasso, não apenas
  representação de alarmes;
- qualquer ganho aqui é exploratório, pois o mapa foi orientado por análise pós-teste.
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
