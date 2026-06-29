from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "06_Investigacao_Erros_E_Familias.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 06 — Investigação de Erros e Candidatos a Famílias

## Objetivo

Investigar falsos positivos, falsos negativos e candidatos iniciais de agrupamento de alarmes,
sem alterar a definição de limpeza, sequência, janelas, target ou split temporal do baseline.

As perguntas principais são:

1. quais `TAGs` e `Id_Alarme` concentram falsos positivos de alta probabilidade;
2. quais `TAGs`, tipos de equipamento e `Id_Alarme` concentram falsos negativos;
3. qual é a evidência específica para escavadeiras;
4. quais descrições de alarme sugerem candidatos auditáveis de `conceito_alarme`;
5. quais agrupamentos merecem teste no próximo modelo.

## Limites

Esta auditoria continua prevendo novos episódios da flag `Is_Dont_Go`, não falhas confirmadas. Uma
janela sem evento continua significando apenas ausência de evento registrado, não operação saudável
observada.

O mapeamento de famílias neste notebook é **candidato**, não definitivo. Ele deve nascer dos erros
observados e só deve virar feature depois de validação em modelo posterior.
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
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score, balanced_accuracy_score, confusion_matrix,
    f1_score, fbeta_score, precision_score, recall_score, roc_auc_score,
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
OBSERVATION_HOURS = 8
HORIZON_HOURS = 8
TOP_ALARM_IDS = 200
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

print(f"Raiz do projeto: {ROOT}")
print("Premissas reproduzidas do notebook 03:")
print(f"- sequência: {SEQUENCE_GAP_SECONDS}s")
print(f"- observação/horizonte: {OBSERVATION_HOURS}h/{HORIZON_HOURS}h")
print(f"- IDs no vocabulário: {TOP_ALARM_IDS}")
"""
    ),
    md(
        """
## 1. Reconstituição controlada da base do baseline

Esta seção recompõe a mesma camada analítica do notebook 03. A duplicação aqui é intencional:
mantém este notebook executável de forma independente e permite auditar o baseline sem depender de
estado temporário em memória.

As regras reproduzidas são:

- expurgo apenas do loop localizado da `PE3798` em `29/06/2025`;
- deduplicação exata ignorando somente `Id_Eventos_Telemetria`;
- formação de sequências por `TAG + Id_Alarme` com gap maior que 60 segundos;
- janelas calendarizadas de 8 horas;
- invalidação da lacuna global de `31/05/2025`;
- split temporal sem aleatoriedade.
"""
    ),
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

rebuild_audit = query(
    '''
    SELECT
        (SELECT count(*) FROM analytic_events) AS registros_analiticos,
        (SELECT sum(ids_evento_no_grupo - 1) FROM analytic_events) AS duplicatas_retiradas,
        (SELECT sum(Is_Dont_Go) FROM analytic_events) AS linhas_dont_go,
        (SELECT count(*) FROM alarm_sequences) AS sequencias,
        (SELECT sum(is_dont_go) FROM alarm_sequences) AS sequencias_dont_go
    '''
)
rebuild_audit["tempo_s"] = round(time.time() - start, 1)
display(rebuild_audit)
"""
    ),
    md(
        """
## 2. Janelas, features e modelo

O modelo abaixo é treinado com as mesmas features do notebook 03:

- agregados das sequências iniciadas nas 8 horas anteriores;
- contagens dos 200 `Id_Alarme` mais frequentes no treino;
- codificação cíclica de hora e dia da semana.

O teste continua isolado: junho não participa da seleção dos IDs, do treino nem da escolha de
threshold.
"""
    ),
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
alarm_columns = ",\\n".join(
    f"sum(CASE WHEN Id_Alarme = {alarm_id} THEN 1 ELSE 0 END) AS alarm_{alarm_id}"
    for alarm_id in alarm_ids
)
alarm_bin_features = query(
    f'''
    SELECT TAG, time_bucket(INTERVAL '8 hours', inicio) AS feature_start,
           {alarm_columns}
    FROM alarm_sequences
    GROUP BY 1, 2
    '''
)
samples = samples.merge(alarm_bin_features, how="left", on=["TAG", "feature_start"])
alarm_feature_names = [f"alarm_{alarm_id}" for alarm_id in alarm_ids]
samples[alarm_feature_names] = samples[alarm_feature_names].fillna(0).astype("int32")

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
    "sequencias_com_classe_nula", "feature_has_events",
    "prediction_hour_sin", "prediction_hour_cos",
    "prediction_dow_sin", "prediction_dow_cos",
]
feature_columns = base_feature_columns + alarm_feature_names

display(
    samples.groupby("split")
    .agg(amostras=("target", "size"), positivas=("target", "sum"), prevalencia=("target", "mean"))
    .reset_index()
)
"""
    ),
    code(
        """
def get_split(name, columns):
    part = samples[samples["split"] == name]
    return part[columns].astype("float32"), part["target"].astype("int8"), part.copy()

X_train, y_train, train_meta = get_split("treino", feature_columns)
X_val, y_val, val_meta = get_split("validacao", feature_columns)
X_test, y_test, test_meta = get_split("teste", feature_columns)

def metric_row(name, y_true, probability, threshold):
    prediction = (probability >= threshold).astype(int)
    return {
        "modelo": name,
        "threshold": threshold,
        "pr_auc": average_precision_score(y_true, probability),
        "roc_auc": roc_auc_score(y_true, probability),
        "precision": precision_score(y_true, prediction, zero_division=0),
        "recall": recall_score(y_true, prediction, zero_division=0),
        "f1": f1_score(y_true, prediction, zero_division=0),
        "f2": fbeta_score(y_true, prediction, beta=2, zero_division=0),
        "balanced_accuracy": balanced_accuracy_score(y_true, prediction),
        "predicoes_positivas": int(prediction.sum()),
    }

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
    best = scores.sort_values(
        ["f2", "precision", "threshold"], ascending=[False, False, False]
    ).iloc[0]["threshold"]
    return float(best), scores

rf_params = dict(
    n_estimators=400,
    max_features="sqrt",
    min_samples_leaf=2,
    class_weight="balanced_subsample",
    random_state=42,
    n_jobs=-1,
)

dummy = DummyClassifier(strategy="prior")
dummy.fit(X_train, y_train)

rf_ids = RandomForestClassifier(**rf_params)
rf_ids.fit(X_train, y_train)

val_prob = rf_ids.predict_proba(X_val)[:, 1]
threshold, threshold_scores = select_threshold(y_val, val_prob)
test_prob = rf_ids.predict_proba(X_test)[:, 1]
test_pred = (test_prob >= threshold).astype("int8")

audit_metrics = pd.DataFrame([
    metric_row("RandomForest_com_IDs_validacao", y_val, val_prob, threshold),
    metric_row("RandomForest_com_IDs_teste", y_test, test_prob, threshold),
])
display(audit_metrics)
print(f"Threshold selecionado na validação: {threshold:.3f}")

predictions = test_meta[[
    "TAG", "Tipo", "Tag_Frota", "feature_start", "prediction_time", "target_end",
    "sequencias_total", "alarmes_distintos", "registros_analiticos",
    "episodios_dont_go_target", "target",
]].copy()
predictions["probabilidade"] = test_prob
predictions["predito"] = test_pred
predictions["erro"] = np.select(
    [
        (predictions["target"] == 1) & (predictions["predito"] == 1),
        (predictions["target"] == 0) & (predictions["predito"] == 1),
        (predictions["target"] == 1) & (predictions["predito"] == 0),
        (predictions["target"] == 0) & (predictions["predito"] == 0),
    ],
    ["TP", "FP", "FN", "TN"],
    default="indefinido",
)
display(predictions["erro"].value_counts().rename_axis("erro").reset_index(name="amostras"))
"""
    ),
    md(
        """
## 3. Auditoria por TAG

Uma `TAG` com muitos falsos positivos pode indicar alarmes ruidosos, mudança de regime ou ausência
de features que diferenciem evento relevante de recorrência comum.

Uma `TAG` com falsos negativos concentra risco para o modelo, porque houve episódio positivo no
horizonte e o baseline não sinalizou.
"""
    ),
    code(
        """
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
            eventos_medios=("sequencias_total", "mean"),
        )
        .reset_index()
    )
    out["precision"] = out["TP"] / (out["TP"] + out["FP"]).replace(0, np.nan)
    out["recall"] = out["TP"] / (out["TP"] + out["FN"]).replace(0, np.nan)
    out["taxa_fp"] = out["FP"] / (out["FP"] + out["TN"]).replace(0, np.nan)
    out["prevalencia"] = out["positivos_reais"] / out["amostras"]
    return out

tag_audit = summarize_group(predictions, ["TAG", "Tipo", "Tag_Frota"])
display(tag_audit.sort_values(["FN", "positivos_reais"], ascending=False).head(15))
display(tag_audit.sort_values(["FP", "positivos_previstos"], ascending=False).head(15))

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
sns.barplot(
    data=tag_audit.sort_values("FN", ascending=False).head(12),
    x="FN", y="TAG", hue="Tipo", dodge=False, ax=axes[0]
)
axes[0].set(title="TAGs com mais falsos negativos")
sns.barplot(
    data=tag_audit.sort_values("FP", ascending=False).head(12),
    x="FP", y="TAG", hue="Tipo", dodge=False, ax=axes[1]
)
axes[1].set(title="TAGs com mais falsos positivos")
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 4. Auditoria por tipo de equipamento

Esta leitura separa possível problema de equipamento específico de problema de classe operacional.
Se um tipo inteiro concentrar erros, pode justificar features ou modelos segmentados. Se o erro ficar
em poucas `TAGs`, a investigação deve começar nelas.
"""
    ),
    code(
        """
tipo_audit = summarize_group(predictions, ["Tipo"])
display(tipo_audit.sort_values("FN", ascending=False))

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
sns.barplot(data=tipo_audit.sort_values("positivos_reais", ascending=False), x="positivos_reais", y="Tipo", ax=axes[0])
axes[0].set(title="Positivos reais por tipo")
sns.barplot(data=tipo_audit.sort_values("FN", ascending=False), x="FN", y="Tipo", ax=axes[1])
axes[1].set(title="Falsos negativos por tipo")
sns.barplot(data=tipo_audit.sort_values("FP", ascending=False), x="FP", y="Tipo", ax=axes[2])
axes[2].set(title="Falsos positivos por tipo")
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 5. Auditoria temporal

Como o split é temporal, precisamos verificar se os erros se acumulam em algum trecho de junho. Isso
pode indicar mudança de regime, efeito residual da lacuna de 31/05 ou concentração de eventos em um
dia específico.
"""
    ),
    code(
        """
predictions["data"] = predictions["prediction_time"].dt.date
predictions["hora_previsao"] = predictions["prediction_time"].dt.hour
predictions["semana"] = predictions["prediction_time"].dt.to_period("W").astype(str)

daily_audit = summarize_group(predictions, ["data"])
hour_audit = summarize_group(predictions, ["hora_previsao"])
week_audit = summarize_group(predictions, ["semana"])

display(daily_audit.sort_values("FN", ascending=False).head(15))
display(daily_audit.sort_values("FP", ascending=False).head(15))
display(hour_audit)
display(week_audit)

fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
sns.lineplot(data=daily_audit, x="data", y="FN", marker="o", ax=axes[0], label="FN")
sns.lineplot(data=daily_audit, x="data", y="FP", marker="o", ax=axes[0], label="FP")
axes[0].set(title="Erros por dia de previsão", ylabel="amostras")
sns.lineplot(data=daily_audit, x="data", y="prevalencia", marker="o", ax=axes[1], label="prevalência")
sns.lineplot(data=daily_audit, x="data", y="prob_media", marker="o", ax=axes[1], label="probabilidade média")
axes[1].set(title="Prevalência real e probabilidade média", ylabel="taxa")
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 6. Probabilidades e sensibilidade do threshold

O threshold foi escolhido para maximizar F2 na validação. Aqui observamos se, em junho, os positivos
ficam de fato mais concentrados nas faixas altas de probabilidade e quantos erros estão próximos do
threshold.
"""
    ),
    code(
        """
prob_bins = np.linspace(0, 1, 11)
prob_audit = (
    predictions.assign(faixa_probabilidade=pd.cut(predictions["probabilidade"], prob_bins, include_lowest=True))
    .groupby("faixa_probabilidade", observed=False)
    .agg(amostras=("target", "size"), positivos=("target", "sum"), taxa_positiva=("target", "mean"))
    .reset_index()
)
display(prob_audit)

near_threshold = predictions[
    predictions["probabilidade"].between(threshold - 0.05, threshold + 0.05)
].copy()
display(
    near_threshold["erro"]
    .value_counts()
    .rename_axis("erro")
    .reset_index(name="amostras_proximas_do_threshold")
)

fig, axes = plt.subplots(1, 2, figsize=(15, 5))
sns.histplot(data=predictions, x="probabilidade", hue="target", bins=30, stat="density", common_norm=False, ax=axes[0])
axes[0].axvline(threshold, color="black", linestyle="--")
axes[0].set(title="Distribuição de probabilidades no teste")
sns.barplot(data=prob_audit, x="faixa_probabilidade", y="taxa_positiva", ax=axes[1], color="#4C78A8")
axes[1].set(title="Taxa positiva por faixa de probabilidade", xlabel="faixa")
axes[1].tick_params(axis="x", rotation=45)
plt.tight_layout()
plt.show()
"""
    ),
    md(
        """
## 7. Drill down dos erros

Os casos abaixo não são removidos nem corrigidos automaticamente. Eles servem para escolher a próxima
investigação:

- falsos negativos com maior probabilidade mostram casos quase capturados pelo threshold;
- falsos negativos com baixa probabilidade indicam padrões ausentes nas features atuais;
- falsos positivos com maior probabilidade mostram recorrências que o modelo trata como risco, mas
  sem episódio positivo no horizonte.
"""
    ),
    code(
        """
fn_high = predictions[predictions["erro"] == "FN"].sort_values("probabilidade", ascending=False).head(15)
fn_low = predictions[predictions["erro"] == "FN"].sort_values("probabilidade", ascending=True).head(15)
fp_high = predictions[predictions["erro"] == "FP"].sort_values("probabilidade", ascending=False).head(15)

print("Falsos negativos mais próximos/acima do padrão de risco:")
display(fn_high)
print("Falsos negativos com baixa probabilidade:")
display(fn_low)
print("Falsos positivos com maior probabilidade:")
display(fp_high)
"""
    ),
    code(
        """
def sequence_context(rows, label):
    if rows.empty:
        print(f"Sem casos para {label}.")
        return pd.DataFrame()
    clauses = []
    for row in rows.itertuples(index=False):
        clauses.append(
            f"(TAG = '{row.TAG}' AND inicio >= TIMESTAMP '{row.feature_start}' "
            f"AND inicio < TIMESTAMP '{row.target_end}')"
        )
    where_clause = " OR ".join(clauses)
    result = query(
        f'''
        SELECT
            '{label}' AS grupo,
            TAG, Tipo, Id_Alarme, Alarme, inicio, fim, duracao_ms,
            registros_analiticos, registros_brutos_representados, is_dont_go,
            possui_critico, possui_activate, possui_inactive, possui_classe_nula
        FROM alarm_sequences
        WHERE {where_clause}
        ORDER BY TAG, inicio, is_dont_go DESC, registros_analiticos DESC
        '''
    )
    return result

context_rows = pd.concat([
    sequence_context(fn_high.head(5), "FN_alta_probabilidade"),
    sequence_context(fn_low.head(5), "FN_baixa_probabilidade"),
    sequence_context(fp_high.head(5), "FP_alta_probabilidade"),
], ignore_index=True)

display(context_rows.head(200))
"""
    ),
    md(
        """
## 8. Escavadeiras: evidência disponível

A hipótese operacional é que uma escavadeira parada pode causar impacto em cascata maior que um
caminhão parado. Este dataset, porém, não traz custo financeiro observado por equipamento. Portanto,
esta seção mede apenas:

- quantas escavadeiras existem na telemetria analítica;
- quantos episódios `Is_Dont_Go` aparecem para elas;
- como o baseline erra ou acerta esse recorte no teste.

Qualquer priorização por custo deve entrar depois como premissa externa documentada ou como dado real
de custo/parada, não como conclusão deste dataset.
"""
    ),
    code(
        """
def is_excavator_series(series):
    return series.fillna("").str.contains("ESCAV", case=False, regex=True)

tag_profile_full = query(
    '''
    SELECT
        TAG,
        any_value(Tipo) AS Tipo,
        any_value(Tag_Frota) AS Tag_Frota,
        count(*) AS registros_analiticos,
        sum(Is_Dont_Go) AS linhas_dont_go,
        count(DISTINCT Id_Alarme) AS alarmes_distintos,
        min(Data_Evento) AS inicio,
        max(Data_Evento) AS fim
    FROM analytic_events
    GROUP BY 1
    ORDER BY Tipo, TAG
    '''
)
tag_profile_full["eh_escavadeira"] = is_excavator_series(tag_profile_full["Tipo"])
display(
    tag_profile_full.groupby(["eh_escavadeira", "Tipo"], dropna=False)
    .agg(
        tags=("TAG", "nunique"),
        registros_analiticos=("registros_analiticos", "sum"),
        linhas_dont_go=("linhas_dont_go", "sum"),
        alarmes_distintos=("alarmes_distintos", "sum"),
    )
    .reset_index()
    .sort_values(["eh_escavadeira", "linhas_dont_go"], ascending=[False, False])
)

sequence_type_audit = query(
    '''
    SELECT
        Tipo,
        count(*) AS sequencias,
        sum(is_dont_go) AS sequencias_dont_go,
        count(DISTINCT TAG) AS tags,
        count(DISTINCT Id_Alarme) AS alarmes_distintos
    FROM alarm_sequences
    GROUP BY 1
    ORDER BY sequencias_dont_go DESC
    '''
)
sequence_type_audit["eh_escavadeira"] = is_excavator_series(sequence_type_audit["Tipo"])
display(sequence_type_audit)

predictions["eh_escavadeira"] = is_excavator_series(predictions["Tipo"])
excavator_test_audit = summarize_group(predictions, ["eh_escavadeira", "Tipo"])
display(excavator_test_audit.sort_values(["eh_escavadeira", "FN"], ascending=[False, False]))

display(
    predictions[predictions["eh_escavadeira"]]
    .sort_values(["target", "probabilidade"], ascending=[False, False])
    .head(100)
)
"""
    ),
    md(
        """
## 9. Alarmes associados aos erros

Aqui ligamos cada janela de teste às sequências de alarme observadas nas 8 horas anteriores e aos
episódios no horizonte. Essa leitura evita criar famílias por similaridade textual ampla antes de
saber quais alarmes realmente aparecem nos erros.
"""
    ),
    code(
        """
con.register("predictions_df", predictions)

obs_error_alarm = query(
    '''
    SELECT
        p.erro,
        p.Tipo,
        s.Id_Alarme,
        any_value(s.Alarme) AS Alarme,
        count(*) AS sequencias_observadas,
        count(DISTINCT p.TAG || '|' || CAST(p.feature_start AS VARCHAR)) AS janelas,
        count(DISTINCT p.TAG) AS tags,
        sum(s.is_dont_go) AS sequencias_observadas_dont_go,
        avg(p.probabilidade) AS prob_media
    FROM predictions_df p
    JOIN alarm_sequences s
      ON s.TAG = p.TAG
     AND s.inicio >= p.feature_start
     AND s.inicio < p.prediction_time
    WHERE p.erro IN ('FP', 'FN')
    GROUP BY 1, 2, 3
    ORDER BY erro, janelas DESC, sequencias_observadas DESC
    '''
)

target_error_alarm = query(
    '''
    SELECT
        p.erro,
        p.Tipo,
        s.Id_Alarme,
        any_value(s.Alarme) AS Alarme,
        count(*) AS sequencias_no_horizonte,
        count(DISTINCT p.TAG || '|' || CAST(p.feature_start AS VARCHAR)) AS janelas,
        count(DISTINCT p.TAG) AS tags,
        sum(s.is_dont_go) AS sequencias_dont_go_no_horizonte,
        avg(p.probabilidade) AS prob_media
    FROM predictions_df p
    JOIN alarm_sequences s
      ON s.TAG = p.TAG
     AND s.inicio >= p.prediction_time
     AND s.inicio < p.target_end
    WHERE p.erro IN ('FP', 'FN')
    GROUP BY 1, 2, 3
    ORDER BY erro, sequencias_dont_go_no_horizonte DESC, janelas DESC
    '''
)

print("Alarmes na janela de observação dos erros:")
display(obs_error_alarm.groupby("erro").head(25))
print("Alarmes no horizonte dos erros:")
display(target_error_alarm.groupby("erro").head(25))

print("Recorte de escavadeiras na observação dos erros:")
display(obs_error_alarm[is_excavator_series(obs_error_alarm["Tipo"])].groupby("erro").head(25))
print("Recorte de escavadeiras no horizonte dos erros:")
display(target_error_alarm[is_excavator_series(target_error_alarm["Tipo"])].groupby("erro").head(25))
"""
    ),
    md(
        """
## 10. Candidatos iniciais de conceito de alarme

Esta seção cria uma normalização textual simples para apoiar inspeção humana:

- maiúsculas;
- remoção de acentos;
- remoção de sufixos como `(L-1850)`;
- compactação de espaços.

Isso **não** define família final. Serve para achar grupos candidatos onde múltiplos `Id_Alarme`
aparecem com nomes equivalentes ou muito próximos nos erros.
"""
    ),
    code(
        """
def normalize_alarm_name(value):
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\\s*\\(L-?\\d+\\)\\s*$", "", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text

error_alarm_base = pd.concat([
    obs_error_alarm.assign(origem="observacao")[["origem", "erro", "Tipo", "Id_Alarme", "Alarme", "janelas", "tags", "prob_media"]],
    target_error_alarm.assign(origem="horizonte")[["origem", "erro", "Tipo", "Id_Alarme", "Alarme", "janelas", "tags", "prob_media"]],
], ignore_index=True)
error_alarm_base["alarme_normalizado"] = error_alarm_base["Alarme"].map(normalize_alarm_name)
error_alarm_base["eh_escavadeira"] = is_excavator_series(error_alarm_base["Tipo"])

concept_candidates = (
    error_alarm_base.groupby(["origem", "erro", "alarme_normalizado"], dropna=False)
    .agg(
        ids=("Id_Alarme", "nunique"),
        id_alarmes=("Id_Alarme", lambda x: ", ".join(map(str, sorted(set(x))))),
        descricoes=("Alarme", lambda x: " | ".join(sorted(set(map(str, x)))[:5])),
        janelas=("janelas", "sum"),
        tags=("tags", "max"),
        prob_media=("prob_media", "mean"),
        aparece_em_escavadeira=("eh_escavadeira", "max"),
    )
    .reset_index()
    .sort_values(["erro", "janelas", "ids"], ascending=[True, False, False])
)

print("Candidatos com mais de um Id_Alarme após normalização textual:")
display(concept_candidates[concept_candidates["ids"] > 1].head(50))

print("Candidatos mais frequentes nos falsos positivos:")
display(concept_candidates[concept_candidates["erro"] == "FP"].head(50))

print("Candidatos mais frequentes nos falsos negativos:")
display(concept_candidates[concept_candidates["erro"] == "FN"].head(50))

print("Candidatos ligados a escavadeiras:")
display(concept_candidates[concept_candidates["aparece_em_escavadeira"]].head(50))
"""
    ),
    md(
        """
## 11. Saídas para o próximo modelo

O próximo modelo só deve usar uma família/conceito se a evidência mínima existir:

1. o grupo aparece em erros relevantes ou positivos reais;
2. o agrupamento tem explicação técnica plausível pelo nome e contexto;
3. a regra de agrupamento pode ser reproduzida sem consultar o teste futuro;
4. a comparação é feita contra o baseline congelado, com o mesmo split.

Se escavadeiras forem priorizadas por custo, registrar explicitamente a premissa ou incorporar uma
tabela real de custo/parada. Com os dados atuais, a decisão baseada em evidência é apenas sobre
frequência, prevalência e erro de classificação.
"""
    ),
    md(
        """
## 12. Leitura auditada

Ao interpretar este notebook, separar três situações:

1. **erro do modelo:** o padrão existe nos dados, mas as features atuais não capturam;
2. **limitação do target:** a flag `Is_Dont_Go` pode não representar uma consequência operacional;
3. **mudança de regime:** junho pode ter comportamento diferente de janeiro-maio.

Próximos passos naturais:

1. revisar as `TAGs`, tipos e alarmes que concentram `FN`;
2. verificar se os `FP` de maior probabilidade têm alarmes semanticamente próximos aos positivos;
3. transformar apenas candidatos sustentados em um mapa `Id_Alarme -> conceito_alarme`;
4. testar esse mapa no próximo modelo e repetir esta auditoria;
5. comparar outros gaps de sequência mantendo este mesmo split;
6. só então testar multijanelas ou modelos mais complexos.
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
