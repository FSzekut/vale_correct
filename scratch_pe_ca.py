import pandas as pd, glob, numpy as np

dfs = [pd.read_parquet(f, columns=['TAG','Data_Evento','Is_Dont_Go','Alarme','Criticidade'])
       for f in glob.glob(r'data/raw/Base/datasets/telemetria/*.parquet')]
df = pd.concat(dfs, ignore_index=True)
df['TAG_Limpa'] = df['TAG'].replace({'CA5926':'CA65926','CA5927':'CA65927'})
df['Prefixo'] = df['TAG_Limpa'].str[:2]
df['Data_Evento'] = pd.to_datetime(df['Data_Evento'])
df['Mes'] = df['Data_Evento'].dt.month
df['Dia'] = df['Data_Evento'].dt.day

# expurgo
df = df[~((df['TAG_Limpa']=='PE3798') & (df['Mes']==6) & (df['Dia']==29))]
df = df[~((df['TAG_Limpa']=='PE3797') & (df['Mes']==1) & (df['Dia']==12))]
df = df[~((df['TAG_Limpa']=='CA65932') & (df['Mes']==3) & (df['Dia']==26))]

print("=== DISTRIBUICAO GERAL POR FROTA ===")
for pref in ['CA','PE']:
    sub = df[df['Prefixo']==pref]
    dg = sub['Is_Dont_Go'].sum()
    n = len(sub)
    maq = sub['TAG_Limpa'].nunique()
    print(f"[{pref}] Equipamentos: {maq} | Registros: {n:,} | DontGo: {dg:,} ({dg/n*100:.4f}%)")

print("\n=== DONTGO POR EQUIPAMENTO PE ===")
pe_dg = (df[df['Prefixo']=='PE']
         .groupby('TAG_Limpa')
         .agg(total=('Is_Dont_Go','count'), dontgo=('Is_Dont_Go','sum'))
         .assign(taxa=lambda d: d['dontgo']/d['total'])
         .sort_values('dontgo', ascending=False))
print(pe_dg.to_string())

print("\n=== QUAIS DOS 19 ALARMES COM DONTGO SAO CA vs PE? ===")
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
            .groupby(['Alarme','Prefixo'])['Is_Dont_Go']
            .agg(['sum','count'])
            .reset_index()
            .rename(columns={'sum':'dontgo','count':'total'})
            .sort_values(['Alarme','Prefixo']))
print(al_frota.to_string())

print("\n=== JANELAS 8H COM DONTGO: CA vs PE (simulacao resample) ===")
import re
blocos = []
for tag, grupo in df.groupby('TAG_Limpa'):
    g = grupo.set_index('Data_Evento').sort_index()
    base = pd.DataFrame({
        'Is_Dont_Go': g['Is_Dont_Go'].resample('8h').sum(),
        'count': g['Is_Dont_Go'].resample('8h').count(),
    }).fillna(0)
    base['Target'] = (base['Is_Dont_Go'] > 0).astype(int)
    base['TAG_Limpa'] = tag
    base['Prefixo'] = tag[:2]
    blocos.append(base)
features = pd.concat(blocos).reset_index().rename(columns={'index':'Data_Evento'})
features['shift_ok'] = features.groupby('TAG_Limpa')['count'].shift(1)
features = features.dropna(subset=['shift_ok'])

print("Janelas 8H totais e com DontGo por frota:")
for pref in ['CA','PE']:
    sub = features[features['Prefixo']==pref]
    treino = sub[sub['Data_Evento'].dt.month <= 4]
    teste  = sub[sub['Data_Evento'].dt.month == 6]
    print(f"  [{pref}] Total: {len(sub):,} | DG%: {sub['Target'].mean()*100:.2f}% | "
          f"Treino DG: {treino['Target'].sum()} | Teste DG: {teste['Target'].sum()}")
