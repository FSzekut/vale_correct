"""Patch NB05: corrige chamadas a avaliar() onde o modelo foi passado como string."""
import json

NB_PATH = r'c:\TT\AntiGravity\Vale_\Projeto_Final_Mina_05_Custo_Assimetrico.ipynb'

with open(NB_PATH, 'r', encoding='utf-8') as f:
    nb = json.load(f)

FIXES = [
    ("avaliar('CatBoost','cat_com',Xte,yte,thr_com,tag='_COM_ispe')",
     "avaliar('CatBoost',cat_com,Xte,yte,thr_com,tag='_COM_ispe')"),
    ("avaliar('CatBoost','cat_sem',Xte2,yte2,thr_sem,tag='_SEM_ispe')",
     "avaliar('CatBoost',cat_sem,Xte2,yte2,thr_sem,tag='_SEM_ispe')"),
    ("avaliar(f'CatBoost_{pref}','cat_com_filt',Xte_p,y_te_p,thr_com,frota=pref,tag='_COM')",
     "avaliar(f'CatBoost_{pref}',cat_com,Xte_p,y_te_p,thr_com,frota=pref,tag='_COM')"),
    ("avaliar(f'CatBoost_{pref}','cat_sem_filt',Xte_p2,y_te_p2,thr_sem,frota=pref,tag='_SEM')",
     "avaliar(f'CatBoost_{pref}',cat_sem,Xte_p2,y_te_p2,thr_sem,frota=pref,tag='_SEM')"),
    # Também corrigir no avaliar da seção assimétrica (mesmo padrão)
    ("avaliar('CatBoost_Asym','',Xte,yte,thr_asym,tag='_geral')",
     "avaliar('CatBoost_Asym',cat_asym,Xte,yte,thr_asym,tag='_geral')"),
    ("avaliar(f'CatBoost_Asym_{pref}','',Xte_p,yte_p,thr_p,frota=pref,tag=f'_thr{thr_p:.2f}')",
     "avaliar(f'CatBoost_Asym_{pref}',cat_asym,Xte_p,yte_p,thr_p,frota=pref,tag=f'_thr{thr_p:.2f}')"),
]

total = 0
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])
    original = src
    for old, new in FIXES:
        if old in src:
            src = src.replace(old, new)
            print(f"  Fix aplicado (celula {i}): ...{old[-40:]}")
            total += 1
    if src != original:
        cell['source'] = src

with open(NB_PATH, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"\nTotal: {total} fix(es) aplicado(s). NB05 atualizado.")
