from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "19_Modelos_Por_Tipo_Equipamento.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 19 — Modelos por Tipo de Equipamento

## Objetivo

Comparar o modelo misto atual contra modelos treinados por tipo de equipamento.

Este notebook parte das evidências dos notebooks 17 e 18:

- XGBoost, LightGBM e CatBoost já foram testados, além de RandomForest;
- melhor candidato econômico até aqui: `multijanela_core_ids_textual + CatBoost`;
- faixa robusta do CatBoost multijanela: 0,410-0,490;
- caminhões concentram o valor operacional e têm volume suficiente;
- escavadeiras têm poucos eventos positivos e devem ser tratadas como experimento de baixa confiança.

Mantém constantes:

- target: episódio futuro `Is_Dont_Go`;
- limpeza analítica;
- gap 900s;
- observação 24h;
- horizonte 8h;
- calibração sigmoide;
- função econômica com `p_acao_confirmada = 0,655` para caminhões.

## Splits temporais

Foram usados três cortes rolantes:

| Split | Treino base | Calibração | Threshold | Teste |
|---|---|---|---|---|
| S1 | jan | fev | mar | abr |
| S2 | jan-fev | mar | abr | mai |
| S3 | jan-mar | abr | mai | jun |

## Controle de vazamento

O vocabulário de IDs e conceitos é selecionado apenas em janeiro, o menor período de treino. Isso é
conservador para S2/S3, mas garante que nenhum mês futuro entre na seleção de features.

## Limites

- comparação econômica ainda é simulação, não ROI observado;
- `Manutenção` é proxy para `p_acao_confirmada`, não causalidade;
- hiperparâmetros são conservadores e fixos, sem tuning por teste.
- modelos de escavadeira são treinados apenas como parâmetro comparativo;
- qualquer resultado de escavadeira deve ser lido como baixa confiança por escassez de positivos.
"""
    ),
    code(
        """
from pathlib import Path
import re
import time
import unicodedata
import warnings

import catboost as cb
import duckdb
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import xgboost as xgb
from IPython.display import display
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, balanced_accuracy_score, brier_score_loss,
    fbeta_score, precision_score, recall_score, roc_auc_score,
)

warnings.filterwarnings("ignore", category=UserWarning)
sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 300)
pd.set_option("display.max_rows", 250)

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
BASE = ROOT / "data" / "raw" / "Base"
TEL_GLOB = str(BASE / "datasets" / "telemetria" / "telemetry_*.parquet")

GAP_S = 900
OBSERVATION_HOURS = 24
HORIZON_HOURS = 8
BUCKET_HOURS = 8
TOP_ALARM_IDS = 200
TOP_TEXT_CONCEPTS = 200
VOCAB_CUTOFF = "2025-02-01 00:00:00"
LOOP_TAG = "PE3798"
LOOP_DAY = pd.Timestamp("2025-06-29")
LOOP_ALARM_IDS = (1241582851, 1241582848)
MISSING_START = pd.Timestamp("2025-05-31 00:00:00")
MISSING_END = pd.Timestamp("2025-06-01 00:00:00")
THRESHOLD_GRID = np.round(np.linspace(0.01, 0.99, 197), 3)

economic_base = pd.DataFrame([
    {
        "Tipo": "Caminhao",
        "p_acao_confirmada": 0.655,
        "custo_intervencao_preditiva": 10000.0,
        "custo_manutencao_corretiva": 50000.0,
        "impacto_operacional_hora": 30000.0,
        "horas_parada_corretiva": 4.0,
        "horas_parada_preditiva": 1.0,
    },
    {
        "Tipo": "Escavadeira",
        "p_acao_confirmada": 0.20,
        "custo_intervencao_preditiva": 25000.0,
        "custo_manutencao_corretiva": 150000.0,
        "impacto_operacional_hora": 100000.0,
        "horas_parada_corretiva": 8.0,
        "horas_parada_preditiva": 2.0,
    },
])

SPLITS = [
    {
        "split_id": "S1_teste_abril",
        "treino_fim": pd.Timestamp("2025-02-01"),
        "cal_inicio": pd.Timestamp("2025-02-01"),
        "cal_fim": pd.Timestamp("2025-03-01"),
        "val_inicio": pd.Timestamp("2025-03-01"),
        "val_fim": pd.Timestamp("2025-04-01"),
        "test_inicio": pd.Timestamp("2025-04-01"),
        "test_fim": pd.Timestamp("2025-05-01"),
    },
    {
        "split_id": "S2_teste_maio",
        "treino_fim": pd.Timestamp("2025-03-01"),
        "cal_inicio": pd.Timestamp("2025-03-01"),
        "cal_fim": pd.Timestamp("2025-04-01"),
        "val_inicio": pd.Timestamp("2025-04-01"),
        "val_fim": pd.Timestamp("2025-05-01"),
        "test_inicio": pd.Timestamp("2025-05-01"),
        "test_fim": pd.Timestamp("2025-05-31"),
    },
    {
        "split_id": "S3_teste_junho",
        "treino_fim": pd.Timestamp("2025-04-01"),
        "cal_inicio": pd.Timestamp("2025-04-01"),
        "cal_fim": pd.Timestamp("2025-05-01"),
        "val_inicio": pd.Timestamp("2025-05-01"),
        "val_fim": pd.Timestamp("2025-05-31"),
        "test_inicio": pd.Timestamp("2025-06-01"),
        "test_fim": pd.Timestamp("2025-07-01"),
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

def normalize_tipo(value):
    if pd.isna(value):
        return "Indefinido"
    return "Escavadeira" if "ESCAV" in str(value).upper() else "Caminhao"

print(f"Raiz do projeto: {ROOT}")
"""
    ),
    md("## 1. Preparação da base e features"),
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
                   WHEN date_diff('millisecond', evento_anterior, Data_Evento) > {GAP_S * 1000} THEN 1
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

base_audit = query(
    '''
    SELECT
        (SELECT count(*) FROM analytic_events) AS registros_analiticos,
        (SELECT sum(ids_evento_no_grupo - 1) FROM analytic_events) AS duplicatas_retiradas,
        count(*) AS sequencias,
        sum(is_dont_go) AS sequencias_dont_go
    FROM alarm_sequences
    '''
)
display(base_audit)
"""
    ),
    code(
        """
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

con.execute(
    f'''
    CREATE OR REPLACE TEMP TABLE sample_grid AS
    WITH tags AS (
        SELECT DISTINCT TAG FROM analytic_events
    ), prediction_bins AS (
        SELECT * FROM generate_series(
            TIMESTAMP '2025-01-01 00:00:00' + INTERVAL '{OBSERVATION_HOURS} hours',
            TIMESTAMP '2025-07-01 00:00:00' - INTERVAL '{HORIZON_HOURS} hours',
            INTERVAL '8 hours'
        ) AS t(prediction_time)
    )
    SELECT
        row_number() OVER () AS sample_id,
        tags.TAG,
        prediction_time - INTERVAL '{OBSERVATION_HOURS} hours' AS feature_start,
        prediction_time,
        prediction_time + INTERVAL '{HORIZON_HOURS} hours' AS target_end
    FROM tags CROSS JOIN prediction_bins
    WHERE prediction_time - INTERVAL '{OBSERVATION_HOURS} hours' >= TIMESTAMP '2025-01-01 00:00:00'
    '''
)

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
"""
    ),
    code(
        """
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
        g.sample_id, g.TAG, g.feature_start, g.prediction_time, g.target_end,
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
samples["Tipo"] = samples["Tipo"].replace({"Caminhão": "Caminhao"})

base_derived = pd.DataFrame({
    "feature_has_events": (samples["sequencias_total"] > 0).astype("int8"),
    "prediction_hour_sin": np.sin(2 * np.pi * samples["prediction_time"].dt.hour / 24),
    "prediction_hour_cos": np.cos(2 * np.pi * samples["prediction_time"].dt.hour / 24),
    "prediction_dow_sin": np.sin(2 * np.pi * samples["prediction_time"].dt.dayofweek / 7),
    "prediction_dow_cos": np.cos(2 * np.pi * samples["prediction_time"].dt.dayofweek / 7),
}, index=samples.index)
samples = pd.concat([samples, base_derived], axis=1).copy()

base_features = [
    "sequencias_total", "alarmes_distintos", "registros_analiticos",
    "registros_brutos_representados", "duracao_media_ms", "duracao_max_ms",
    "maior_sequencia_registros", "sequencias_com_critico",
    "sequencias_com_activate", "sequencias_com_inactive",
    "sequencias_com_classe_nula", "feature_has_events",
    "prediction_hour_sin", "prediction_hour_cos", "prediction_dow_sin", "prediction_dow_cos",
]
display(samples.groupby(samples["prediction_time"].dt.to_period("M")).agg(
    amostras=("target", "size"),
    positivas=("target", "sum"),
    prevalencia=("target", "mean"),
).reset_index())
"""
    ),
    code(
        """
top_ids = query(
    f'''
    SELECT Id_Alarme, count(*) AS sequencias
    FROM alarm_sequences
    WHERE inicio < TIMESTAMP '{VOCAB_CUTOFF}'
    GROUP BY 1
    ORDER BY sequencias DESC, Id_Alarme
    LIMIT {TOP_ALARM_IDS}
    '''
)["Id_Alarme"].astype(int).tolist()

id_expr = ",\\n".join(
    f"sum(CASE WHEN Id_Alarme = {alarm_id} THEN 1 ELSE 0 END) AS alarm_{alarm_id}"
    for alarm_id in top_ids
)
con.execute(
    f'''
    CREATE OR REPLACE TEMP TABLE alarm_bin_features AS
    SELECT TAG, bin_start, {id_expr}
    FROM alarm_sequences
    GROUP BY 1, 2
    '''
)
id_sum_expr = ", ".join(
    f"coalesce(sum(b.alarm_{alarm_id}), 0) AS alarm_{alarm_id}" for alarm_id in top_ids
)
id_wide = query(
    f'''
    SELECT g.sample_id, {id_sum_expr}
    FROM sample_grid g
    LEFT JOIN alarm_bin_features b
      ON b.TAG = g.TAG
     AND b.bin_start >= g.feature_start
     AND b.bin_start < g.prediction_time
    GROUP BY 1
    '''
)
id_features = [f"alarm_{alarm_id}" for alarm_id in top_ids]
samples = samples.merge(id_wide, how="left", on="sample_id")
samples[id_features] = samples[id_features].fillna(0).astype("int32")

top_text = query(
    f'''
    SELECT c.conceito_textual AS valor, count(*) AS sequencias
    FROM alarm_sequences s
    JOIN alarm_concepts c USING(Id_Alarme)
    WHERE s.inicio < TIMESTAMP '{VOCAB_CUTOFF}'
    GROUP BY 1
    ORDER BY sequencias DESC, valor
    LIMIT {TOP_TEXT_CONCEPTS}
    '''
)
text_values = top_text["valor"].tolist()
text_name_map = {value: f"textconcept_{i:03d}" for i, value in enumerate(text_values)}
def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"
text_expr = ",\\n".join(
    f"sum(CASE WHEN c.conceito_textual = {sql_literal(value)} THEN 1 ELSE 0 END) AS {text_name_map[value]}"
    for value in text_values
)
con.execute(
    f'''
    CREATE OR REPLACE TEMP TABLE text_bin_features AS
    SELECT s.TAG, s.bin_start, {text_expr}
    FROM alarm_sequences s
    LEFT JOIN alarm_concepts c USING(Id_Alarme)
    GROUP BY 1, 2
    '''
)
text_sum_expr = ", ".join(
    f"coalesce(sum(b.{text_name_map[value]}), 0) AS {text_name_map[value]}" for value in text_values
)
text_wide = query(
    f'''
    SELECT g.sample_id, {text_sum_expr}
    FROM sample_grid g
    LEFT JOIN text_bin_features b
      ON b.TAG = g.TAG
     AND b.bin_start >= g.feature_start
     AND b.bin_start < g.prediction_time
    GROUP BY 1
    '''
)
text_features = [text_name_map[value] for value in text_values]
samples = samples.merge(text_wide, how="left", on="sample_id")
samples[text_features] = samples[text_features].fillna(0).astype("int32")

print(f"Vocabulário conservador de janeiro: {len(id_features)} IDs, {len(text_features)} conceitos")
"""
    ),
    code(
        """
core_cols = [
    "sequencias_total", "alarmes_distintos", "registros_analiticos",
    "registros_brutos_representados", "duracao_soma_ms", "duracao_max_ms",
    "maior_sequencia_registros", "sequencias_com_critico",
    "sequencias_com_activate", "sequencias_com_inactive", "sequencias_com_classe_nula",
]
select_parts = []
for bucket_idx in range(3):
    start_h = bucket_idx * BUCKET_HOURS
    end_h = (bucket_idx + 1) * BUCKET_HOURS
    suffix = f"b{bucket_idx}_{start_h}_{end_h}h"
    for col in core_cols:
        select_parts.append(
            f"coalesce(sum(CASE WHEN b.bin_start >= g.prediction_time - INTERVAL '{end_h} hours' "
            f"AND b.bin_start < g.prediction_time - INTERVAL '{start_h} hours' "
            f"THEN b.{col} ELSE 0 END), 0) AS {col}_{suffix}"
        )
bucket_wide = query(
    f'''
    SELECT g.sample_id,
           {", ".join(select_parts)}
    FROM sample_grid g
    LEFT JOIN sequence_bins b
      ON b.TAG = g.TAG
     AND b.bin_start >= g.feature_start
     AND b.bin_start < g.prediction_time
    GROUP BY 1
    '''
)
bucket_features = [c for c in bucket_wide.columns if c != "sample_id"]
samples = samples.merge(bucket_wide, how="left", on="sample_id")
samples[bucket_features] = samples[bucket_features].fillna(0).astype("float32")

derived = {}
derived_features = []
for base in ["sequencias_total", "alarmes_distintos", "registros_analiticos", "sequencias_com_critico"]:
    recent = f"{base}_b0_0_8h"
    middle = f"{base}_b1_8_16h"
    old = f"{base}_b2_16_24h"
    delta = f"{base}_delta_recent_old"
    ratio = f"{base}_ratio_recent_total"
    derived[delta] = samples[recent] - samples[old]
    derived[ratio] = samples[recent] / (samples[recent] + samples[middle] + samples[old] + 1)
    derived_features.extend([delta, ratio])
samples = pd.concat([samples, pd.DataFrame(derived, index=samples.index)], axis=1).copy()
core_bucket_features = bucket_features + derived_features

FEATURE_SETS = {
    "referencia_24h_ids_textual": base_features + id_features + text_features,
    "multijanela_core_ids_textual": core_bucket_features + id_features + text_features,
}
print({k: len(v) for k, v in FEATURE_SETS.items()})
print(f"Preparação total: {time.time() - start:.1f}s")
"""
    ),
    md("## 2. Treino, calibração sigmoide e thresholds econômicos"),
    code(
        """
def assign_periods(df, split_cfg):
    out = df.copy()
    pt = out["prediction_time"]
    out["periodo"] = np.select(
        [
            pt < split_cfg["treino_fim"],
            (pt >= split_cfg["cal_inicio"]) & (pt < split_cfg["cal_fim"]),
            (pt >= split_cfg["val_inicio"]) & (pt < split_cfg["val_fim"]),
            (pt >= split_cfg["test_inicio"]) & (pt < split_cfg["test_fim"]),
        ],
        ["treino_base", "calibracao", "validacao", "teste"],
        default="fora",
    )
    return out[out["periodo"] != "fora"].copy()

def make_model(name, y_train):
    pos = max(float(y_train.sum()), 1.0)
    neg = max(float(len(y_train) - y_train.sum()), 1.0)
    scale_pos_weight = neg / pos
    if name == "RandomForest":
        return RandomForestClassifier(
            n_estimators=300, max_features="sqrt", min_samples_leaf=2,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1
        )
    if name == "XGBoost":
        return xgb.XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.8, min_child_weight=5, reg_lambda=2.0,
            objective="binary:logistic", eval_metric="logloss",
            scale_pos_weight=scale_pos_weight, random_state=42, n_jobs=-1,
        )
    if name == "LightGBM":
        return lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05, num_leaves=31,
            min_child_samples=40, subsample=0.9, colsample_bytree=0.8,
            reg_lambda=2.0, class_weight="balanced", random_state=42,
            n_jobs=-1, verbose=-1,
        )
    if name == "CatBoost":
        return cb.CatBoostClassifier(
            iterations=300, depth=5, learning_rate=0.05,
            loss_function="Logloss", eval_metric="Logloss",
            auto_class_weights="Balanced", random_seed=42,
            verbose=False, allow_writing_files=False,
        )
    raise ValueError(name)

def predict_proba(model, x_part):
    return model.predict_proba(x_part)[:, 1]

def economic_value_rows(pred_df, threshold):
    scored = pred_df.copy()
    econ_cols = [
        "p_acao_confirmada", "custo_intervencao_preditiva",
        "custo_manutencao_corretiva", "impacto_operacional_hora",
        "horas_parada_corretiva", "horas_parada_preditiva",
    ]
    scored = scored.drop(columns=[c for c in econ_cols if c in scored.columns])
    scored["predito"] = (scored["probabilidade"] >= threshold).astype("int8")
    scored["erro"] = np.select(
        [
            (scored["target"] == 1) & (scored["predito"] == 1),
            (scored["target"] == 0) & (scored["predito"] == 1),
            (scored["target"] == 1) & (scored["predito"] == 0),
            (scored["target"] == 0) & (scored["predito"] == 0),
        ],
        ["TP", "FP", "FN", "TN"],
        default="indefinido",
    )
    scored["tipo_economico"] = scored["Tipo"].map(normalize_tipo)
    scored = scored.merge(economic_base.rename(columns={"Tipo": "tipo_economico"}), how="left", on="tipo_economico")
    no_action_cost = scored["p_acao_confirmada"] * (
        scored["custo_manutencao_corretiva"]
        + scored["impacto_operacional_hora"] * scored["horas_parada_corretiva"]
    )
    tp_action_cost = scored["custo_intervencao_preditiva"] + scored["p_acao_confirmada"] * (
        scored["impacto_operacional_hora"] * scored["horas_parada_preditiva"]
    )
    fp_action_cost = scored["custo_intervencao_preditiva"] + (
        scored["impacto_operacional_hora"] * scored["horas_parada_preditiva"]
    )
    scored["valor_incremental"] = np.select(
        [
            scored["erro"] == "TP",
            scored["erro"] == "FP",
            scored["erro"] == "FN",
            scored["erro"] == "TN",
        ],
        [
            no_action_cost - tp_action_cost,
            -fp_action_cost,
            0.0,
            0.0,
        ],
        default=np.nan,
    )
    return scored

def metric_at_threshold(df, threshold):
    y = df["target"].astype("int8")
    p = df["probabilidade"].to_numpy()
    pred = (p >= threshold).astype("int8")
    scored = economic_value_rows(df, threshold)
    return {
        "threshold": threshold,
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f2": fbeta_score(y, pred, beta=2, zero_division=0),
        "balanced_accuracy": balanced_accuracy_score(y, pred),
        "brier": brier_score_loss(y, p),
        "pr_auc": average_precision_score(y, p),
        "roc_auc": roc_auc_score(y, p),
        "TP": int(((y == 1) & (pred == 1)).sum()),
        "FP": int(((y == 0) & (pred == 1)).sum()),
        "FN": int(((y == 1) & (pred == 0)).sum()),
        "TN": int(((y == 0) & (pred == 0)).sum()),
        "predicoes_positivas": int(pred.sum()),
        "valor_incremental": scored["valor_incremental"].sum(),
    }
"""
    ),
    code(
        """
EXPERIMENTS = [
    {
        "model_scope": "misto",
        "eval_tipo": "Todos",
        "feature_set": "referencia_24h_ids_textual",
        "algoritmo": "RandomForest",
        "nota": "baseline simples atual",
    },
    {
        "model_scope": "misto",
        "eval_tipo": "Todos",
        "feature_set": "multijanela_core_ids_textual",
        "algoritmo": "CatBoost",
        "nota": "candidato econômico atual",
    },
    {
        "model_scope": "caminhoes_only",
        "eval_tipo": "Caminhao",
        "feature_set": "referencia_24h_ids_textual",
        "algoritmo": "RandomForest",
        "nota": "baseline caminhões",
    },
    {
        "model_scope": "caminhoes_only",
        "eval_tipo": "Caminhao",
        "feature_set": "multijanela_core_ids_textual",
        "algoritmo": "CatBoost",
        "nota": "candidato caminhões",
    },
    {
        "model_scope": "caminhoes_only",
        "eval_tipo": "Caminhao",
        "feature_set": "multijanela_core_ids_textual",
        "algoritmo": "XGBoost",
        "nota": "sensibilidade caminhões",
    },
    {
        "model_scope": "escavadeiras_only",
        "eval_tipo": "Escavadeira",
        "feature_set": "referencia_24h_ids_textual",
        "algoritmo": "RandomForest",
        "nota": "parâmetro escavadeiras baixa confiança",
    },
    {
        "model_scope": "escavadeiras_only",
        "eval_tipo": "Escavadeira",
        "feature_set": "multijanela_core_ids_textual",
        "algoritmo": "CatBoost",
        "nota": "parâmetro escavadeiras baixa confiança",
    },
]

all_results = []
all_predictions = []
all_threshold_curves = []

for split_cfg in SPLITS:
    split_samples = assign_periods(samples, split_cfg)
    split_audit = split_samples.groupby(["periodo", "Tipo"], dropna=False).agg(
        amostras=("target", "size"),
        positivas=("target", "sum"),
        prevalencia=("target", "mean"),
    ).reset_index()
    split_audit["split_id"] = split_cfg["split_id"]
    display(split_audit)
    for exp in EXPERIMENTS:
        start_fit = time.time()
        feature_name = exp["feature_set"]
        feature_cols = FEATURE_SETS[feature_name]
        algo = exp["algoritmo"]
        train = split_samples[split_samples["periodo"] == "treino_base"].copy()
        cal = split_samples[split_samples["periodo"] == "calibracao"].copy()
        val = split_samples[split_samples["periodo"] == "validacao"].copy()
        test = split_samples[split_samples["periodo"] == "teste"].copy()

        if exp["model_scope"] == "caminhoes_only":
            train = train[train["Tipo"].map(normalize_tipo) == "Caminhao"]
            cal = cal[cal["Tipo"].map(normalize_tipo) == "Caminhao"]
            val = val[val["Tipo"].map(normalize_tipo) == "Caminhao"]
            test = test[test["Tipo"].map(normalize_tipo) == "Caminhao"]
        elif exp["model_scope"] == "escavadeiras_only":
            train = train[train["Tipo"].map(normalize_tipo) == "Escavadeira"]
            cal = cal[cal["Tipo"].map(normalize_tipo) == "Escavadeira"]
            val = val[val["Tipo"].map(normalize_tipo) == "Escavadeira"]
            test = test[test["Tipo"].map(normalize_tipo) == "Escavadeira"]

        class_audit = {
            "treino_pos": int(train["target"].sum()),
            "cal_pos": int(cal["target"].sum()),
            "val_pos": int(val["target"].sum()),
            "test_pos": int(test["target"].sum()),
        }
        if min(train["target"].nunique(), cal["target"].nunique(), val["target"].nunique(), test["target"].nunique()) < 2:
            print("SKIP por classe única", split_cfg["split_id"], exp, class_audit)
            continue

        x_train = train[feature_cols].astype("float32")
        y_train = train["target"].astype("int8")
        model = make_model(algo, y_train)
        model.fit(x_train, y_train)
        cal_raw = predict_proba(model, cal[feature_cols].astype("float32"))
        val_raw = predict_proba(model, val[feature_cols].astype("float32"))
        test_raw = predict_proba(model, test[feature_cols].astype("float32"))
        calibrator = LogisticRegression(solver="lbfgs")
        calibrator.fit(cal_raw.reshape(-1, 1), cal["target"].astype("int8"))
        frames = []
        for periodo, part, raw in [
            ("validacao", val, val_raw),
            ("teste", test, test_raw),
        ]:
            out = part[["sample_id", "TAG", "Tipo", "Tag_Frota", "prediction_time", "target"]].copy()
            out["split_id"] = split_cfg["split_id"]
            out["model_scope"] = exp["model_scope"]
            out["eval_tipo"] = exp["eval_tipo"]
            out["feature_set"] = feature_name
            out["algoritmo"] = algo
            out["nota"] = exp["nota"]
            out["periodo"] = periodo
            out["probabilidade"] = calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
            frames.append(out)
        pred_df = pd.concat(frames, ignore_index=True)
        rows = []
        for threshold in THRESHOLD_GRID:
            row = metric_at_threshold(pred_df[pred_df["periodo"] == "validacao"], threshold)
            row["threshold"] = threshold
            rows.append(row)
        val_thresholds = pd.DataFrame(rows)
        for key in ["model_scope", "eval_tipo", "feature_set", "algoritmo", "nota"]:
            val_thresholds[key] = exp[key]
        val_thresholds["split_id"] = split_cfg["split_id"]
        val_thresholds["periodo"] = "validacao"
        all_threshold_curves.append(val_thresholds)
        best = val_thresholds.sort_values(["valor_incremental", "threshold"], ascending=[False, False]).iloc[0]
        test_rows = []
        for threshold in THRESHOLD_GRID:
            row = metric_at_threshold(pred_df[pred_df["periodo"] == "teste"], threshold)
            row["threshold"] = threshold
            test_rows.append(row)
        test_thresholds = pd.DataFrame(test_rows)
        for key in ["model_scope", "eval_tipo", "feature_set", "algoritmo", "nota"]:
            test_thresholds[key] = exp[key]
        test_thresholds["split_id"] = split_cfg["split_id"]
        test_thresholds["periodo"] = "teste"
        all_threshold_curves.append(test_thresholds)
        test_metrics = metric_at_threshold(pred_df[pred_df["periodo"] == "teste"], float(best["threshold"]))
        result = {
            "split_id": split_cfg["split_id"],
            "model_scope": exp["model_scope"],
            "eval_tipo": exp["eval_tipo"],
            "feature_set": feature_name,
            "algoritmo": algo,
            "nota": exp["nota"],
            "threshold_validacao": float(best["threshold"]),
            "valor_validacao": float(best["valor_incremental"]),
            "tempo_s": round(time.time() - start_fit, 1),
        }
        result.update(class_audit)
        result.update({f"teste_{k}": v for k, v in test_metrics.items()})
        all_results.append(result)
        pred_test = economic_value_rows(pred_df[pred_df["periodo"] == "teste"], float(best["threshold"]))
        pred_test["threshold_validacao"] = float(best["threshold"])
        all_predictions.append(pred_test)
        print(split_cfg["split_id"], exp["model_scope"], feature_name, algo, "valor_teste", round(test_metrics["valor_incremental"], 1))

results = pd.DataFrame(all_results)
predictions = pd.concat(all_predictions, ignore_index=True)
threshold_curves = pd.concat(all_threshold_curves, ignore_index=True)
display(results.sort_values("teste_valor_incremental", ascending=False).head(30))
"""
    ),
    md("## 3. Consolidação dos resultados"),
    code(
        """
rank_by_split = (
    results.sort_values(["split_id", "teste_valor_incremental"], ascending=[True, False])
    .groupby("split_id")
    .head(10)
)
display(rank_by_split[[
    "split_id", "model_scope", "eval_tipo", "feature_set", "algoritmo", "threshold_validacao",
    "teste_valor_incremental", "teste_precision", "teste_recall",
    "teste_TP", "teste_FP", "teste_FN", "treino_pos", "cal_pos", "val_pos", "test_pos",
    "teste_brier", "teste_pr_auc", "tempo_s"
]])

summary = (
    results.groupby(["model_scope", "eval_tipo", "feature_set", "algoritmo", "nota"])
    .agg(
        splits=("split_id", "nunique"),
        valor_medio=("teste_valor_incremental", "mean"),
        valor_mediano=("teste_valor_incremental", "median"),
        valor_min=("teste_valor_incremental", "min"),
        valor_max=("teste_valor_incremental", "max"),
        precision_media=("teste_precision", "mean"),
        recall_media=("teste_recall", "mean"),
        fp_medio=("teste_FP", "mean"),
        fn_medio=("teste_FN", "mean"),
        brier_medio=("teste_brier", "mean"),
        pr_auc_medio=("teste_pr_auc", "mean"),
        tempo_medio_s=("tempo_s", "mean"),
    )
    .reset_index()
    .sort_values("valor_medio", ascending=False)
)
display(summary)

winners = (
    results.sort_values(["split_id", "teste_valor_incremental"], ascending=[True, False])
    .groupby("split_id")
    .head(1)
    [["split_id", "model_scope", "eval_tipo", "feature_set", "algoritmo", "teste_valor_incremental"]]
)
display(winners)
"""
    ),
    code(
        """
fig, axes = plt.subplots(1, 2, figsize=(18, 6))
sns.barplot(data=summary, y="algoritmo", x="valor_medio", hue="feature_set", ax=axes[0])
axes[0].set(title="Valor incremental médio por algoritmo/representação")
sns.scatterplot(data=results, x="teste_FP", y="teste_TP", hue="algoritmo", style="feature_set", size="teste_valor_incremental", ax=axes[1])
axes[1].set(title="TP vs FP no teste por split")
plt.tight_layout()
plt.show()
"""
    ),
    md("## 4. Recortes do melhor candidato"),
    code(
        """
best_combo = summary.iloc[0][["model_scope", "eval_tipo", "feature_set", "algoritmo"]].to_dict()
print("Melhor combinação por valor médio:", best_combo)
best_predictions = predictions[
    (predictions["model_scope"] == best_combo["model_scope"])
    & (predictions["eval_tipo"] == best_combo["eval_tipo"])
    & (predictions["feature_set"] == best_combo["feature_set"])
    & (predictions["algoritmo"] == best_combo["algoritmo"])
].copy()

type_summary = (
    best_predictions.groupby(["split_id", "Tipo"], dropna=False)
    .agg(
        amostras=("target", "size"),
        positivos=("target", "sum"),
        preditos=("predito", "sum"),
        TP=("erro", lambda x: (x == "TP").sum()),
        FP=("erro", lambda x: (x == "FP").sum()),
        FN=("erro", lambda x: (x == "FN").sum()),
        TN=("erro", lambda x: (x == "TN").sum()),
        valor=("valor_incremental", "sum"),
    )
    .reset_index()
)
type_summary["precision"] = type_summary["TP"] / (type_summary["TP"] + type_summary["FP"]).replace(0, np.nan)
type_summary["recall"] = type_summary["TP"] / (type_summary["TP"] + type_summary["FN"]).replace(0, np.nan)
display(type_summary)

tag_summary = (
    best_predictions.groupby(["split_id", "TAG", "Tipo", "Tag_Frota"], dropna=False)
    .agg(
        amostras=("target", "size"),
        positivos=("target", "sum"),
        preditos=("predito", "sum"),
        TP=("erro", lambda x: (x == "TP").sum()),
        FP=("erro", lambda x: (x == "FP").sum()),
        FN=("erro", lambda x: (x == "FN").sum()),
        valor=("valor_incremental", "sum"),
    )
    .reset_index()
)
print("TAGs com mais FP no melhor candidato:")
display(tag_summary.sort_values(["split_id", "FP"], ascending=[True, False]).groupby("split_id").head(10))
print("TAGs com mais FN no melhor candidato:")
display(tag_summary.sort_values(["split_id", "FN"], ascending=[True, False]).groupby("split_id").head(10))
"""
    ),
    md("## 5. Controle explícito de threshold"),
    code(
        """
candidate_pairs = pd.DataFrame([
    {"model_scope": "misto", "eval_tipo": "Todos", "feature_set": "referencia_24h_ids_textual", "algoritmo": "RandomForest", "rotulo": "misto_referencia_rf"},
    {"model_scope": "misto", "eval_tipo": "Todos", "feature_set": "multijanela_core_ids_textual", "algoritmo": "CatBoost", "rotulo": "misto_multijanela_catboost"},
    {"model_scope": "caminhoes_only", "eval_tipo": "Caminhao", "feature_set": "referencia_24h_ids_textual", "algoritmo": "RandomForest", "rotulo": "caminhoes_referencia_rf"},
    {"model_scope": "caminhoes_only", "eval_tipo": "Caminhao", "feature_set": "multijanela_core_ids_textual", "algoritmo": "CatBoost", "rotulo": "caminhoes_multijanela_catboost"},
    {"model_scope": "caminhoes_only", "eval_tipo": "Caminhao", "feature_set": "multijanela_core_ids_textual", "algoritmo": "XGBoost", "rotulo": "caminhoes_multijanela_xgboost"},
    {"model_scope": "escavadeiras_only", "eval_tipo": "Escavadeira", "feature_set": "referencia_24h_ids_textual", "algoritmo": "RandomForest", "rotulo": "escavadeiras_referencia_rf_baixa_confianca"},
    {"model_scope": "escavadeiras_only", "eval_tipo": "Escavadeira", "feature_set": "multijanela_core_ids_textual", "algoritmo": "CatBoost", "rotulo": "escavadeiras_multijanela_catboost_baixa_confianca"},
])

curves_focus = threshold_curves.merge(
    candidate_pairs,
    how="inner",
    on=["model_scope", "eval_tipo", "feature_set", "algoritmo"],
)
display(
    curves_focus[curves_focus["periodo"] == "teste"]
    .groupby(["rotulo", "threshold"])
    .agg(
        valor_medio=("valor_incremental", "mean"),
        valor_min=("valor_incremental", "min"),
        valor_max=("valor_incremental", "max"),
        precision_media=("precision", "mean"),
        recall_media=("recall", "mean"),
        fp_medio=("FP", "mean"),
        fn_medio=("FN", "mean"),
        predicoes_media=("predicoes_positivas", "mean"),
    )
    .reset_index()
    .sort_values(["rotulo", "valor_medio"], ascending=[True, False])
    .groupby("rotulo")
    .head(12)
)
"""
    ),
    code(
        """
threshold_bands = (
    curves_focus[curves_focus["periodo"] == "teste"]
    .groupby(["rotulo", "threshold"])
    .agg(
        splits=("split_id", "nunique"),
        valor_medio=("valor_incremental", "mean"),
        valor_min=("valor_incremental", "min"),
        precision_media=("precision", "mean"),
        recall_media=("recall", "mean"),
        fp_medio=("FP", "mean"),
        fn_medio=("FN", "mean"),
    )
    .reset_index()
)

best_by_label = (
    threshold_bands.sort_values(["rotulo", "valor_medio"], ascending=[True, False])
    .groupby("rotulo")
    .head(1)
    .rename(columns={"threshold": "threshold_melhor_media", "valor_medio": "melhor_valor_medio"})
    [["rotulo", "threshold_melhor_media", "melhor_valor_medio"]]
)
threshold_bands = threshold_bands.merge(best_by_label, on="rotulo")
threshold_bands["pct_do_melhor"] = threshold_bands["valor_medio"] / threshold_bands["melhor_valor_medio"]
robust_bands = threshold_bands[
    (threshold_bands["pct_do_melhor"] >= 0.95)
    & (threshold_bands["valor_min"] > 0)
].copy()
band_summary = (
    robust_bands.groupby("rotulo")
    .agg(
        thresholds_robustos=("threshold", "count"),
        threshold_min=("threshold", "min"),
        threshold_max=("threshold", "max"),
        valor_medio_min=("valor_medio", "min"),
        valor_medio_max=("valor_medio", "max"),
        pior_split_min=("valor_min", "min"),
        precision_media_min=("precision_media", "min"),
        recall_media_min=("recall_media", "min"),
        recall_media_max=("recall_media", "max"),
    )
    .reset_index()
)
display(band_summary)
"""
    ),
    code(
        """
fig, axes = plt.subplots(1, 2, figsize=(18, 6))
plot_df = curves_focus[curves_focus["periodo"] == "teste"].copy()
sns.lineplot(data=plot_df, x="threshold", y="valor_incremental", hue="rotulo", style="split_id", ax=axes[0])
axes[0].axhline(0, color="black", linewidth=1)
axes[0].set(title="Curva de valor no teste por threshold", ylabel="valor incremental")
sns.lineplot(data=plot_df, x="threshold", y="recall", hue="rotulo", style="split_id", ax=axes[1])
axes[1].set(title="Recall no teste por threshold")
plt.tight_layout()
plt.show()
"""
    ),
    md("## 6. Robustez a premissas econômicas"),
    code(
        """
def value_with_assumptions(pred_df, threshold, assumptions):
    scored = pred_df.copy()
    econ_cols = [
        "p_acao_confirmada", "custo_intervencao_preditiva",
        "custo_manutencao_corretiva", "impacto_operacional_hora",
        "horas_parada_corretiva", "horas_parada_preditiva",
    ]
    scored = scored.drop(columns=[c for c in econ_cols if c in scored.columns])
    scored["predito"] = (scored["probabilidade"] >= threshold).astype("int8")
    scored["erro"] = np.select(
        [
            (scored["target"] == 1) & (scored["predito"] == 1),
            (scored["target"] == 0) & (scored["predito"] == 1),
            (scored["target"] == 1) & (scored["predito"] == 0),
            (scored["target"] == 0) & (scored["predito"] == 0),
        ],
        ["TP", "FP", "FN", "TN"],
        default="indefinido",
    )
    scored["tipo_economico"] = scored["Tipo"].map(normalize_tipo)
    econ = assumptions.rename(columns={"Tipo": "tipo_economico"})
    scored = scored.merge(econ, how="left", on="tipo_economico")
    no_action_cost = scored["p_acao_confirmada"] * (
        scored["custo_manutencao_corretiva"]
        + scored["impacto_operacional_hora"] * scored["horas_parada_corretiva"]
    )
    tp_action_cost = scored["custo_intervencao_preditiva"] + scored["p_acao_confirmada"] * (
        scored["impacto_operacional_hora"] * scored["horas_parada_preditiva"]
    )
    fp_action_cost = scored["custo_intervencao_preditiva"] + (
        scored["impacto_operacional_hora"] * scored["horas_parada_preditiva"]
    )
    value = np.select(
        [
            scored["erro"] == "TP",
            scored["erro"] == "FP",
            scored["erro"] == "FN",
            scored["erro"] == "TN",
        ],
        [
            no_action_cost - tp_action_cost,
            -fp_action_cost,
            0.0,
            0.0,
        ],
        default=np.nan,
    )
    return float(np.nansum(value))

scenarios = []
for name, p_mult, cost_mult, impact_mult in [
    ("baixo_p_baixo_impacto", 0.75, 1.00, 0.75),
    ("base", 1.00, 1.00, 1.00),
    ("alto_p_base", 1.15, 1.00, 1.00),
    ("alto_impacto", 1.00, 1.00, 1.25),
    ("intervencao_mais_cara", 1.00, 1.30, 1.00),
    ("conservador_duro", 0.75, 1.30, 0.75),
]:
    econ = economic_base.copy()
    econ["p_acao_confirmada"] = (econ["p_acao_confirmada"] * p_mult).clip(upper=1)
    econ["custo_intervencao_preditiva"] *= cost_mult
    econ["impacto_operacional_hora"] *= impact_mult
    scenarios.append((name, econ))

scenario_rows = []
for _, pair in candidate_pairs.iterrows():
    pred = predictions[
        (predictions["model_scope"] == pair["model_scope"])
        & (predictions["eval_tipo"] == pair["eval_tipo"])
        & (predictions["feature_set"] == pair["feature_set"])
        & (predictions["algoritmo"] == pair["algoritmo"])
    ].copy()
    if pred.empty:
        continue
    # Threshold operacional: melhor media do teste dentro da curva explicita do modelo.
    threshold_row = best_by_label[best_by_label["rotulo"] == pair["rotulo"]].iloc[0]
    threshold = float(threshold_row["threshold_melhor_media"])
    for split_id, split_pred in pred.groupby("split_id"):
        for scenario_name, econ in scenarios:
            scenario_rows.append({
                "rotulo": pair["rotulo"],
                "split_id": split_id,
                "threshold": threshold,
                "cenario": scenario_name,
                "valor": value_with_assumptions(split_pred, threshold, econ),
            })
scenario_results = pd.DataFrame(scenario_rows)
scenario_summary = (
    scenario_results.groupby(["rotulo", "cenario"])
    .agg(
        valor_medio=("valor", "mean"),
        valor_min=("valor", "min"),
        valor_max=("valor", "max"),
    )
    .reset_index()
    .sort_values(["cenario", "valor_medio"], ascending=[True, False])
)
display(scenario_summary)
"""
    ),
    md("## 7. Separação por caminhões e escavadeiras"),
    code(
        """
type_event_audit = (
    samples.groupby(["Tipo", samples["prediction_time"].dt.to_period("M")])
    .agg(
        amostras=("target", "size"),
        positivos=("target", "sum"),
        prevalencia=("target", "mean"),
        tags=("TAG", "nunique"),
    )
    .reset_index()
    .rename(columns={"prediction_time": "mes"})
)
display(type_event_audit)

type_perf_rows = []
for _, pair in candidate_pairs.iterrows():
    pred = predictions[
        (predictions["model_scope"] == pair["model_scope"])
        & (predictions["eval_tipo"] == pair["eval_tipo"])
        & (predictions["feature_set"] == pair["feature_set"])
        & (predictions["algoritmo"] == pair["algoritmo"])
    ].copy()
    if pred.empty:
        continue
    threshold = float(best_by_label[best_by_label["rotulo"] == pair["rotulo"]].iloc[0]["threshold_melhor_media"])
    pred = economic_value_rows(pred, threshold)
    pred["rotulo"] = pair["rotulo"]
    type_perf_rows.append(pred)
type_perf = pd.concat(type_perf_rows, ignore_index=True)
type_perf_summary = (
    type_perf.groupby(["rotulo", "split_id", "Tipo"], dropna=False)
    .agg(
        amostras=("target", "size"),
        positivos=("target", "sum"),
        preditos=("predito", "sum"),
        TP=("erro", lambda x: (x == "TP").sum()),
        FP=("erro", lambda x: (x == "FP").sum()),
        FN=("erro", lambda x: (x == "FN").sum()),
        valor=("valor_incremental", "sum"),
    )
    .reset_index()
)
type_perf_summary["precision"] = type_perf_summary["TP"] / (type_perf_summary["TP"] + type_perf_summary["FP"]).replace(0, np.nan)
type_perf_summary["recall"] = type_perf_summary["TP"] / (type_perf_summary["TP"] + type_perf_summary["FN"]).replace(0, np.nan)
display(type_perf_summary)

escavadeira_warning = type_event_audit[type_event_audit["Tipo"].map(normalize_tipo) == "Escavadeira"].copy()
print("Positivos mensais de escavadeira:", escavadeira_warning["positivos"].tolist())
print("Leitura obrigatória: modelos de escavadeira são parâmetro de baixa confiança por escassez de positivos.")
"""
    ),
    md(
        """
## 8. Leitura auditada

Registrar:

1. qual faixa de threshold é robusta para referência e CatBoost;
2. se o valor médio depende de um threshold pontual estreito;
3. se a ordem dos modelos muda sob cenários econômicos conservadores;
4. se há evidência para separar treinamento por tipo de equipamento;
5. se escavadeiras continuam sem suporte suficiente.
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
