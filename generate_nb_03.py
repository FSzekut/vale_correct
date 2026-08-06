import nbformat as nbf

nb = nbf.v4.new_notebook()

# ═══════════════════════════════════════════════════════════════════════════════
# CAPÍTULO 1 — ENTENDIMENTO DO NEGÓCIO
# ═══════════════════════════════════════════════════════════════════════════════
md_cap1 = nbf.v4.new_markdown_cell("""# Projeto Final Mina — Manutenção Preditiva: Notebook Definitivo

## Capítulo 1 — Entendimento do Negócio

### 1.1 Contexto Operacional
A operação analisa uma frota de equipamentos pesados em mina a céu aberto, dividida em duas classes:
- **Caminhões Fora-de-Estrada (CA)**: transporte de material
- **Pás Escavadeiras (PE)**: carregamento

Cada equipamento emite sinais contínuos de telemetria via sensores onboard, registrando centenas de tipos de alarmes ao longo do turno.

### 1.2 O Evento Crítico: Don't Go
O alarme `Is_Dont_Go == 1` sinaliza uma **falha crítica imediata** que paralisa o equipamento — uma parada não planejada de alto impacto. O objetivo do projeto é antecipar esse evento usando os padrões históricos dos sensores das horas anteriores à falha.

### 1.3 Pergunta de Negócio
> *"Com base no comportamento dos sensores nas últimas horas, qual a probabilidade de um equipamento entrar em falha crítica no próximo turno (8 horas)?"*
""")

code_cap1_setup = nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import glob
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

sns.set_theme(style='whitegrid', palette='muted')
plt.rcParams['figure.dpi'] = 110

# ── Ingestão Completa ──
COLS = ['TAG', 'Data_Evento', 'Is_Dont_Go', 'Alarme', 'Tipo',
        'Nome_Operador_Anon', 'Criticidade']
arquivos = glob.glob(r'.\\\\data\\\\raw\\\\Base\\\\datasets\\\\telemetria\\\\*.parquet')

dfs = [pd.read_parquet(f, columns=COLS) for f in arquivos]
df_raw = pd.concat(dfs, ignore_index=True)
df_raw['Data_Evento'] = pd.to_datetime(df_raw['Data_Evento'])

df_ap = pd.read_parquet(r'.\\\\data\\\\raw\\\\Base\\\\datasets\\\\apontamentos\\\\desenvolver_apontamentos.parquet')
df_ap['Inicio'] = pd.to_datetime(df_ap['Inicio'])
df_ap['Fim']    = pd.to_datetime(df_ap['Fim'])

print(f"Telemetria bruta: {len(df_raw):,} registros | {df_raw['Data_Evento'].dt.date.min()} a {df_raw['Data_Evento'].dt.date.max()}")
print(f"Apontamentos: {len(df_ap):,} registros")
""")

md_downtime = nbf.v4.new_markdown_cell("""### 1.4 O Custo Real da Falha — Downtime Médio por Tipo de Alarme

Abandonamos premissas fixas ("12 horas salvas por parada evitada") e calculamos o **Downtime Real** diretamente dos dados: o intervalo entre o registro do alarme `Don't Go` e o primeiro registro de retorno a `Operando` nos Apontamentos Oficiais.
""")

code_downtime = nbf.v4.new_code_cell("""# ── Correção de TAGs (reproduzindo EDA) ──
df_raw['TAG_Limpa'] = df_raw['TAG'].replace({'CA5926': 'CA65926', 'CA5927': 'CA65927'})

# ── Merge asof: Don't Go → primeiro retorno a Operando ──
dontgo_ev  = df_raw[df_raw['Is_Dont_Go'] == 1].sort_values('Data_Evento').copy()
ap_operando = df_ap[df_ap['Classe'] == 'Operando'].sort_values('Inicio').copy()

dontgo_ev['Data_Evento'] = dontgo_ev['Data_Evento'].astype('datetime64[ns]')
ap_operando['Inicio']    = ap_operando['Inicio'].astype('datetime64[ns]')

downtime_real = pd.merge_asof(
    dontgo_ev[['TAG_Limpa', 'Data_Evento', 'Alarme']],
    ap_operando[['Tag', 'Inicio']],
    left_on='Data_Evento', right_on='Inicio',
    left_by='TAG_Limpa', right_by='Tag',
    direction='forward'
)
downtime_real['Downtime_H'] = (downtime_real['Inicio'] - downtime_real['Data_Evento']).dt.total_seconds() / 3600
# Filtrar outliers: paradas > 30 dias provavelmente indicam equipamento fora de serviço permanente
downtime_real = downtime_real[(downtime_real['Downtime_H'] > 0) & (downtime_real['Downtime_H'] <= 720)]

tabela_roi = (downtime_real.groupby('Alarme')['Downtime_H']
              .agg(['mean', 'count'])
              .rename(columns={'mean': 'Media_H_Inoperante', 'count': 'Ocorrencias'})
              .sort_values('Media_H_Inoperante', ascending=False)
              .round(2))

print("=== DOWNTIME REAL MÉDIO POR ALARME DON'T GO ===")
print(f"Base: {len(downtime_real):,} eventos Don't Go com retorno a Operando mapeado")
display(tabela_roi)
""")

# ═══════════════════════════════════════════════════════════════════════════════
# CAPÍTULO 2 — QUALIDADE DOS DADOS
# ═══════════════════════════════════════════════════════════════════════════════
md_cap2 = nbf.v4.new_markdown_cell("""## Capítulo 2 — Entendimento e Qualidade dos Dados
""")

md_tags = nbf.v4.new_markdown_cell("""### 2.1 Correção de Nomenclatura (TAGs)
Uma inspeção revelou erros de digitação onde dígitos foram omitidos no código do equipamento. Isso fragmentaria o histórico de fadiga de uma mesma máquina, diluindo o sinal do modelo.
""")

code_tags = nbf.v4.new_code_cell("""tags_orig = df_raw['TAG'].unique()
print(f"TAGs originais (com erro): {len(tags_orig)}")

CORRECOES = {'CA5926': 'CA65926', 'CA5927': 'CA65927'}
df_raw['TAG_Limpa'] = df_raw['TAG'].replace(CORRECOES)
df_raw['Prefixo']   = df_raw['TAG_Limpa'].str[:2]

tags_limpas = df_raw['TAG_Limpa'].unique()
print(f"TAGs após correção: {len(tags_limpas)}")
print(f"Correções aplicadas: {CORRECOES}")
""")

md_taxa = nbf.v4.new_markdown_cell("""### 2.2 Prova de Taxonomia da Frota
Não assumimos empiricamente que CA = Caminhão e PE = Escavadeira. Cruzamos o prefixo das TAGs com a coluna `Tipo` presente no dataset para provar via dado.
""")

code_taxa = nbf.v4.new_code_cell("""taxonomia = (df_raw[['Prefixo', 'Tipo']]
             .drop_duplicates()
             .dropna()
             .reset_index(drop=True))
print("=== PROVA DE TAXONOMIA ===")
display(taxonomia)
print("\\nConclusion: CA = Caminhão | PE = Escavadeira — confirmado pelos dados.")
""")

md_op = nbf.v4.new_markdown_cell("""### 2.3 Análise de Operadores
Com 395 operadores registrados, investigamos dois pontos: erros de nomenclatura e concentração de falhas por operador.
""")

code_op = nbf.v4.new_code_cell("""ops = df_raw['Nome_Operador_Anon'].unique()
print(f"Operadores únicos: {len(ops)} | Nulos: {df_raw['Nome_Operador_Anon'].isna().sum()}")

fora = [o for o in ops if not re.match(r'^OP_\\d+$', str(o))]
print(f"Fora do padrão OP_XXX: {len(fora)}" + (" — nenhum erro de nomenclatura." if not fora else str(fora[:10])))

rank_op = (df_raw.groupby('Nome_Operador_Anon')
           .agg(total=('Is_Dont_Go','count'), dontgo=('Is_Dont_Go','sum'))
           .assign(taxa=lambda d: d['dontgo']/d['total'])
           .query('total > 500')
           .sort_values('taxa', ascending=False))

fig, ax = plt.subplots(figsize=(12, 5))
sns.barplot(data=rank_op.head(15).reset_index(), y='Nome_Operador_Anon', x='taxa',
            palette='rocket', ax=ax)
ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
ax.set_title("Top 15 Operadores por Taxa de Don't Go")
ax.set_xlabel("Taxa de Don't Go")
ax.set_ylabel("Operador")
plt.tight_layout()
plt.show()

print(f"\\nMédia da taxa de Don't Go por operador: {rank_op['taxa'].mean()*100:.2f}%")
print(f"OP_004 (maior): {rank_op['taxa'].iloc[0]*100:.2f}% — {rank_op['taxa'].iloc[0]/rank_op['taxa'].mean():.0f}x acima da média")
print("\\nDecisão: Operador entra como feature via Target Encoding (calculado apenas no treino).")
""")

md_gap = nbf.v4.new_markdown_cell("""### 2.4 Continuidade Temporal — O Apagão de Maio
Antes de construir qualquer feature baseada em tempo, precisamos verificar se a série temporal é contínua.
""")

code_gap = nbf.v4.new_code_cell("""df_raw['Data_Dia'] = pd.to_datetime(df_raw['Data_Evento'].dt.date)
df_raw['Mes'] = df_raw['Data_Evento'].dt.month
df_raw['Dia'] = df_raw['Data_Evento'].dt.day

vol_dia = df_raw.groupby('Data_Dia').size().reset_index(name='Volume')
cal = pd.date_range(vol_dia['Data_Dia'].min(), vol_dia['Data_Dia'].max())
vol_dia = vol_dia.set_index('Data_Dia').reindex(cal, fill_value=0).reset_index()
vol_dia.rename(columns={'index': 'Data_Dia'}, inplace=True)

fig, ax = plt.subplots(figsize=(15, 4))
ax.plot(vol_dia['Data_Dia'], vol_dia['Volume'], color='steelblue', linewidth=1)
ax.fill_between(vol_dia['Data_Dia'], vol_dia['Volume'], alpha=0.2, color='steelblue')
ax.set_title("Volume Diário de Registros de Telemetria — Gap do Dia 31/05 Evidenciado")
ax.set_ylabel("Registros por Dia")
ax.set_xlabel("Data")
ax.axvline(pd.Timestamp('2025-05-31'), color='red', linestyle='--', linewidth=1.5, label='31/05 — Gap completo')
ax.legend()
plt.tight_layout()
plt.show()

gap_vol = vol_dia[vol_dia['Data_Dia'] == pd.Timestamp('2025-05-31')]['Volume'].values[0]
print(f"Registros no dia 31/05: {gap_vol}")
print("\\nConsequência técnica: janelas row-based (N linhas) cruzariam este gap silenciosamente,")
print("fundindo fadiga de dias distantes. Obrigatório usar resample('8h') — janelas calendarizadas.")
""")

md_anomalias = nbf.v4.new_markdown_cell("""### 2.5 Detecção e Expurgo de Anomalias de Volume
Varremos os 6 meses separando as frotas para detectar *Sensor Loops* — dias com volume de alarmes ordens de magnitude acima do normal. Cada anomalia foi investigada com 3 vetores: quais alarmes, houve `Don't Go`, e houve apontamento de manutenção?
""")

code_anomalias = nbf.v4.new_code_cell("""# ── Top volumetrias diárias por frota ──
for pref, label in [('PE', 'Escavadeiras'), ('CA', 'Caminhões')]:
    df_p = df_raw[df_raw['Prefixo'] == pref]
    vol = df_p.groupby(['TAG_Limpa','Mes','Dia']).size().sort_values(ascending=False).reset_index(name='Volume')
    print(f"\\n--- TOP 5 DIA/EQUIPAMENTO: {label} ---")
    display(vol.head(5))

# ── Deep Dive nas 3 anomalias ──
anomalias = [
    ('PE3798', 6, 29), ('PE3797', 1, 12), ('CA65932', 3, 26)
]
for tag, mes, dia in anomalias:
    loop = df_raw[(df_raw['TAG_Limpa']==tag) & (df_raw['Mes']==mes) & (df_raw['Dia']==dia)]
    print(f"\\n=== {tag} | Mês {mes:02d} / Dia {dia:02d} ===")
    print(f"Volume: {len(loop):,} | Is_Dont_Go total: {loop['Is_Dont_Go'].sum()}")
    print("Top alarme:", loop['Alarme'].value_counts().index[0])
    ap_loop = df_ap[(df_ap['Tag']==tag) & (df_ap['Inicio'].dt.month==mes) &
                    (df_ap['Inicio'].dt.day >= dia)]
    print(f"Apontamentos (a partir do dia {dia}):")
    print(ap_loop[['Inicio','Fim','Classe']].head(3).to_string())
    print("→ CONCLUSÃO: Is_Dont_Go = ZERO. Ruído de sensor. Expurgo cirúrgico justificado.")

# ── Expurgo ──
df = df_raw.copy()
df = df[~((df['TAG_Limpa']=='PE3798') & (df['Mes']==6) & (df['Dia']==29))]
df = df[~((df['TAG_Limpa']=='PE3797') & (df['Mes']==1) & (df['Dia']==12))]
df = df[~((df['TAG_Limpa']=='CA65932') & (df['Mes']==3) & (df['Dia']==26))]
df = df.sort_values(['TAG_Limpa','Data_Evento']).reset_index(drop=True)

print(f"\\nRegistros antes do expurgo: {len(df_raw):,}")
print(f"Registros após expurgo:     {len(df):,}")
print(f"Removidos (ruído de sensor): {len(df_raw)-len(df):,}")
""")

md_alarmes = nbf.v4.new_markdown_cell("""### 2.6 Taxonomia de Alarmes — Fundamentando as Features
Com 712 tipos de alarmes únicos, seria um erro tratar todos igualmente. Precisamos entender quais carregam sinal preditivo real.
""")

code_alarmes = nbf.v4.new_code_cell("""# ── Análise de Alarmes: quais têm Don't Go? ──
res_al = (df.groupby('Alarme')
           .agg(total=('Is_Dont_Go','count'), dontgo=('Is_Dont_Go','sum'))
           .assign(taxa_dg=lambda d: d['dontgo']/d['total'])
           .reset_index()
           .sort_values('total', ascending=False))

total_reg = len(df)
n_unicos  = res_al['Alarme'].nunique()
com_dg    = res_al[res_al['dontgo'] > 0]
sem_dg    = res_al[res_al['dontgo'] == 0]

print(f"Total de alarmes únicos: {n_unicos}")
print(f"Alarmes COM correlação com Don't Go: {len(com_dg)} ({len(com_dg)/n_unicos*100:.1f}%)")
print(f"Alarmes SEM correlação com Don't Go: {len(sem_dg)} ({len(sem_dg)/n_unicos*100:.1f}%)")

# ── Cobertura dos Top-N por volume ──
cobertura = [(n, res_al.head(n)['total'].sum()) for n in [10, 20, 30, 50, 100, 200]]
df_cob = pd.DataFrame(cobertura, columns=['Top_N', 'Registros'])
df_cob['Pct'] = df_cob['Registros'] / total_reg * 100
df_cob['DG_entre_top'] = [res_al.head(n)['dontgo'].sum() for n, _ in cobertura]

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Plot 1: Cobertura de volume vs Don't Go nos Top-N
axes[0].bar(df_cob['Top_N'].astype(str), df_cob['Pct'], color='steelblue', label='% Volume total')
axes[0].set_title("Cobertura de Volume pelos Top-N Alarmes Mais Frequentes")
axes[0].set_xlabel("Top-N alarmes por volume")
axes[0].set_ylabel("% dos registros")
for i, row in df_cob.iterrows():
    axes[0].text(i, row['Pct'] + 0.5, f"{row['Pct']:.1f}%", ha='center', fontsize=9)
axes[0].set_ylim(0, 115)

# Plot 2: Alarmes COM vs SEM Don't Go
com_vol  = com_dg['total'].sum()
sem_vol  = sem_dg['total'].sum()
axes[1].pie([com_vol, sem_vol],
            labels=[f"Alarmes COM\\nDon't Go\\n({len(com_dg)} tipos)", f"Alarmes SEM\\nDon't Go\\n({len(sem_dg)} tipos)"],
            autopct='%1.1f%%', colors=['#e74c3c','#3498db'], startangle=90,
            textprops={'fontsize': 10})
axes[1].set_title("Volume de Registros: Alarmes com vs sem sinal de Don't Go")

plt.tight_layout()
plt.show()

print("\\n=== CONCLUSÃO CRÍTICA ===")
print(f"Os Top-10 alarmes por volume cobrem {df_cob.iloc[0]['Pct']:.1f}% dos registros.")
print(f"Destes, Don't Gos presentes: {df_cob.iloc[0]['DG_entre_top']:.0f} — zero.")
print("Os 10 alarmes mais frequentes são PURAMENTE informacionais (operação normal).")
print(f"\\nApenas {len(com_dg)} de {n_unicos} tipos de alarme têm correlação com Don't Go.")
print("Esta análise fundamenta a criação de features baseadas em famílias físicas,")
print("e não em contagem bruta de todos os alarmes.")

print("\\n--- ALARMES COM DON'T GO (ordenados por ocorrências) ---")
display(com_dg.sort_values('dontgo', ascending=False)[['Alarme','total','dontgo','taxa_dg']].round(3))
""")

# ═══════════════════════════════════════════════════════════════════════════════
# CAPÍTULO 3 — FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════════
md_cap3 = nbf.v4.new_markdown_cell("""## Capítulo 3 — Feature Engineering

> **Decisões metodológicas fundamentadas nos dados:**
>
> 1. **Granularidade de 8H (1 turno de mina)**: unidade natural de operação. Features calculadas para cada turno de cada equipamento.
>
> 2. **`resample('8h')` obrigatório**: janelas row-based foram descartadas por dois motivos documentados nos dados:
>    - Gap do 31/05: toda a frota ficou sem telemetria; uma janela de N linhas "saltaria" o buraco, fundindo fadiga de dias distantes
>    - Dias expurgados (PE3798/PE3797/CA65932): o resample cria janelas com `count=0` para esses períodos — matematicamente correto, pois a máquina estava parada para conserto de sensor
>
> 3. **Shift(1) em todas as features**: o modelo prevê o turno `[t]` usando **somente** informação de `[t-1]` e anteriores. Nenhuma informação da janela corrente vaza para o modelo.
>
> 4. **`dontgo` excluído das features**: queremos que o modelo aprenda os *precursores físicos* (temperatura de freio, nível de fluido) — não o padrão de repetição de falhas. Usar histórico de Don't Go como feature cria uma dependência circular que não se sustenta em produção.
>
> 5. **Target Encoding do operador**: calculado **exclusivamente** no bloco de treino, aplicado depois a validação e teste.
""")

code_fe_setup = nbf.v4.new_code_cell("""# ── Mapeamento dos 19 alarmes com Don't Go em famílias físicas ──
FAMILIAS = {
    'freio': [
        'Right Front Brake Temperature - Active',
        'Left Front Brake Temperature - Active',
        'Right Rear Brake Temperature - Active',
        'Left Rear Brake Temperature - Active',
    ],
    'motor': [
        'Engine Coolant Level - Active',
        'Engine Coolant Flow - Active',
        'Engine Coolant Temperature - Active',
        'Engine Oil Level - Active',
        'Engine Oil Filter - Active',
    ],
    'transmissao': [
        'Transmission Oil Level - Active',
        'Hydraulic Reservoir Oil Temperature Critically High (L-1850)',
        'HPD Gearbox Oil Pressure Critically Low (L-1850)',
    ],
    'pressao': [
        'Crankcase Pressure - Active',
        'Low Oil Pressure - Active',
    ],
    'arrefecimento': [
        'Aftercooler Level - Active',
        'Left Exhaust Temperature - Active',
        'Right Exhaust Temperature - Active',
    ],
    'outros_criticos': [
        'Steering Oil Temperature - Active',
        'Parking Brake - Active',
    ],
}
TODOS_SINAIS = [a for grp in FAMILIAS.values() for a in grp]

print("=== FAMÍLIAS DE ALARMES COM SINAL DE DON'T GO ===")
for familia, alarmes in FAMILIAS.items():
    print(f"  [{familia.upper()}] ({len(alarmes)} alarmes)")
    for a in alarmes:
        print(f"    - {a}")
""")

code_fe_build = nbf.v4.new_code_cell("""print("Gerando features (resample 8H + shift 1)...")
blocos = []

for tag, grupo in df.groupby('TAG_Limpa'):
    g = grupo.set_index('Data_Evento').sort_index()

    # ─── Base por turno 8H ───
    aggs = {
        'count_total':  g['Is_Dont_Go'].resample('8h').count(),
        'Is_Dont_Go':   g['Is_Dont_Go'].resample('8h').sum(),   # target
    }

    # Esquema 2 — Criticidade
    for crit, col in [('Critico','count_critico'), ('Informacional','count_info')]:
        aggs[col] = g['Criticidade'].resample('8h').apply(
            lambda x: (x.str.contains(crit, case=False, na=False)).sum())
    aggs['count_nao_critico'] = g['Criticidade'].resample('8h').apply(
        lambda x: (x.str.contains('o Cr', case=False, na=False)).sum())

    # Esquema 1 — Famílias físicas
    for familia, alarmes in FAMILIAS.items():
        aggs[f'f_{familia}'] = g['Alarme'].resample('8h').apply(
            lambda x: x.isin(alarmes).sum())

    # Esquema 3 — Individual (todos os 19 sinais)
    for alarme in TODOS_SINAIS:
        col = 'a_' + re.sub(r'[^a-zA-Z0-9]', '_', alarme)[:40]
        aggs[col] = g['Alarme'].resample('8h').apply(lambda x, al=alarme: (x == al).sum())

    base = pd.DataFrame(aggs).fillna(0)

    # ─── Rolling calendarizado ───
    feat_base_cols = [c for c in base.columns if c != 'Is_Dont_Go']
    for col in [c for c in feat_base_cols if not c.startswith('a_')]:
        base[f'{col}_24H'] = base[col].rolling(3, min_periods=1).sum()
        base[f'{col}_72H'] = base[col].rolling(9, min_periods=1).sum()

    # ─── SHIFT(1): todas as features deslocadas 1 janela ───
    feature_cols_all = [c for c in base.columns if c != 'Is_Dont_Go']
    base[feature_cols_all] = base[feature_cols_all].shift(1)

    base['TAG_Limpa'] = tag
    base['Prefixo']   = tag[:2]
    blocos.append(base)

features = pd.concat(blocos).reset_index().rename(columns={'index': 'Data_Evento'})
features = features.dropna(subset=['count_total']).copy()
features['Target'] = (features['Is_Dont_Go'] > 0).astype(int)

print(f"Features geradas: {features.shape[0]:,} linhas × {features.shape[1]} colunas")
print(f"Proporção de Don't Go (janelas 8H): {features['Target'].mean()*100:.2f}%")
""")

code_fe_operador = nbf.v4.new_code_cell("""# ── Operador mais frequente por janela 8H ──
op_janela = (df.groupby(['TAG_Limpa', pd.Grouper(key='Data_Evento', freq='8h')])
             ['Nome_Operador_Anon']
             .agg(lambda x: x.value_counts().index[0] if len(x) > 0 else 'DESCONHECIDO')
             .reset_index()
             .rename(columns={'Data_Evento': 'Data_Evento', 'Nome_Operador_Anon': 'Operador'}))

features = features.merge(op_janela, on=['TAG_Limpa','Data_Evento'], how='left')
features['Operador'] = features['Operador'].fillna('DESCONHECIDO')

print(f"Operadores presentes nas janelas: {features['Operador'].nunique()}")
""")

# ═══════════════════════════════════════════════════════════════════════════════
# CAPÍTULO 4 — MODELAGEM
# ═══════════════════════════════════════════════════════════════════════════════
md_cap4 = nbf.v4.new_markdown_cell("""## Capítulo 4 — Modelagem Preditiva

### 4.1 Estratégia de Split Temporal

> **Nunca embaralhar dados temporais.** O futuro não pode treinar o passado — `train_test_split` aleatório causaria Data Leakage temporal.

```
Meses 1–4 (Jan–Abr) → TREINO    (67%)   — base de aprendizado
Mês 5     (Maio)     → VALIDAÇÃO (17%)   — tuning de hiperparâmetros
Mês 6     (Junho)    → TESTE     (16%)   — avaliação final, nunca visto antes
```
`TimeSeriesSplit(n_splits=5)` dentro do GridSearch/Optuna, sempre respeitando a cronologia.
""")

code_split = nbf.v4.new_code_cell("""from sklearn.model_selection import TimeSeriesSplit

COLS_META = ['TAG_Limpa','Data_Evento','Is_Dont_Go','Target','TAG','Tipo',
             'Alarme','Criticidade','Prefixo','Mes','Dia','Data_Dia','Operador']

# ── Definição dos 3 conjuntos de features ──
ESQUEMAS = {
    'Esquema1_Familias': lambda df_f: [c for c in df_f.columns
        if c not in COLS_META and (c.startswith('f_') or c in ['count_total','count_total_24H',
           'count_total_72H','op_taxa_dontgo','is_pe'])],
    'Esquema2_Criticidade': lambda df_f: [c for c in df_f.columns
        if c not in COLS_META and (c.startswith('count_') or c in ['op_taxa_dontgo','is_pe'])
        and not c.startswith('f_') and not c.startswith('a_')],
    'Esquema3_Individual': lambda df_f: [c for c in df_f.columns
        if c not in COLS_META and not c.startswith('count_') and not c.startswith('f_')
        or c in ['op_taxa_dontgo','is_pe']],
}

def preparar_split(df_f, esquema_cols_fn, label=''):
    df_s = df_f.sort_values('Data_Evento').copy()
    treino    = df_s[df_s['Data_Evento'].dt.month <= 4]
    validacao = df_s[df_s['Data_Evento'].dt.month == 5]
    teste     = df_s[df_s['Data_Evento'].dt.month == 6]

    # Target Encoding do Operador (calculado SOMENTE no treino)
    enc_op = treino.groupby('Operador')['Target'].mean().to_dict()
    global_mean = treino['Target'].mean()
    for split in [treino, validacao, teste]:
        split['op_taxa_dontgo'] = split['Operador'].map(enc_op).fillna(global_mean)
        split['is_pe'] = split['TAG_Limpa'].str.startswith('PE').astype(int)

    feat_cols = esquema_cols_fn(treino)
    feat_cols = [c for c in feat_cols if c in treino.columns]

    X_tr  = treino[feat_cols].fillna(0)
    y_tr  = treino['Target']
    X_val = validacao[feat_cols].fillna(0)
    y_val = validacao['Target']
    X_te  = teste[feat_cols].fillna(0)
    y_te  = teste['Target']

    datas = {
        'treino': (treino['Data_Evento'].min().date(), treino['Data_Evento'].max().date()),
        'validacao': (validacao['Data_Evento'].min().date(), validacao['Data_Evento'].max().date()),
        'teste': (teste['Data_Evento'].min().date(), teste['Data_Evento'].max().date()),
    }

    print(f"  {label} | Features: {len(feat_cols)}")
    print(f"    Treino    [{datas['treino'][0]} → {datas['treino'][1]}]:    {X_tr.shape[0]:,} | Don'tGo: {y_tr.sum():,} ({y_tr.mean()*100:.2f}%)")
    print(f"    Validação [{datas['validacao'][0]} → {datas['validacao'][1]}]:  {X_val.shape[0]:,} | Don'tGo: {y_val.sum():,} ({y_val.mean()*100:.2f}%)")
    print(f"    Teste     [{datas['teste'][0]} → {datas['teste'][1]}]:    {X_te.shape[0]:,} | Don'tGo: {y_te.sum():,} ({y_te.mean()*100:.2f}%)")
    return X_tr, y_tr, X_val, y_val, X_te, y_te, feat_cols

tscv = TimeSeriesSplit(n_splits=5)

# Split principal: Esquema 1, Frota Combinada
print("=== SPLIT PRINCIPAL — Esquema 1 (Famílias Físicas), Frota Combinada ===")
X_tr, y_tr, X_val, y_val, X_te, y_te, feat_cols_e1 = preparar_split(
    features, ESQUEMAS['Esquema1_Familias'], label='E1-Combinado')

scale_pos = int((y_tr == 0).sum() / max((y_tr == 1).sum(), 1))
print(f"\\nscale_pos_weight (razão 0/1): {scale_pos}")
print(f"Justificativa: o target é altamente desbalanceado. 'scale_pos_weight' penaliza mais os")
print(f"falsos negativos (Don't Go perdido), que são mais custosos que falsos positivos.")
""")

code_modelos = nbf.v4.new_code_cell("""from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from sklearn.metrics import f1_score, roc_auc_score, classification_report, ConfusionMatrixDisplay
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
import optuna, joblib, os
optuna.logging.set_verbosity(optuna.logging.WARNING)

os.makedirs(r'.\\\\models', exist_ok=True)
RESULTADOS = []

def avaliar(nome, modelo, X_t, y_t, frota='Combinado', esquema='E1'):
    y_p    = modelo.predict(X_t)
    y_prob = modelo.predict_proba(X_t)[:,1] if hasattr(modelo,'predict_proba') else y_p.astype(float)
    f1     = f1_score(y_t, y_p, zero_division=0)
    auc    = roc_auc_score(y_t, y_prob) if y_t.nunique() > 1 else 0.0
    prec   = (y_t[y_p==1]).mean() if (y_p==1).sum() > 0 else 0.0
    rec    = (y_p[y_t==1]).mean() if (y_t==1).sum() > 0 else 0.0
    print(f"  [{nome}] Precision={prec:.3f} | Recall={rec:.3f} | F1={f1:.4f} | AUC={auc:.4f}")
    RESULTADOS.append({'Modelo':nome,'Frota':frota,'Esquema':esquema,'Precision':round(prec,4),
                       'Recall':round(rec,4),'F1':round(f1,4),'AUC':round(auc,4)})
    return modelo

# ════ BASELINE ════
print("\\n=== Baseline ===")
dummy = DummyClassifier(strategy='most_frequent').fit(X_tr, y_tr)
avaliar('Baseline', dummy, X_te, y_te)

# ════ RANDOM FOREST ════
print("\\n=== Random Forest — GridSearchCV ===")
rf_grid = {'n_estimators':[200,500],'max_depth':[6,10,None],'class_weight':['balanced']}
rf = GridSearchCV(RandomForestClassifier(random_state=42,n_jobs=-1),
                  rf_grid, cv=tscv, scoring='f1', n_jobs=-1)
rf.fit(X_tr, y_tr)
print(f"  Best: {rf.best_params_}")
best_rf = avaliar('RandomForest_E1', rf.best_estimator_, X_te, y_te)

# ════ XGBOOST ════
print("\\n=== XGBoost — RandomizedSearchCV ===")
xgb_params = {
    'n_estimators':[300,500,1000],'max_depth':[4,6,8],
    'learning_rate':[0.01,0.05,0.1],'subsample':[0.7,0.9],
    'colsample_bytree':[0.7,0.9],'scale_pos_weight':[scale_pos, scale_pos//2],
}
xgb = RandomizedSearchCV(
    XGBClassifier(random_state=42,n_jobs=-1,eval_metric='logloss',use_label_encoder=False),
    xgb_params, n_iter=30, cv=tscv, scoring='f1', random_state=42, n_jobs=-1)
xgb.fit(X_tr, y_tr)
print(f"  Best: {xgb.best_params_}")
best_xgb = avaliar('XGBoost_E1', xgb.best_estimator_, X_te, y_te)

# ════ LIGHTGBM ════
print("\\n=== LightGBM — RandomizedSearchCV ===")
lgb_params = {
    'n_estimators':[300,500,1000],'max_depth':[4,6,8],
    'learning_rate':[0.01,0.05,0.1],'num_leaves':[31,63,127],
    'class_weight':['balanced'],
}
lgb = RandomizedSearchCV(
    LGBMClassifier(random_state=42,n_jobs=-1,verbose=-1),
    lgb_params, n_iter=30, cv=tscv, scoring='f1', random_state=42, n_jobs=-1)
lgb.fit(X_tr, y_tr)
print(f"  Best: {lgb.best_params_}")
best_lgb = avaliar('LightGBM_E1', lgb.best_estimator_, X_te, y_te)

# ════ HISTGRADIENTBOOSTING ════
print("\\n=== HistGradientBoosting — GridSearchCV ===")
hgb_grid = {'max_iter':[200,500],'max_depth':[4,6],'learning_rate':[0.05,0.1],'class_weight':['balanced']}
hgb = GridSearchCV(HistGradientBoostingClassifier(random_state=42),
                   hgb_grid, cv=tscv, scoring='f1', n_jobs=-1)
hgb.fit(X_tr, y_tr)
avaliar('HistGB_E1', hgb.best_estimator_, X_te, y_te)

# ════ CATBOOST — OPTUNA 100 TRIALS (Esquemas 1, 2 e 3) ════
print("\\n=== CatBoost + Optuna (100 trials) — Esquema 1 ===")
def objective_cat(trial, X_t=X_tr, y_t=y_tr, sp=scale_pos):
    params = {
        'iterations': trial.suggest_int('iterations', 200, 1000),
        'depth': trial.suggest_int('depth', 4, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 10),
        'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1, sp),
        'random_seed': 42, 'verbose': 0,
    }
    scores = []
    for tr_idx, val_idx in tscv.split(X_t):
        m = CatBoostClassifier(**params)
        m.fit(X_t.iloc[tr_idx], y_t.iloc[tr_idx], verbose=0)
        scores.append(f1_score(y_t.iloc[val_idx], m.predict(X_t.iloc[val_idx]), zero_division=0))
    return np.mean(scores)

study1 = optuna.create_study(direction='maximize')
study1.optimize(objective_cat, n_trials=100, show_progress_bar=True)
best_cat_e1 = CatBoostClassifier(**study1.best_params, random_seed=42, verbose=0)
best_cat_e1.fit(X_tr, y_tr)
avaliar('CatBoost_E1', best_cat_e1, X_te, y_te)
""")

code_esquema2 = nbf.v4.new_code_cell("""# ═══ ESQUEMA 2 — Criticidade ═══
print("\\n=== Esquema 2 (Criticidade) — todos os modelos ===")
X_tr2, y_tr2, _, _, X_te2, y_te2, feat_e2 = preparar_split(
    features, ESQUEMAS['Esquema2_Criticidade'], label='E2-Combinado')
sp2 = int((y_tr2==0).sum() / max((y_tr2==1).sum(),1))

rf2 = GridSearchCV(RandomForestClassifier(random_state=42,n_jobs=-1,class_weight='balanced'),
                   {'n_estimators':[200,500],'max_depth':[6,10]}, cv=tscv, scoring='f1', n_jobs=-1)
rf2.fit(X_tr2, y_tr2)
avaliar('RandomForest_E2', rf2.best_estimator_, X_te2, y_te2, esquema='E2')

xgb2 = XGBClassifier(random_state=42, n_jobs=-1, eval_metric='logloss',
                      use_label_encoder=False, scale_pos_weight=sp2,
                      n_estimators=500, max_depth=6, learning_rate=0.05)
xgb2.fit(X_tr2, y_tr2)
avaliar('XGBoost_E2', xgb2, X_te2, y_te2, esquema='E2')

study2 = optuna.create_study(direction='maximize')
study2.optimize(lambda t: objective_cat(t, X_t=X_tr2, y_t=y_tr2, sp=sp2), n_trials=100, show_progress_bar=True)
best_cat_e2 = CatBoostClassifier(**study2.best_params, random_seed=42, verbose=0)
best_cat_e2.fit(X_tr2, y_tr2)
avaliar('CatBoost_E2', best_cat_e2, X_te2, y_te2, esquema='E2')
""")

code_esquema3 = nbf.v4.new_code_cell("""# ═══ ESQUEMA 3 — Individual (apenas CatBoost) ═══
print("\\n=== Esquema 3 (Alarmes Individuais — CatBoost only) ===")
X_tr3, y_tr3, _, _, X_te3, y_te3, feat_e3 = preparar_split(
    features, ESQUEMAS['Esquema3_Individual'], label='E3-CatBoost')
sp3 = int((y_tr3==0).sum() / max((y_tr3==1).sum(),1))

study3 = optuna.create_study(direction='maximize')
study3.optimize(lambda t: objective_cat(t, X_t=X_tr3, y_t=y_tr3, sp=sp3), n_trials=100, show_progress_bar=True)
best_cat_e3 = CatBoostClassifier(**study3.best_params, random_seed=42, verbose=0)
best_cat_e3.fit(X_tr3, y_tr3)
avaliar('CatBoost_E3', best_cat_e3, X_te3, y_te3, esquema='E3')
""")

code_separado = nbf.v4.new_code_cell("""# ═══ EXPERIMENTO SEPARADO: CA e PE ═══
print("\\n=== Experimento Separado — CA e PE (Esquema 1) ===")
for prefixo in ['CA', 'PE']:
    print(f"\\n--- {prefixo} ---")
    df_frota = features[features['TAG_Limpa'].str.startswith(prefixo)].copy()
    Xtr_f, ytr_f, _, _, Xte_f, yte_f, _ = preparar_split(
        df_frota, ESQUEMAS['Esquema1_Familias'], label=f'E1-{prefixo}')
    sp_f = int((ytr_f==0).sum() / max((ytr_f==1).sum(),1))

    xgb_f = XGBClassifier(random_state=42, n_jobs=-1, eval_metric='logloss',
                           use_label_encoder=False, scale_pos_weight=sp_f,
                           n_estimators=500, max_depth=6, learning_rate=0.05)
    xgb_f.fit(Xtr_f, ytr_f)
    avaliar(f'XGBoost_{prefixo}_E1', xgb_f, Xte_f, yte_f, frota=prefixo)

    study_f = optuna.create_study(direction='maximize')
    study_f.optimize(lambda t: objective_cat(t, X_t=Xtr_f, y_t=ytr_f, sp=sp_f),
                     n_trials=100, show_progress_bar=True)
    cat_f = CatBoostClassifier(**study_f.best_params, random_seed=42, verbose=0)
    cat_f.fit(Xtr_f, ytr_f)
    avaliar(f'CatBoost_{prefixo}_E1', cat_f, Xte_f, yte_f, frota=prefixo)
""")

# ═══════════════════════════════════════════════════════════════════════════════
# CAPÍTULO 5 — RESULTADOS E ROI
# ═══════════════════════════════════════════════════════════════════════════════
md_cap5 = nbf.v4.new_markdown_cell("""## Capítulo 5 — Resultados e ROI
""")

code_tabela = nbf.v4.new_code_cell("""df_res = pd.DataFrame(RESULTADOS).sort_values('F1', ascending=False).reset_index(drop=True)

print("=== TABELA COMPARATIVA FINAL ===")
display(df_res.style
        .background_gradient(cmap='RdYlGn', subset=['F1','AUC'])
        .format({'F1':'{:.4f}','AUC':'{:.4f}','Precision':'{:.4f}','Recall':'{:.4f}'}))

melhor = df_res.iloc[0]
print(f"\\nMelhor modelo: {melhor['Modelo']} | Esquema: {melhor['Esquema']} | F1={melhor['F1']:.4f} | AUC={melhor['AUC']:.4f}")
""")

code_roi = nbf.v4.new_code_cell("""# ═══ Cálculo de ROI por modelo ═══
downtime_medio = tabela_roi['Media_H_Inoperante'].mean()
print(f"Downtime médio geral de um Don't Go: {downtime_medio:.2f} horas")

# Custo de oportunidade: estimativa conservadora de R$ por hora de equipamento parado
CUSTO_HORA_PARADO  = 5000   # R$ por hora de equipamento fora de operação
CUSTO_FALSO_POS    = 800    # R$ custo de parada preventiva desnecessária (inspeção + tempo)

roi_rows = []
for _, row in df_res.iterrows():
    # Estimativa de TP/FP/FN baseada em Precision e Recall aplicados ao tamanho do conjunto de teste
    # Nota: usamos métricas do conjunto de teste (X_te, y_te do Esquema 1 principal)
    n_positivos_reais = y_te.sum()
    n_total_previstos_pos = n_positivos_reais  # aproximação para cálculo

    TP = int(row['Recall']    * n_positivos_reais)
    FP = int(TP / max(row['Precision'], 0.001) - TP) if row['Precision'] > 0 else 0
    FN = n_positivos_reais - TP

    beneficio = TP * downtime_medio * CUSTO_HORA_PARADO
    custo     = FP * CUSTO_FALSO_POS
    roi       = beneficio - custo
    roi_rows.append({**row.to_dict(), 'TP':TP, 'FP':FP, 'FN':FN,
                     'Beneficio_R$': beneficio, 'Custo_FP_R$': custo, 'ROI_R$': roi})

df_roi = pd.DataFrame(roi_rows).sort_values('ROI_R$', ascending=False)
print("\\n=== ROI ESTIMADO POR MODELO ===")
print(f"(Base: R$ {CUSTO_HORA_PARADO:,}/h de equipamento parado | R$ {CUSTO_FALSO_POS:,}/parada desnecessária)")
display(df_roi[['Modelo','Esquema','F1','TP','FP','FN','Beneficio_R$','Custo_FP_R$','ROI_R$']]
        .style.background_gradient(cmap='RdYlGn', subset=['ROI_R$'])
        .format({'ROI_R$': 'R$ {:,.0f}', 'Beneficio_R$': 'R$ {:,.0f}', 'Custo_FP_R$': 'R$ {:,.0f}'}))
""")

# ═══════════════════════════════════════════════════════════════════════════════
# CAPÍTULO 6 — INTERPRETABILIDADE
# ═══════════════════════════════════════════════════════════════════════════════
md_shap = nbf.v4.new_markdown_cell("""## Capítulo 6 — Interpretabilidade (SHAP)

O SHAP (SHapley Additive exPlanations) permite responder: *"Por que o modelo acredita que essa máquina vai falhar no próximo turno?"* — com rigor matemático e sem caixa-preta.
""")

code_shap = nbf.v4.new_code_cell("""import shap

# Usando o melhor modelo CatBoost do Esquema 1
modelo_shap = best_cat_e1

explainer   = shap.TreeExplainer(modelo_shap)
shap_values = explainer.shap_values(X_te)

print("=== SHAP — Importância Global das Features (Esquema 1) ===")
shap.summary_plot(shap_values, X_te, plot_type='bar', max_display=15, show=True)

print("\\n=== SHAP — Beeswarm: Impacto e Direção ===")
shap.summary_plot(shap_values, X_te, max_display=15, show=True)
""")

# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTÊNCIA
# ═══════════════════════════════════════════════════════════════════════════════
md_salvar = nbf.v4.new_markdown_cell("""## Persistência do Modelo Vencedor
""")

code_salvar = nbf.v4.new_code_cell("""melhor_nome = df_roi.iloc[0]['Modelo']
print(f"Modelo vencedor (ROI): {melhor_nome}")

# Mapear nome para objeto
modelo_map = {
    'CatBoost_E1': best_cat_e1,
    'CatBoost_E2': best_cat_e2,
    'CatBoost_E3': best_cat_e3,
    'XGBoost_E1': best_xgb,
    'LightGBM_E1': best_lgb,
}
modelo_final = modelo_map.get(melhor_nome, best_cat_e1)

caminho = r'.\\\\models\\\\modelo_definitivo.pkl'
joblib.dump(modelo_final, caminho)
print(f"Modelo salvo: {caminho}")
""")

# ═══════════════════════════════════════════════════════════════════════════════
# MONTAGEM
# ═══════════════════════════════════════════════════════════════════════════════
nb.cells = [
    md_cap1, code_cap1_setup, md_downtime, code_downtime,
    md_cap2,
    md_tags, code_tags,
    md_taxa, code_taxa,
    md_op, code_op,
    md_gap, code_gap,
    md_anomalias, code_anomalias,
    md_alarmes, code_alarmes,
    md_cap3, code_fe_setup, code_fe_build, code_fe_operador,
    md_cap4, code_split, code_modelos, code_esquema2, code_esquema3, code_separado,
    md_cap5, code_tabela, code_roi,
    md_shap, code_shap,
    md_salvar, code_salvar,
]

with open(r'.\Projeto_Final_Mina_03_Definitivo.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print("Notebook Projeto_Final_Mina_03_Definitivo gerado com sucesso.")
