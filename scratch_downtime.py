import pandas as pd, glob, numpy as np

dfs = [pd.read_parquet(f, columns=['TAG','Data_Evento','Is_Dont_Go','Alarme','Criticidade'])
       for f in glob.glob(r'data/raw/Base/datasets/telemetria/*.parquet')]
df = pd.concat(dfs, ignore_index=True)
df['TAG_Limpa'] = df['TAG'].replace({'CA5926':'CA65926','CA5927':'CA65927'})
df['Data_Evento'] = pd.to_datetime(df['Data_Evento'])

df_ap = pd.read_parquet(r'data/raw/Base/datasets/apontamentos/desenvolver_apontamentos.parquet')
df_ap['Inicio'] = pd.to_datetime(df_ap['Inicio'])

# ── Foco em CA65908 ──
ca908 = df[df['TAG_Limpa']=='CA65908'].sort_values('Data_Evento')
print("=== CA65908 ===")
print(f"Total registros: {len(ca908):,}")
print(f"Periodo: {ca908['Data_Evento'].min()} ate {ca908['Data_Evento'].max()}")
print(f"Dont Go total: {ca908['Is_Dont_Go'].sum():,}")

# Distribuição mensal
print("\nRegistros por mes:")
print(ca908.groupby(ca908['Data_Evento'].dt.month).size().to_string())

# Ultimas ocorrencias antes de sumir
print("\nUltimos 20 eventos antes do silencio:")
print(ca908.tail(20)[['Data_Evento','Alarme','Is_Dont_Go']].to_string())

# Quais alarmes DontGo ela tinha?
print("\nAlarmes com DontGo na CA65908:")
print(ca908[ca908['Is_Dont_Go']==1]['Alarme'].value_counts().to_string())

# Apontamentos desta maquina
ap_908 = df_ap[df_ap['Tag']=='CA65908'].sort_values('Inicio')
print(f"\nApontamentos CA65908: {len(ap_908)}")
print("Ultimos apontamentos:")
print(ap_908.tail(10)[['Inicio','Fim','Classe']].to_string())

# ── Os ultimos dias de CA65908 ──
ultimos = ca908[ca908['Data_Evento'] >= ca908['Data_Evento'].max() - pd.Timedelta(days=7)]
print(f"\nUltima semana de CA65908: {len(ultimos)} registros")
print(ultimos.groupby('Alarme').size().sort_values(ascending=False).head(10).to_string())
