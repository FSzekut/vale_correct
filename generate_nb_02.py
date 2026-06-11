import nbformat as nbf

nb = nbf.v4.new_notebook()

# ─── SEÇÃO 1: INGESTÃO ────────────────────────────────────────────────────────
md_intro = nbf.v4.new_markdown_cell("""# Projeto Final Mina — Fase 02: Feature Engineering & Modelagem Preditiva

## Objetivo
Transformar o dataset de telemetria limpo (pós-EDA) em features temporais de fadiga e treinar múltiplos modelos para prever falhas críticas (`Is_Dont_Go == 1`) com antecedência.
""")

md_ingestao = nbf.v4.new_markdown_cell("""## 1. Ingestão e Recuperação do Estado Limpo
Reproduzimos aqui, de forma idêntica, os tratamentos documentados no Notebook 01 (EDA): correção de TAGs e expurgo cirúrgico dos 3 dias de loop de sensor confirmados.
""")

code_ingestao = nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import glob
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

sns.set_theme(style="whitegrid")

# Ingestão completa com todas as colunas necessárias para modelagem
caminho_base = r'c:\\TT\\AntiGravity\\Vale_\\data\\raw\\Base\\datasets\\telemetria\\*.parquet'
arquivos_telemetria = glob.glob(caminho_base)

cols = ['TAG', 'Data_Evento', 'Is_Dont_Go', 'Alarme', 'Id_Alarme', 'Tipo',
        'Nome_Operador_Anon', 'Criticidade', 'Localidade']

dfs = []
for arq in arquivos_telemetria:
    dfs.append(pd.read_parquet(arq, columns=cols))
df = pd.concat(dfs, ignore_index=True)

# ── Tratamento de TAGs (Reprodução do EDA 3.1) ──
df['TAG_Limpa'] = df['TAG'].replace({'CA5926': 'CA65926', 'CA5927': 'CA65927'})
df['Prefixo'] = df['TAG_Limpa'].str[:2]

# ── Expurgo Cirúrgico (Reprodução do EDA 3.10) ──
df['Data_Evento'] = pd.to_datetime(df['Data_Evento'])
df['Mes'] = df['Data_Evento'].dt.month
df['Dia'] = df['Data_Evento'].dt.day

df = df[~((df['TAG_Limpa'] == 'PE3798') & (df['Mes'] == 6) & (df['Dia'] == 29))]
df = df[~((df['TAG_Limpa'] == 'PE3797') & (df['Mes'] == 1) & (df['Dia'] == 12))]
df = df[~((df['TAG_Limpa'] == 'CA65932') & (df['Mes'] == 3) & (df['Dia'] == 26))]

df = df.sort_values(['TAG_Limpa', 'Data_Evento']).reset_index(drop=True)

print(f"Dataset limpo: {len(df):,} registros | {df['TAG_Limpa'].nunique()} equipamentos")
print(f"Distribuição do Target (Is_Dont_Go): {df['Is_Dont_Go'].value_counts().to_dict()}")
print(f"Proporção de Don't Go: {df['Is_Dont_Go'].mean()*100:.4f}%")
""")

# ─── SEÇÃO 2: FEATURE ENGINEERING ─────────────────────────────────────────────
md_fe = nbf.v4.new_markdown_cell("""## 2. Feature Engineering — Janelas Temporais de Fadiga

> **Por que não usamos janelas baseadas em linhas (row-based)?**
> Dois motivos documentados no EDA:
> 1. **Gap do 31/05**: toda a frota ficou sem telemetria neste dia. Uma janela de N linhas "saltaria" este buraco, fundindo a fadiga de dias distantes como se fossem contínuos — **Data Leakage Temporal**.
> 2. **Expurgo dos dias de loop (PE3798/29-06, PE3797/12-01, CA65932/26-03)**: o `resample` cria janelas calendárias fixas de 8H. Os períodos expurgados surgem como janelas com `count=0` — **matematicamente correto**, pois a máquina estava de fato parada para conserto do sensor. Uma janela por linhas "saltaria" esses dias silenciosamente e distorceria a fadiga calculada.
>
> Solução: `resample('8h')` por equipamento cria uma grade calendária completa. Janelas vazias existem com valor zero.

**Dois esquemas de features testados em paralelo:**
- **Esquema A**: Agregações temporais (contagens, taxas, rolling 24H e 72H)
- **Esquema B**: One-Hot dos 50 alarmes mais frequentes por janela de 8H (wide format)
""")

code_fe = nbf.v4.new_code_cell("""import re

# ── Top-50 alarmes mais frequentes para Esquema B ──
top_alarmes = df['Alarme'].value_counts().head(50).index.tolist()
print(f"Top 50 alarmes mapeados: {len(top_alarmes)}")

# ── Esquema A: Uma linha por (TAG, turno_8H) com rolling calendarizado ──
print("\\nGerando Esquema A... (pode levar alguns minutos)")

blocos_a = []
for tag, grupo in df.groupby('TAG_Limpa'):
    g = grupo.set_index('Data_Evento').sort_index()

    # resample cria grade calendária: períodos sem dados viram NaN → fill 0
    base = pd.DataFrame({
        'count_8H':   g['Is_Dont_Go'].resample('8h').count(),
        'dontgo_8H':  g['Is_Dont_Go'].resample('8h').sum(),
        'critico_8H': g['Criticidade'].resample('8h').apply(
                          lambda x: (x.str.upper() == 'CRITICO').sum()),
        'Is_Dont_Go': g['Is_Dont_Go'].resample('8h').sum(),  # target: Don'tGo naquela janela
    }).fillna(0)

    # Rolling 24H = 3 janelas de 8H | Rolling 72H = 9 janelas de 8H
    # min_periods=1: janelas no início da série não são descartadas
    base['count_24H']   = base['count_8H'].rolling(3, min_periods=1).sum()
    base['dontgo_24H']  = base['dontgo_8H'].rolling(3, min_periods=1).sum()
    base['taxa_24H']    = base['dontgo_24H'] / base['count_24H'].clip(lower=1)
    base['critico_24H'] = base['critico_8H'].rolling(3, min_periods=1).sum()

    base['count_72H']   = base['count_8H'].rolling(9, min_periods=1).sum()
    base['dontgo_72H']  = base['dontgo_8H'].rolling(9, min_periods=1).sum()
    base['taxa_72H']    = base['dontgo_72H'] / base['count_72H'].clip(lower=1)
    base['critico_72H'] = base['critico_8H'].rolling(9, min_periods=1).sum()

    base['TAG_Limpa'] = tag
    base['Prefixo']   = tag[:2]
    blocos_a.append(base)

features_a = pd.concat(blocos_a).reset_index().rename(columns={'index': 'Data_Evento'})
print(f"Esquema A: {features_a.shape[0]:,} linhas x {features_a.shape[1]} colunas")
display(features_a.head(3))

# ── Esquema B: One-Hot de alarmes por janela 8H ──
print("\\nGerando Esquema B...")
df_ohot = df.copy()
alarme_cols = []
for alarme in top_alarmes:
    col = 'a_' + re.sub(r'[^a-zA-Z0-9]', '_', alarme)[:35]
    df_ohot[col] = (df_ohot['Alarme'] == alarme).astype(int)
    alarme_cols.append(col)

features_b = df_ohot.groupby(
    ['TAG_Limpa', pd.Grouper(key='Data_Evento', freq='8h')]
)[alarme_cols + ['Is_Dont_Go']].sum().reset_index()
features_b['Prefixo'] = features_b['TAG_Limpa'].str[:2]

print(f"Esquema B: {features_b.shape[0]:,} linhas x {features_b.shape[1]} colunas")
""")

# ─── SEÇÃO 3: SPLIT TEMPORAL ───────────────────────────────────────────────────
md_split = nbf.v4.new_markdown_cell("""## 3. Split Temporal (TimeSeriesSplit)

> **Por que não usar `train_test_split` aleatório?**
> Em séries temporais, o futuro **não pode treinar o passado**. Embaralhar os dados causaria Data Leakage: o modelo aprenderia com eventos que ainda não tinham ocorrido no ponto de previsão real.

**Split Cronológico:**
- **Treino**: Meses 1–4 (Janeiro a Abril) — ~67% dos dados
- **Validação**: Mês 5 (Maio) — ~17% (usado no GridSearch/Optuna)
- **Teste**: Mês 6 (Junho) — ~16% ← **nunca visto pelo modelo durante treino**

Dentro do bloco de treino, usamos `TimeSeriesSplit(n_splits=5)` para o search de hiperparâmetros.
""")

code_split = nbf.v4.new_code_cell("""from sklearn.model_selection import TimeSeriesSplit

COLS_EXCLUIR = ['TAG_Limpa', 'Data_Evento', 'Is_Dont_Go', 'TAG', 'Tipo',
                'Nome_Operador_Anon', 'Alarme', 'Id_Alarme', 'Localidade',
                'Criticidade', 'Prefixo', 'Mes', 'Dia']

def preparar_split(features_df, target_col='Is_Dont_Go', label=''):
    if target_col not in features_df.columns:
        raise KeyError(f"Coluna '{target_col}' ausente. Disponíveis: {features_df.columns.tolist()}")

    df_f = features_df.dropna(subset=[target_col]).sort_values('Data_Evento').copy()

    treino    = df_f[df_f['Data_Evento'].dt.month <= 4]
    validacao = df_f[df_f['Data_Evento'].dt.month == 5]
    teste     = df_f[df_f['Data_Evento'].dt.month == 6]

    feat_cols = [c for c in df_f.columns if c not in COLS_EXCLUIR]

    X_tr  = treino[feat_cols].fillna(0)
    y_tr  = (treino[target_col] > 0).astype(int)
    X_val = validacao[feat_cols].fillna(0)
    y_val = (validacao[target_col] > 0).astype(int)
    X_te  = teste[feat_cols].fillna(0)
    y_te  = (teste[target_col] > 0).astype(int)

    print(f"{label} Treino:    {X_tr.shape} | Don'tGo: {y_tr.sum()} ({y_tr.mean()*100:.2f}%)")
    print(f"{label} Validação: {X_val.shape} | Don'tGo: {y_val.sum()} ({y_val.mean()*100:.2f}%)")
    print(f"{label} Teste:     {X_te.shape} | Don'tGo: {y_te.sum()} ({y_te.mean()*100:.2f}%)")
    return X_tr, y_tr, X_val, y_val, X_te, y_te, feat_cols

print("=== ESQUEMA A — Frota Combinada ===")
X_tr, y_tr, X_val, y_val, X_te, y_te, feat_cols = preparar_split(features_a, label='[A]')

scale_pos = int((y_tr == 0).sum() / max((y_tr == 1).sum(), 1))
print(f"\\nscale_pos_weight (razão negativo/positivo): {scale_pos}")
tscv = TimeSeriesSplit(n_splits=5)
""")

# ─── SEÇÃO 4: BASELINE ─────────────────────────────────────────────────────────
md_baseline = nbf.v4.new_markdown_cell("""## 4. Baseline — Modelo Ingênuo
Antes de qualquer sofisticação, precisamos de um piso de performance honesto. O `DummyClassifier` prevê sempre a classe majoritária ("nunca vai falhar"). **Todo modelo que não supere este baseline não tem valor algum.**
""")

code_baseline = nbf.v4.new_code_cell("""from sklearn.dummy import DummyClassifier
from sklearn.metrics import classification_report, roc_auc_score, ConfusionMatrixDisplay
import matplotlib.pyplot as plt

dummy = DummyClassifier(strategy='most_frequent')
dummy.fit(X_tr, y_tr)
y_pred_dummy = dummy.predict(X_te)

print("=== BASELINE (DummyClassifier) ===")
print(classification_report(y_te, y_pred_dummy, target_names=['Normal', "Don't Go"]))
try:
    auc = roc_auc_score(y_te, dummy.predict_proba(X_te)[:, 1])
    print(f"ROC-AUC: {auc:.4f}")
except:
    print("ROC-AUC: N/A (classe única prevista)")

fig, ax = plt.subplots(figsize=(5, 4))
ConfusionMatrixDisplay.from_predictions(y_te, y_pred_dummy, ax=ax,
    display_labels=['Normal', "Don't Go"], colorbar=False)
plt.title("Confusion Matrix — Baseline")
plt.tight_layout()
plt.show()
""")

# ─── SEÇÃO 5: ISOLATION FOREST ─────────────────────────────────────────────────
md_iso = nbf.v4.new_markdown_cell("""## 5. Isolation Forest — Detecção de Anomalia (Não Supervisionado)
Treinado **sem usar o label `Is_Dont_Go`**. O modelo aprende o que é comportamento normal e sinaliza desvios. Se o Isolation Forest e os modelos supervisionados identificam as mesmas anomalias, temos dupla confiança na predição.
""")

code_iso = nbf.v4.new_code_cell("""from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report

contaminacao = float(y_tr.mean())
print(f"Contaminação (proporção real de Don't Go): {contaminacao:.4f}")

iso = IsolationForest(contamination=contaminacao, random_state=42, n_jobs=-1)
iso.fit(X_tr)

# Isolation Forest retorna -1 (anomalia) e 1 (normal). Convertemos para 0/1
y_pred_iso = (iso.predict(X_te) == -1).astype(int)

print("\\n=== ISOLATION FOREST (Não Supervisionado) ===")
print(classification_report(y_te, y_pred_iso, target_names=['Normal', "Don't Go"]))

fig, ax = plt.subplots(figsize=(5, 4))
ConfusionMatrixDisplay.from_predictions(y_te, y_pred_iso, ax=ax,
    display_labels=['Normal', "Don't Go"], colorbar=False)
plt.title("Confusion Matrix — Isolation Forest")
plt.tight_layout()
plt.show()
""")

# ─── SEÇÃO 6: MODELOS SUPERVISIONADOS ─────────────────────────────────────────
md_modelos = nbf.v4.new_markdown_cell("""## 6. Modelos Supervisionados com Otimização de Hiperparâmetros

Cada modelo será otimizado de forma independente usando:
- **GridSearchCV** (modelos sklearn)
- **RandomizedSearchCV** (XGBoost, LightGBM)
- **Optuna** (CatBoost — busca bayesiana)

Todos usando `TimeSeriesSplit(n_splits=5)` internamente.
""")

code_modelos = nbf.v4.new_code_cell("""from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)
from sklearn.metrics import f1_score, roc_auc_score, classification_report
import joblib, os

os.makedirs(r'c:\\TT\\AntiGravity\\Vale_\\models', exist_ok=True)
resultados = []

def avaliar(nome, modelo, X_t, y_t, frota='Combinado', esquema='A'):
    y_p = modelo.predict(X_t)
    y_prob = modelo.predict_proba(X_t)[:, 1] if hasattr(modelo, 'predict_proba') else y_p
    f1  = f1_score(y_t, y_p, zero_division=0)
    auc = roc_auc_score(y_t, y_prob) if y_t.nunique() > 1 else 0.0
    print(f"[{nome}] F1={f1:.4f} | AUC={auc:.4f}")
    resultados.append({'Modelo': nome, 'Frota': frota, 'Esquema': esquema, 'F1': f1, 'AUC': auc})
    return modelo

# ── 1. Random Forest (GridSearchCV) ──
print("\\n=== Random Forest ===")
rf_grid = {'n_estimators': [200, 500], 'max_depth': [6, 10, None], 'class_weight': ['balanced']}
rf = GridSearchCV(RandomForestClassifier(random_state=42, n_jobs=-1), rf_grid, cv=tscv, scoring='f1', n_jobs=-1)
rf.fit(X_tr, y_tr)
print(f"Melhores params RF: {rf.best_params_}")
avaliar('RandomForest', rf.best_estimator_, X_te, y_te)

# ── 2. XGBoost (RandomizedSearch) ──
print("\\n=== XGBoost ===")
xgb_params = {
    'n_estimators': [300, 500, 1000],
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.05, 0.1],
    'subsample': [0.7, 0.9],
    'colsample_bytree': [0.7, 0.9],
    'scale_pos_weight': [scale_pos, scale_pos//2],
}
xgb = RandomizedSearchCV(
    XGBClassifier(random_state=42, n_jobs=-1, eval_metric='logloss', use_label_encoder=False),
    xgb_params, n_iter=30, cv=tscv, scoring='f1', random_state=42, n_jobs=-1
)
xgb.fit(X_tr, y_tr)
print(f"Melhores params XGB: {xgb.best_params_}")
avaliar('XGBoost', xgb.best_estimator_, X_te, y_te)

# ── 3. LightGBM (RandomizedSearch) ──
print("\\n=== LightGBM ===")
lgb_params = {
    'n_estimators': [300, 500, 1000],
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.05, 0.1],
    'num_leaves': [31, 63, 127],
    'class_weight': ['balanced'],
}
lgb = RandomizedSearchCV(
    LGBMClassifier(random_state=42, n_jobs=-1, verbose=-1),
    lgb_params, n_iter=30, cv=tscv, scoring='f1', random_state=42, n_jobs=-1
)
lgb.fit(X_tr, y_tr)
print(f"Melhores params LGB: {lgb.best_params_}")
avaliar('LightGBM', lgb.best_estimator_, X_te, y_te)

# ── 4. CatBoost (Optuna) ──
print("\\n=== CatBoost + Optuna ===")
def objective_cat(trial):
    params = {
        'iterations': trial.suggest_int('iterations', 200, 1000),
        'depth': trial.suggest_int('depth', 4, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 10),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1, scale_pos),
        'random_seed': 42, 'verbose': 0
    }
    scores = []
    for tr_idx, val_idx in tscv.split(X_tr):
        m = CatBoostClassifier(**params)
        m.fit(X_tr.iloc[tr_idx], y_tr.iloc[tr_idx], verbose=0)
        scores.append(f1_score(y_tr.iloc[val_idx], m.predict(X_tr.iloc[val_idx]), zero_division=0))
    return np.mean(scores)

study_cat = optuna.create_study(direction='maximize')
study_cat.optimize(objective_cat, n_trials=50, show_progress_bar=True)
best_cat = CatBoostClassifier(**study_cat.best_params, random_seed=42, verbose=0)
best_cat.fit(X_tr, y_tr)
avaliar('CatBoost', best_cat, X_te, y_te)

# ── 5. HistGradientBoosting (GridSearch — referência sklearn) ──
print("\\n=== HistGradientBoosting ===")
hgb_grid = {
    'max_iter': [200, 500],
    'max_depth': [4, 6],
    'learning_rate': [0.05, 0.1],
    'class_weight': ['balanced'],
}
hgb = GridSearchCV(HistGradientBoostingClassifier(random_state=42), hgb_grid, cv=tscv, scoring='f1', n_jobs=-1)
hgb.fit(X_tr, y_tr)
avaliar('HistGradientBoosting', hgb.best_estimator_, X_te, y_te)
""")

# ─── SEÇÃO 7: EXPERIMENTO SEPARADO CA vs PE ───────────────────────────────────
md_separado = nbf.v4.new_markdown_cell("""## 7. Experimento B — Frotas Separadas (CA e PE)
Treinamos os dois melhores modelos (XGBoost e CatBoost) de forma **independente** para cada frota. Depois comparamos com o experimento combinado para decidir a estratégia de produção.
""")

code_separado = nbf.v4.new_code_cell("""for prefixo in ['CA', 'PE']:
    print(f"\\n{'='*50}")
    print(f"=== EXPERIMENTO SEPARADO — Frota {prefixo} ===")
    
    df_frota = features_a[features_a['TAG_Limpa'].str.startswith(prefixo)]
    res = preparar_split(df_frota)
    if res is None:
        continue
    Xtr_f, ytr_f, Xval_f, yval_f, Xte_f, yte_f, _ = res
    
    sp = int((ytr_f == 0).sum() / max((ytr_f == 1).sum(), 1))
    
    # XGBoost separado
    xgb_f = XGBClassifier(random_state=42, n_jobs=-1, eval_metric='logloss',
                           use_label_encoder=False, scale_pos_weight=sp,
                           n_estimators=500, max_depth=6, learning_rate=0.05)
    xgb_f.fit(Xtr_f, ytr_f)
    avaliar(f'XGBoost_{prefixo}', xgb_f, Xte_f, yte_f, frota=prefixo)
    
    # CatBoost separado
    cat_f = CatBoostClassifier(**study_cat.best_params, random_seed=42, verbose=0)
    cat_f.fit(Xtr_f, ytr_f)
    avaliar(f'CatBoost_{prefixo}', cat_f, Xte_f, yte_f, frota=prefixo)
""")

# ─── SEÇÃO 8: TABELA COMPARATIVA ──────────────────────────────────────────────
md_tabela = nbf.v4.new_markdown_cell("""## 8. Tabela Comparativa de Resultados
""")

code_tabela = nbf.v4.new_code_cell("""df_res = pd.DataFrame(resultados).sort_values('F1', ascending=False).reset_index(drop=True)
print("=== RESULTADOS CONSOLIDADOS ===")
display(df_res.style.background_gradient(cmap='RdYlGn', subset=['F1', 'AUC']))

melhor = df_res.iloc[0]
print(f"\\nMelhor modelo: {melhor['Modelo']} | Frota: {melhor['Frota']} | F1={melhor['F1']:.4f} | AUC={melhor['AUC']:.4f}")
""")

# ─── SEÇÃO 9: SHAP ─────────────────────────────────────────────────────────────
md_shap = nbf.v4.new_markdown_cell("""## 9. Interpretabilidade — SHAP Values
Qual feature mais influencia a predição de um `Don't Go`? O SHAP (SHapley Additive exPlanations) nos responde com rigor matemático.
""")

code_shap = nbf.v4.new_code_cell("""import shap

# Usando o melhor modelo CatBoost ou XGBoost
modelo_para_shap = best_cat  # trocar por outro se necessário
explainer = shap.TreeExplainer(modelo_para_shap)
shap_values = explainer.shap_values(X_te)

print("=== SHAP — Importância Global das Features ===")
shap.summary_plot(shap_values, X_te, plot_type='bar', max_display=20, show=True)

print("\\n=== SHAP — Beeswarm (Impacto e Direção) ===")
shap.summary_plot(shap_values, X_te, max_display=20, show=True)
""")

# ─── SEÇÃO 10: PERSISTÊNCIA ────────────────────────────────────────────────────
md_salvar = nbf.v4.new_markdown_cell("""## 10. Persistência do Melhor Modelo
""")

code_salvar = nbf.v4.new_code_cell("""import joblib

modelo_final = best_cat  # trocar pelo modelo vencedor da tabela comparativa
caminho_modelo = r'c:\\TT\\AntiGravity\\Vale_\\models\\best_model.pkl'
joblib.dump(modelo_final, caminho_modelo)

print(f"Modelo salvo em: {caminho_modelo}")
print(f"Features utilizadas: {feat_cols}")
print("\\nPróximo passo: Notebook 03 — Relatório Final e Visualizações")
""")

# ─── MONTAGEM ─────────────────────────────────────────────────────────────────
nb.cells = [
    md_intro,
    md_ingestao, code_ingestao,
    md_fe, code_fe,
    md_split, code_split,
    md_baseline, code_baseline,
    md_iso, code_iso,
    md_modelos, code_modelos,
    md_separado, code_separado,
    md_tabela, code_tabela,
    md_shap, code_shap,
    md_salvar, code_salvar,
]

with open(r'c:\TT\AntiGravity\Vale_\Projeto_Final_Mina_02_Modelagem.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print("Notebook Projeto_Final_Mina_02_Modelagem gerado com sucesso.")
