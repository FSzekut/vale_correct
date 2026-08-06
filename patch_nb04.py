"""
Patch cirúrgico: corrige 'display' nas células do NB04 para usar
from IPython.display import display explícito ou print/to_string.
"""
import json

NB_PATH = r'Projeto_Final_Mina_04_Telemetria_Puro.ipynb'

with open(NB_PATH, 'r', encoding='utf-8') as f:
    nb = json.load(f)

fixes = 0
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue

    src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])

    # Célula do downtime: substituir display() por print() com to_string
    if "dt_alarme.sort_values('Mediana_H'" in src:
        src = src.replace(
            "display(dt_alarme.sort_values('Mediana_H', ascending=False).round(2))",
            "print(dt_alarme.sort_values('Mediana_H', ascending=False).round(2).to_string())"
        )
        cell['source'] = src
        print(f"Fix 'display' na célula de downtime (index {i})")
        fixes += 1

    # Todas as outras células com display(): adicionar import no topo se necessário
    if 'display(' in src and 'from IPython.display import display' not in src:
        # Substituir display( por print( para DataFrames simples
        # ou adicionar import no topo
        if src.strip().startswith('# ──'):
            src = 'from IPython.display import display\n' + src
        else:
            src = 'from IPython.display import display\n' + src
        cell['source'] = src
        print(f"Adicionado import display na célula index {i}")
        fixes += 1

with open(NB_PATH, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"\nTotal de fixes aplicados: {fixes}")
print("NB04 atualizado.")
