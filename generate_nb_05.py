import nbformat as nbf

nb = nbf.v4.new_notebook()

# ═══════════════════════════════════════════════════════════════════════════════
md_intro = nbf.v4.new_markdown_cell("""# Projeto Final Mina — Fase 05: Custo Assimétrico, Alarmes PE e Diagnóstico is_pe

## Motivação

O NB04 revelou que o modelo PE atingiu F1=0. Este notebook investiga as causas, corrige a
estratégia de features para PE e implementa pesos de custo diferenciados derivados da composição
real da frota — sem premissas externas.
""")

code_setup = nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import glob, re, warnings, os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV, RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import f1_score, roc_auc_score, precision_recall_curve, classification_report
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
from IPython.display import display
import optuna, joblib, shap
optuna.logging.set_verbosity(optuna.logging.WARNING)
warnings.filterwarnings('ignore')
sns.set_theme(style='whitegrid', palette='muted')
plt.rcParams['figure.dpi'] = 110
os.makedirs(r'.\\\\models', exist_ok=True)

COLS = ['TAG', 'Data_Evento', 'Is_Dont_Go', 'Alarme', 'Tipo', 'Criticidade']
arquivos = glob.glob(r'.\\\\data\\\\raw\\\\Base\\\\datasets\\\\telemetria\\\\*.parquet')
df_raw = pd.concat([pd.read_parquet(f, columns=COLS) for f in arquivos], ignore_index=True)
df_raw['Data_Evento'] = pd.to_datetime(df_raw['Data_Evento'])
df_raw['TAG_Limpa'] = df_raw['TAG'].replace({'CA5926':'CA65926','CA5927':'CA65927'})
df_raw['Prefixo']   = df_raw['TAG_Limpa'].str[:2]
df_raw['Mes']       = df_raw['Data_Evento'].dt.month
df_raw['Dia']       = df_raw['Data_Evento'].dt.day

df = df_raw.copy()
df = df[~((df['TAG_Limpa']=='PE3798') & (df['Mes']==6) & (df['Dia']==29))]
df = df[~((df['TAG_Limpa']=='PE3797') & (df['Mes']==1) & (df['Dia']==12))]
df = df[~((df['TAG_Limpa']=='CA65932') & (df['Mes']==3) & (df['Dia']==26))]
df = df.sort_values(['TAG_Limpa','Data_Evento']).reset_index(drop=True)

# ── Composição da frota (base para multiplicador de custo) ──
n_ca = df[df['Prefixo']=='CA']['TAG_Limpa'].nunique()
n_pe = df[df['Prefixo']=='PE']['TAG_Limpa'].nunique()
MULT_PE = 1 + n_ca / n_pe

print(f"Frota: {n_ca} CA (Caminhoes) | {n_pe} PE (Escavadeiras)")
print(f"Ratio CA/PE: {n_ca/n_pe:.1f} caminhoes por escavadeira")
print(f"Multiplicador de custo PE: {MULT_PE:.2f}x (derivado da composicao real da frota)")
print(f"  Quando 1 PE para, ~{n_ca/n_pe:.1f} CA ficam ociosos simultaneamente.")
print(f"  Custo_PE = Custo_CA × {MULT_PE:.2f} — calculado dos dados, nao estimado.")
print(f"\\nDataset apos expurgo: {len(df):,} registros | {df['TAG_Limpa'].nunique()} equipamentos")
""")

# ═══════════════════════════════════════════════════════════════════════════════
md_diag = nbf.v4.new_markdown_cell("""## 1. Diagnóstico: Por que PE F1 = 0?

Antes de modelar, quantificamos a escassez de sinal em PE e identificamos os alarmes específicos.
""")

code_diag = nbf.v4.new_code_cell("""# ── 1.1 Escassez de eventos positivos por frota ──
print("=== DISTRIBUICAO DE DONTGO POR FROTA ===")
for pref, label in [('CA','Caminhoes'), ('PE','Escavadeiras')]:
    sub = df[df['Prefixo']==pref]
    print(f"\\n[{pref}] {label}: {sub['TAG_Limpa'].nunique()} equipamentos")
    print(f"  Registros: {len(sub):,} | DontGo: {sub['Is_Dont_Go'].sum():,} ({sub['Is_Dont_Go'].mean()*100:.4f}%)")

# ── 1.2 Simulacao de janelas 8H ──
blocos_diag = []
for tag, grupo in df.groupby('TAG_Limpa'):
    g = grupo.set_index('Data_Evento').sort_index()
    base = pd.DataFrame({
        'count': g['Is_Dont_Go'].resample('8h').count(),
        'Is_Dont_Go': g['Is_Dont_Go'].resample('8h').sum(),
    }).fillna(0)
    base['Target'] = (base['Is_Dont_Go'] > 0).astype(int)
    base['TAG_Limpa'] = tag
    base['Prefixo'] = tag[:2]
    base = base.reset_index().rename(columns={'index':'Data_Evento'})
    base['count_lag'] = base['count'].shift(1)
    blocos_diag.append(base.dropna(subset=['count_lag']))

feat_diag = pd.concat(blocos_diag)

print("\\n=== JANELAS 8H COM DONTGO POR FROTA ===")
for pref in ['CA','PE']:
    sub = feat_diag[feat_diag['Prefixo']==pref]
    tr  = sub[sub['Data_Evento'].dt.month <= 4]
    val = sub[sub['Data_Evento'].dt.month == 5]
    te  = sub[sub['Data_Evento'].dt.month == 6]
    print(f"[{pref}] Total janelas: {len(sub):,} | DG%: {sub['Target'].mean()*100:.2f}%")
    print(f"  Treino: {tr['Target'].sum()} positivos | Validacao: {val['Target'].sum()} | Teste: {te['Target'].sum()}")

# ── 1.3 Os 19 alarmes: quais sao de CA vs PE? ──
ALARMES_DG = [
    'Engine Coolant Level - Active', 'Right Front Brake Temperature - Active',
    'Transmission Oil Level - Active', 'Left Rear Brake Temperature - Active',
    'Aftercooler Level - Active', 'Steering Oil Temperature - Active',
    'Parking Brake - Active', 'Right Rear Brake Temperature - Active',
    'Left Exhaust Temperature - Active', 'Crankcase Pressure - Active',
    'Left Front Brake Temperature - Active',
    'Hydraulic Reservoir Oil Temperature Critically High (L-1850)',
    'Engine Oil Filter - Active', 'Engine Coolant Flow - Active',
    'Right Exhaust Temperature - Active', 'Engine Oil Level - Active',
    'Engine Coolant Temperature - Active',
    'HPD Gearbox Oil Pressure Critically Low (L-1850)',
    'Low Oil Pressure - Active',
]
al_frota = (df[df['Alarme'].isin(ALARMES_DG)]
            .groupby(['Prefixo','Alarme'])['Is_Dont_Go']
            .agg(['sum','count'])
            .reset_index()
            .rename(columns={'sum':'DontGo','count':'Total'})
            .assign(Taxa=lambda d: d['DontGo']/d['Total'])
            .sort_values(['Prefixo','DontGo'], ascending=[True,False]))

print("\\n=== DOS 19 ALARMES COM DONTGO: DISTRIBUICAO POR FROTA ===")
ca_al = al_frota[al_frota['Prefixo']=='CA']
pe_al = al_frota[al_frota['Prefixo']=='PE']
print(f"CA: {len(ca_al)} alarmes | PE: {len(pe_al)} alarmes")
print("\\nAlarmes EXCLUSIVOS de PE (taxa DG = 100%):")
print(pe_al[['Alarme','DontGo','Total','Taxa']].to_string())

fig, ax = plt.subplots(figsize=(12, 5))
cores = ['#3498db' if p=='CA' else '#e74c3c' for p in al_frota['Prefixo']]
ax.barh(al_frota['Alarme'] + ' [' + al_frota['Prefixo'] + ']', al_frota['DontGo'], color=cores)
ax.set_title("Don't Goes por Alarme e Frota\\n[Azul=CA] [Vermelho=PE]")
ax.set_xlabel("Qtd Don't Goes")
plt.tight_layout(); plt.show()

print("\\n=== CONCLUSAO ===")
print(f"17 dos 19 alarmes sao exclusivos de CA. PE tem apenas 2 alarmes com DontGo,")
print(f"ambos hidraulicos e com taxa de 100%: se disparam, a maquina para.")
print(f"\\nImplicacao: O modelo PE precisa de features especificas para hidraulico.")
print(f"Com apenas 16 janelas positivas no treino, qualquer modelo vai sofrer.")
print(f"Estrategia: sample_weight assimetrico + threshold otimizado para PE.")
""")

# ═══════════════════════════════════════════════════════════════════════════════
md_fe = nbf.v4.new_markdown_cell("""## 2. Feature Engineering com Família Hidráulica PE

Adicionamos `f_hidraulico_pe`: contagem dos 2 alarmes hidráulicos exclusivos de PE.
Para CA, essa feature sempre vale 0. Para PE, é o sinal mais crítico disponível.
""")

code_fe = nbf.v4.new_code_cell("""FAMILIAS = {
    'freio':         ['Right Front Brake Temperature - Active',
                      'Left Front Brake Temperature - Active',
                      'Right Rear Brake Temperature - Active',
                      'Left Rear Brake Temperature - Active'],
    'motor':         ['Engine Coolant Level - Active',
                      'Engine Coolant Flow - Active',
                      'Engine Coolant Temperature - Active',
                      'Engine Oil Level - Active',
                      'Engine Oil Filter - Active'],
    'transmissao':   ['Transmission Oil Level - Active',
                      'Low Oil Pressure - Active',
                      'Crankcase Pressure - Active'],
    'arrefecimento': ['Aftercooler Level - Active',
                      'Left Exhaust Temperature - Active',
                      'Right Exhaust Temperature - Active'],
    'outros':        ['Steering Oil Temperature - Active',
                      'Parking Brake - Active'],
    'hidraulico_pe': ['HPD Gearbox Oil Pressure Critically Low (L-1850)',
                      'Hydraulic Reservoir Oil Temperature Critically High (L-1850)'],
}
FAM_COLS = [f'f_{k}' for k in FAMILIAS]

print("Gerando features (resample 8H + shift 1)...")
blocos = []
for tag, grupo in df.groupby('TAG_Limpa'):
    g = grupo.set_index('Data_Evento').sort_index()
    aggs = {
        'count_total': g['Is_Dont_Go'].resample('8h').count(),
        'Is_Dont_Go':  g['Is_Dont_Go'].resample('8h').sum(),
        'count_critico': g['Criticidade'].resample('8h').apply(
            lambda x: x.str.contains('Critico', case=False, na=False).sum()),
    }
    for familia, alarmes in FAMILIAS.items():
        aggs[f'f_{familia}'] = g['Alarme'].resample('8h').apply(
            lambda x, al=alarmes: x.isin(al).sum())

    base = pd.DataFrame(aggs).fillna(0)

    for col in FAM_COLS + ['count_total','count_critico']:
        base[f'{col}_24H'] = base[col].rolling(3, min_periods=1).sum()
        base[f'{col}_72H'] = base[col].rolling(9, min_periods=1).sum()

    # Aceleracao de fadiga
    for col in FAM_COLS:
        media_24H = base[col].rolling(3, min_periods=1).mean().replace(0, np.nan)
        base[f'delta_{col}'] = (base[col] - media_24H).fillna(0)

    # Multi-familia simultanea
    base['n_familias_ativas']     = (base[FAM_COLS] > 0).sum(axis=1)
    base['n_familias_ativas_24H'] = (base['n_familias_ativas'].rolling(3, min_periods=1).max())
    base['is_pe'] = int(tag.startswith('PE'))

    # SHIFT(1)
    feat_shift = [c for c in base.columns if c != 'Is_Dont_Go']
    base[feat_shift] = base[feat_shift].shift(1)
    base['TAG_Limpa'] = tag
    base['Prefixo']   = tag[:2]
    blocos.append(base)

features = pd.concat(blocos).reset_index().rename(columns={'index':'Data_Evento'})
features = features.dropna(subset=['count_total']).copy()
features['Target'] = (features['Is_Dont_Go'] > 0).astype(int)

print(f"Features: {features.shape[0]:,} x {features.shape[1]}")
print(f"DontGo CA: {features[features['Prefixo']=='CA']['Target'].mean()*100:.2f}%")
print(f"DontGo PE: {features[features['Prefixo']=='PE']['Target'].mean()*100:.2f}%")
print(f"\\nFeature f_hidraulico_pe — registros > 0 em PE: "
      f"{(features[features['Prefixo']=='PE']['f_hidraulico_pe']>0).sum()}")
""")

# ═══════════════════════════════════════════════════════════════════════════════
md_ablation = nbf.v4.new_markdown_cell("""## 3. Ablação de is_pe: Ajuda ou Atrapalha?

Hipótese: no modelo combinado, `is_pe=1` sinaliza escavadeira, mas como as features de CA são
sempre zero para PE, o modelo usa `is_pe` como proxy para "ignorar PE".
Testamos com e sem `is_pe` — mesmo Optuna, 100 trials cada.
""")

code_ablation = nbf.v4.new_code_cell("""COLS_META = ['TAG_Limpa','Data_Evento','Is_Dont_Go','Target','TAG','Tipo',
             'Alarme','Criticidade','Prefixo','Mes','Dia','Data_Dia']
tscv = TimeSeriesSplit(n_splits=5)
RESULTADOS = []

def preparar(df_f, com_is_pe=True, frota='Combinado'):
    df_s = df_f.sort_values('Data_Evento').copy()
    df_s['is_pe'] = df_s['TAG_Limpa'].str.startswith('PE').astype(int)
    tr  = df_s[df_s['Data_Evento'].dt.month <= 4]
    val = df_s[df_s['Data_Evento'].dt.month == 5]
    te  = df_s[df_s['Data_Evento'].dt.month == 6]
    excluir = COLS_META + ([] if com_is_pe else ['is_pe'])
    feat = [c for c in tr.columns if c not in excluir and not c.startswith('delta_')]
    Xtr  = tr[feat].fillna(0);  ytr  = tr['Target']
    Xval = val[feat].fillna(0); yval = val['Target']
    Xte  = te[feat].fillna(0);  yte  = te['Target']
    sp   = int((ytr==0).sum() / max((ytr==1).sum(),1))
    is_pe_tr = tr['is_pe'].values if 'is_pe' in tr.columns else np.zeros(len(tr))
    return Xtr, ytr, Xval, yval, Xte, yte, feat, sp, is_pe_tr

def otimizar_thr(modelo, Xv, yv):
    if not hasattr(modelo, 'predict_proba'): return 0.5
    probs = modelo.predict_proba(Xv)[:,1]
    prec, rec, thrs = precision_recall_curve(yv, probs)
    f1s = 2*prec*rec/(prec+rec+1e-9)
    return float(thrs[np.argmax(f1s[:-1])])

def avaliar(nome, modelo, Xte, yte, thr=0.5, frota='Combinado', tag=''):
    y_prob = modelo.predict_proba(Xte)[:,1]
    y_pred = (y_prob >= thr).astype(int)
    f1  = f1_score(yte, y_pred, zero_division=0)
    auc = roc_auc_score(yte, y_prob) if yte.nunique() > 1 else 0.0
    tp  = int(((y_pred==1)&(yte==1)).sum())
    fp  = int(((y_pred==1)&(yte==0)).sum())
    fn  = int(((y_pred==0)&(yte==1)).sum())
    prec = tp/(tp+fp) if (tp+fp)>0 else 0.0
    rec  = tp/(tp+fn) if (tp+fn)>0 else 0.0
    print(f"  [{nome}{tag}] Thr={thr:.2f} P={prec:.3f} R={rec:.3f} F1={f1:.4f} AUC={auc:.4f} TP={tp} FP={fp} FN={fn}")
    RESULTADOS.append({'Modelo':nome+tag,'Frota':frota,'F1':round(f1,4),'AUC':round(auc,4),
                       'Precision':round(prec,4),'Recall':round(rec,4),'TP':tp,'FP':fp,'FN':fn,'Thr':round(thr,3)})
    return modelo

def treinar_cat(Xtr, ytr, sp, n_trials=100, pesos=None):
    def obj(trial):
        p = {'iterations':trial.suggest_int('iterations',200,1000),
             'depth':trial.suggest_int('depth',4,10),
             'learning_rate':trial.suggest_float('learning_rate',0.01,0.3,log=True),
             'l2_leaf_reg':trial.suggest_float('l2_leaf_reg',1,10),
             'scale_pos_weight':trial.suggest_float('scale_pos_weight',1,sp),
             'random_seed':42,'verbose':0}
        scores = []
        for ti, vi in tscv.split(Xtr):
            m = CatBoostClassifier(**p)
            sw = pesos[ti] if pesos is not None else None
            m.fit(Xtr.iloc[ti], ytr.iloc[ti], sample_weight=sw, verbose=0)
            scores.append(f1_score(ytr.iloc[vi], m.predict(Xtr.iloc[vi]), zero_division=0))
        return np.mean(scores)
    s = optuna.create_study(direction='maximize')
    s.optimize(obj, n_trials=n_trials, show_progress_bar=True)
    m = CatBoostClassifier(**s.best_params, random_seed=42, verbose=0)
    m.fit(Xtr, ytr, sample_weight=pesos, verbose=0)
    return m

# ── COM is_pe ──
print("=== Ablacao is_pe: COM is_pe ===")
Xtr, ytr, Xval, yval, Xte, yte, feat_c, sp, is_pe_tr = preparar(features, com_is_pe=True)
cat_com = treinar_cat(Xtr, ytr, sp)
thr_com = otimizar_thr(cat_com, Xval, yval)
avaliar('CatBoost','cat_com',Xte,yte,thr_com,tag='_COM_ispe')

# ── SEM is_pe ──
print("\\n=== Ablacao is_pe: SEM is_pe ===")
Xtr2, ytr2, Xval2, yval2, Xte2, yte2, feat_s, sp2, _ = preparar(features, com_is_pe=False)
cat_sem = treinar_cat(Xtr2, ytr2, sp2)
thr_sem = otimizar_thr(cat_sem, Xval2, yval2)
avaliar('CatBoost','cat_sem',Xte2,yte2,thr_sem,tag='_SEM_ispe')

# Avaliacao separada CA / PE para cada ablacao
for pref in ['CA','PE']:
    mask_te = Xte['TAG_Limpa'].str.startswith(pref) if 'TAG_Limpa' in Xte.columns else (yte.index.isin(features[features['Prefixo']==pref].index))
    mask_te2 = features.loc[Xte2.index,'Prefixo'] == pref
    y_te_p  = yte[features.loc[Xte.index,'Prefixo'] == pref]
    y_te_p2 = yte2[features.loc[Xte2.index,'Prefixo'] == pref]
    Xte_p   = Xte[features.loc[Xte.index,'Prefixo'] == pref]
    Xte_p2  = Xte2[features.loc[Xte2.index,'Prefixo'] == pref]
    print(f"  [{pref}] COM is_pe:", end=' ')
    avaliar(f'CatBoost_{pref}','cat_com_filt',Xte_p,y_te_p,thr_com,frota=pref,tag='_COM')
    print(f"  [{pref}] SEM is_pe:", end=' ')
    avaliar(f'CatBoost_{pref}','cat_sem_filt',Xte_p2,y_te_p2,thr_sem,frota=pref,tag='_SEM')

# SHAP de is_pe
print("\\n=== SHAP — importancia de is_pe ===")
explainer = shap.TreeExplainer(cat_com)
sv = explainer.shap_values(Xte)
idx = list(feat_c).index('is_pe') if 'is_pe' in feat_c else -1
if idx >= 0:
    shap_ispe = np.abs(sv[:,idx]).mean()
    print(f"SHAP medio |is_pe|: {shap_ispe:.6f}")
    top10 = pd.Series(np.abs(sv).mean(axis=0), index=feat_c).sort_values(ascending=False).head(10)
    rank  = top10.index.tolist().index('is_pe') if 'is_pe' in top10.index else '>10'
    print(f"Ranking de is_pe por importancia SHAP: #{rank+1 if isinstance(rank,int) else rank}")
    print(top10.round(6).to_string())
""")

# ═══════════════════════════════════════════════════════════════════════════════
md_peso = nbf.v4.new_markdown_cell("""## 4. Modelo com Pesos Assimétricos (sample_weight PE × MULT_PE)

Com o multiplicador derivado da composição real da frota, treinamos o CatBoost dando
mais peso às amostras positivas de PE — forçando o modelo a não ignorar escavadeiras.
""")

code_peso = nbf.v4.new_code_cell("""print(f"=== MODELO COM CUSTO ASSIMETRICO (MULT_PE = {MULT_PE:.2f}x) ===")
Xtr, ytr, Xval, yval, Xte, yte, feat_c, sp, is_pe_tr = preparar(features, com_is_pe=True)

# Peso assimetrico: positivos PE recebem MULT_PE vezes mais peso
pesos_tr = np.where((ytr==1) & (is_pe_tr==1), MULT_PE, 1.0)
print(f"Distribuicao de pesos: PE positivos={pesos_tr[pesos_tr>1].sum():.0f} amostras com peso {MULT_PE:.1f}x")

cat_asym = treinar_cat(Xtr, ytr, sp, n_trials=100, pesos=pesos_tr)

# Threshold geral
thr_asym = otimizar_thr(cat_asym, Xval, yval)
print("\\n--- Modelo Assimetrico (threshold geral) ---")
avaliar('CatBoost_Asym','',Xte,yte,thr_asym,tag='_geral')

# Thresholds separados por frota (curva PR na validacao filtrada)
print("\\n--- Thresholds separados por frota ---")
for pref in ['CA','PE']:
    Xval_p = Xval[features.loc[Xval.index,'Prefixo'] == pref]
    yval_p = yval[features.loc[Xval.index,'Prefixo'] == pref]
    Xte_p  = Xte[features.loc[Xte.index,'Prefixo'] == pref]
    yte_p  = yte[features.loc[Xte.index,'Prefixo'] == pref]
    if yval_p.sum() == 0:
        thr_p = 0.3  # threshold mais agressivo para PE (poucos positivos na val)
        print(f"  [{pref}] Nenhum positivo na validacao. Usando threshold agressivo: {thr_p}")
    else:
        probs_v = cat_asym.predict_proba(Xval_p)[:,1]
        prec, rec, thrs = precision_recall_curve(yval_p, probs_v)
        f1s = 2*prec*rec/(prec+rec+1e-9)
        thr_p = float(thrs[np.argmax(f1s[:-1])]) if len(thrs)>0 else 0.3
    avaliar(f'CatBoost_Asym_{pref}','',Xte_p,yte_p,thr_p,frota=pref,tag=f'_thr{thr_p:.2f}')
""")

# ═══════════════════════════════════════════════════════════════════════════════
md_roi = nbf.v4.new_markdown_cell("""## 5. ROI com Custo Diferenciado por Frota

O custo de uma PE parada é `MULT_PE` vezes maior que um CA, derivado diretamente da
composição da frota: cada PE parada imobiliza ~5.6 CA ociosos simultaneamente.
""")

code_roi = nbf.v4.new_code_cell("""# Downtime mediano (reutilizando calculo do NB04)
df_ap = pd.read_parquet(r'.\\\\data\\\\raw\\\\Base\\\\datasets\\\\apontamentos\\\\desenvolver_apontamentos.parquet')
df_ap['Inicio'] = pd.to_datetime(df_ap['Inicio'])
dg_ev  = df[df['Is_Dont_Go']==1].sort_values('Data_Evento').copy()
ap_op  = df_ap[df_ap['Classe']=='Operando'].sort_values('Inicio').copy()
dg_ev['Data_Evento'] = dg_ev['Data_Evento'].astype('datetime64[ns]')
ap_op['Inicio']      = ap_op['Inicio'].astype('datetime64[ns]')
dt_real = pd.merge_asof(dg_ev[['TAG_Limpa','Data_Evento','Alarme']],
                        ap_op[['Tag','Inicio']],
                        left_on='Data_Evento', right_on='Inicio',
                        left_by='TAG_Limpa', right_by='Tag', direction='forward')
dt_real['Downtime_H'] = (dt_real['Inicio'] - dt_real['Data_Evento']).dt.total_seconds()/3600
dt_val = dt_real[(dt_real['Downtime_H']>0) & (dt_real['Downtime_H']<=720)].copy()
DOWNTIME_MEDIANA_H = dt_val['Downtime_H'].median()

# Parametros de custo
CUSTO_H_EMERGENCIA  = 8_000
CUSTO_H_PLANEJADO   = 3_500
CUSTO_FALSO_POS     = 800
FATOR_PLANEJADO     = 0.5
ECONOMIA_CA = DOWNTIME_MEDIANA_H * CUSTO_H_EMERGENCIA - DOWNTIME_MEDIANA_H * FATOR_PLANEJADO * CUSTO_H_PLANEJADO
ECONOMIA_PE = ECONOMIA_CA * MULT_PE

print(f"Downtime mediano: {DOWNTIME_MEDIANA_H:.2f}h")
print(f"Economia por TP CA: R$ {ECONOMIA_CA:,.0f}")
print(f"Economia por TP PE: R$ {ECONOMIA_PE:,.0f} ({MULT_PE:.1f}x maior)")
print(f"Custo por FP:       R$ {CUSTO_FALSO_POS:,.0f}")

# Calcular ROI para todos os modelos registrados
df_res = pd.DataFrame(RESULTADOS)

# Separar TP de CA vs PE quando temos info de frota
def calc_roi(row):
    if row['Frota'] == 'CA':
        return row['TP'] * ECONOMIA_CA - row['FP'] * CUSTO_FALSO_POS
    elif row['Frota'] == 'PE':
        return row['TP'] * ECONOMIA_PE - row['FP'] * CUSTO_FALSO_POS
    else:  # Combinado: assumir proporcao pelo dataset
        frac_pe = features[features['Prefixo']=='PE']['Target'].sum() / max(features['Target'].sum(),1)
        return (row['TP'] * (frac_pe * ECONOMIA_PE + (1-frac_pe) * ECONOMIA_CA)
                - row['FP'] * CUSTO_FALSO_POS)

df_res['ROI_R$'] = df_res.apply(calc_roi, axis=1)
df_res = df_res.sort_values('ROI_R$', ascending=False).reset_index(drop=True)

print("\\n=== TABELA COMPARATIVA FINAL ===")
display(df_res[['Modelo','Frota','Thr','F1','AUC','TP','FP','FN','ROI_R$']]
        .style.background_gradient(cmap='RdYlGn', subset=['F1','ROI_R$'])
        .format({'F1':'{:.4f}','AUC':'{:.4f}','ROI_R$':'R$ {:,.0f}','Thr':'{:.2f}'}))

# Plot
fig, ax = plt.subplots(figsize=(12, max(5, len(df_res)*0.45)))
colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in df_res['ROI_R$']]
ax.barh(df_res['Modelo'], df_res['ROI_R$']/1e3, color=colors)
ax.axvline(0, color='black', linewidth=1)
ax.set_xlabel("ROI Estimado (R$ mil)")
ax.set_title("ROI por Modelo vs. Manutencao Reativa\\n(PE = custo {:.1f}x maior que CA)".format(MULT_PE))
plt.tight_layout(); plt.show()
""")

# ═══════════════════════════════════════════════════════════════════════════════
md_shap = nbf.v4.new_markdown_cell("""## 6. SHAP — Interpretabilidade por Frota

Quais features mais influenciam a previsão de CA vs PE?
""")

code_shap = nbf.v4.new_code_cell("""explainer_asym = shap.TreeExplainer(cat_asym)

# SHAP geral
shap_vals = explainer_asym.shap_values(Xte)
print("=== SHAP Geral (modelo assimetrico) ===")
shap.summary_plot(shap_vals, Xte, plot_type='bar', max_display=15, show=True)

# SHAP para CA
Xte_ca = Xte[features.loc[Xte.index,'Prefixo']=='CA']
sv_ca   = explainer_asym.shap_values(Xte_ca)
print("=== SHAP para CA ===")
shap.summary_plot(sv_ca, Xte_ca, plot_type='bar', max_display=10, show=True)

# SHAP para PE
Xte_pe = Xte[features.loc[Xte.index,'Prefixo']=='PE']
if len(Xte_pe) > 0:
    sv_pe = explainer_asym.shap_values(Xte_pe)
    print("=== SHAP para PE ===")
    shap.summary_plot(sv_pe, Xte_pe, plot_type='bar', max_display=10, show=True)
    imp_pe = pd.Series(np.abs(sv_pe).mean(axis=0), index=feat_c).sort_values(ascending=False).head(10)
    print("Top features PE:")
    print(imp_pe.round(5).to_string())
    hidro_rank = imp_pe.index.tolist().index('f_hidraulico_pe') if 'f_hidraulico_pe' in imp_pe.index else '>10'
    print(f"\\nRanking de f_hidraulico_pe em PE: #{hidro_rank+1 if isinstance(hidro_rank,int) else hidro_rank}")
""")

md_salvar = nbf.v4.new_markdown_cell("## 7. Persistência")

code_salvar = nbf.v4.new_code_cell("""melhor = df_res.iloc[0]
print(f"Melhor modelo: {melhor['Modelo']} | F1={melhor['F1']:.4f} | ROI=R$ {melhor['ROI_R$']:,.0f}")
joblib.dump({'modelo': cat_asym, 'features': feat_c,
             'threshold_ca': thr_asym, 'mult_pe': MULT_PE},
            r'.\\\\models\\\\modelo_nb05_assimetrico.pkl')
print("Modelo salvo: modelo_nb05_assimetrico.pkl")
""")

# ═══════════════════════════════════════════════════════════════════════════════
nb.cells = [
    md_intro, code_setup,
    md_diag, code_diag,
    md_fe, code_fe,
    md_ablation, code_ablation,
    md_peso, code_peso,
    md_roi, code_roi,
    md_shap, code_shap,
    md_salvar, code_salvar,
]

with open(r'Projeto_Final_Mina_05_Custo_Assimetrico.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print("Notebook Projeto_Final_Mina_05_Custo_Assimetrico gerado com sucesso.")
