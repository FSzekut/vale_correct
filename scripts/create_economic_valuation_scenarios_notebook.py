from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "21_Valoracao_Cenarios_Economicos.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 21 — Valoração por Cenários Econômicos

## Objetivo

Valorar monetariamente as políticas candidatas usando:

- resultados já auditados no notebook `20_Explicabilidade_E_Politica_Final.ipynb`;
- cenários econômicos documentados em `docs/PREMISSAS_ECONOMICAS_EXTERNAS.md`;
- matriz de decisão baseada em `TP`, `FP`, `FN` e `TN`.

Este notebook é intencionalmente leve: ele não reconstrói a base, não retreina modelos e não recalcula
probabilidades. O foco é aplicar a função econômica aos resultados já gerados.

## Limites

- os valores são simulação de cenário, não ROI real;
- os custos não são dados internos da Vale;
- `Is_Dont_Go` não é falha confirmada;
- `Manutenção` é proxy operacional, não causalidade;
- escavadeiras continuam sem recomendação operacional com este target.
"""
    ),
    code(
        """
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from IPython.display import display

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 200)
pd.set_option("display.max_rows", 300)
"""
    ),
    md("## 1. Premissas Econômicas"),
    code(
        """
economic_scenarios = pd.DataFrame([
    {
        "cenario": "conservador",
        "Tipo": "Caminhao",
        "p_acao_confirmada": 0.40,
        "custo_intervencao_preditiva": 15000.0,
        "custo_manutencao_corretiva": 40000.0,
        "impacto_operacional_hora": 15000.0,
        "horas_parada_preditiva": 1.0,
        "horas_parada_corretiva": 3.0,
    },
    {
        "cenario": "base",
        "Tipo": "Caminhao",
        "p_acao_confirmada": 0.655,
        "custo_intervencao_preditiva": 10000.0,
        "custo_manutencao_corretiva": 50000.0,
        "impacto_operacional_hora": 30000.0,
        "horas_parada_preditiva": 1.0,
        "horas_parada_corretiva": 4.0,
    },
    {
        "cenario": "agressivo",
        "Tipo": "Caminhao",
        "p_acao_confirmada": 0.75,
        "custo_intervencao_preditiva": 10000.0,
        "custo_manutencao_corretiva": 80000.0,
        "impacto_operacional_hora": 45000.0,
        "horas_parada_preditiva": 1.0,
        "horas_parada_corretiva": 6.0,
    },
    {
        "cenario": "conservador",
        "Tipo": "Escavadeira",
        "p_acao_confirmada": 0.20,
        "custo_intervencao_preditiva": 35000.0,
        "custo_manutencao_corretiva": 100000.0,
        "impacto_operacional_hora": 60000.0,
        "horas_parada_preditiva": 2.0,
        "horas_parada_corretiva": 6.0,
    },
    {
        "cenario": "base",
        "Tipo": "Escavadeira",
        "p_acao_confirmada": 0.20,
        "custo_intervencao_preditiva": 25000.0,
        "custo_manutencao_corretiva": 150000.0,
        "impacto_operacional_hora": 100000.0,
        "horas_parada_preditiva": 2.0,
        "horas_parada_corretiva": 8.0,
    },
    {
        "cenario": "agressivo",
        "Tipo": "Escavadeira",
        "p_acao_confirmada": 0.40,
        "custo_intervencao_preditiva": 25000.0,
        "custo_manutencao_corretiva": 250000.0,
        "impacto_operacional_hora": 150000.0,
        "horas_parada_preditiva": 2.0,
        "horas_parada_corretiva": 12.0,
    },
])

economic_scenarios["valor_tp_unitario"] = economic_scenarios["p_acao_confirmada"] * (
    economic_scenarios["custo_manutencao_corretiva"]
    + economic_scenarios["impacto_operacional_hora"] * economic_scenarios["horas_parada_corretiva"]
) - (
    economic_scenarios["custo_intervencao_preditiva"]
    + economic_scenarios["p_acao_confirmada"]
    * economic_scenarios["impacto_operacional_hora"]
    * economic_scenarios["horas_parada_preditiva"]
)
economic_scenarios["valor_fp_unitario"] = -(
    economic_scenarios["custo_intervencao_preditiva"]
    + economic_scenarios["impacto_operacional_hora"]
    * economic_scenarios["horas_parada_preditiva"]
)
display(economic_scenarios)
"""
    ),
    md("## 2. Resultados Auditados do Notebook 20"),
    code(
        """
# Resultados do notebook 20 usando faixas robustas ou thresholds candidatos finais.
# Valores por split no teste. Escavadeiras nos modelos mistos tiveram 0 TP e 0 FP nos candidatos finais.
policy_counts = pd.DataFrame([
    # CatBoost caminhão-only, threshold robusto 0,390-0,440
    {"politica": "caminhoes_catboost_multijanela", "modelo": "CatBoost", "escopo": "Caminhoes", "split": "S1_abril", "Tipo": "Caminhao", "TP": 88, "FP": 99, "FN": 275, "TN": np.nan, "threshold_ref": "0,390-0,440"},
    {"politica": "caminhoes_catboost_multijanela", "modelo": "CatBoost", "escopo": "Caminhoes", "split": "S2_maio", "Tipo": "Caminhao", "TP": 67, "FP": 76, "FN": 213, "TN": np.nan, "threshold_ref": "0,390-0,440"},
    {"politica": "caminhoes_catboost_multijanela", "modelo": "CatBoost", "escopo": "Caminhoes", "split": "S3_junho", "Tipo": "Caminhao", "TP": 63, "FP": 46, "FN": 220, "TN": np.nan, "threshold_ref": "0,390-0,440"},

    # CatBoost misto, threshold robusto 0,420-0,480
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S1_abril", "Tipo": "Caminhao", "TP": 87, "FP": 94, "FN": 276, "TN": np.nan, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S1_abril", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 1, "TN": np.nan, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S2_maio", "Tipo": "Caminhao", "TP": 58, "FP": 75, "FN": 222, "TN": np.nan, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S2_maio", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 7, "TN": np.nan, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S3_junho", "Tipo": "Caminhao", "TP": 56, "FP": 33, "FN": 227, "TN": np.nan, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S3_junho", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 2, "TN": np.nan, "threshold_ref": "0,420-0,480"},

    # RandomForest referência caminhão-only, threshold robusto 0,380-0,390
    {"politica": "caminhoes_rf_referencia", "modelo": "RandomForest", "escopo": "Caminhoes", "split": "S1_abril", "Tipo": "Caminhao", "TP": 96, "FP": 120, "FN": 267, "TN": np.nan, "threshold_ref": "0,380-0,390"},
    {"politica": "caminhoes_rf_referencia", "modelo": "RandomForest", "escopo": "Caminhoes", "split": "S2_maio", "Tipo": "Caminhao", "TP": 70, "FP": 103, "FN": 210, "TN": np.nan, "threshold_ref": "0,380-0,390"},
    {"politica": "caminhoes_rf_referencia", "modelo": "RandomForest", "escopo": "Caminhoes", "split": "S3_junho", "Tipo": "Caminhao", "TP": 50, "FP": 49, "FN": 233, "TN": np.nan, "threshold_ref": "0,380-0,390"},

    # RandomForest referência misto, threshold robusto 0,395-0,450
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S1_abril", "Tipo": "Caminhao", "TP": 95, "FP": 110, "FN": 268, "TN": np.nan, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S1_abril", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 1, "TN": np.nan, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S2_maio", "Tipo": "Caminhao", "TP": 62, "FP": 82, "FN": 218, "TN": np.nan, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S2_maio", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 7, "TN": np.nan, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S3_junho", "Tipo": "Caminhao", "TP": 45, "FP": 46, "FN": 238, "TN": np.nan, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S3_junho", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 2, "TN": np.nan, "threshold_ref": "0,395-0,450"},

    # XGBoost caminhão-only como sensibilidade, threshold escolhido na validação no notebook 20
    {"politica": "caminhoes_xgboost_multijanela_validacao", "modelo": "XGBoost", "escopo": "Caminhoes", "split": "S1_abril", "Tipo": "Caminhao", "TP": 117, "FP": 254, "FN": 246, "TN": np.nan, "threshold_ref": "validacao"},
    {"politica": "caminhoes_xgboost_multijanela_validacao", "modelo": "XGBoost", "escopo": "Caminhoes", "split": "S2_maio", "Tipo": "Caminhao", "TP": 76, "FP": 114, "FN": 204, "TN": np.nan, "threshold_ref": "validacao"},
    {"politica": "caminhoes_xgboost_multijanela_validacao", "modelo": "XGBoost", "escopo": "Caminhoes", "split": "S3_junho", "Tipo": "Caminhao", "TP": 98, "FP": 111, "FN": 185, "TN": np.nan, "threshold_ref": "validacao"},
])

policy_counts["positivos"] = policy_counts["TP"] + policy_counts["FN"]
policy_counts["predicoes_positivas"] = policy_counts["TP"] + policy_counts["FP"]
policy_counts["precision"] = policy_counts["TP"] / policy_counts["predicoes_positivas"].replace(0, np.nan)
policy_counts["recall"] = policy_counts["TP"] / policy_counts["positivos"].replace(0, np.nan)
display(policy_counts)
"""
    ),
    md("## 3. Função de Valoração"),
    code(
        """
def value_policy(counts, scenarios):
    rows = []
    for _, count in counts.iterrows():
        for _, scenario in scenarios[scenarios["Tipo"] == count["Tipo"]].iterrows():
            rows.append({
                **count.to_dict(),
                "cenario": scenario["cenario"],
                "valor_tp_unitario": scenario["valor_tp_unitario"],
                "valor_fp_unitario": scenario["valor_fp_unitario"],
                "valor_tp_total": count["TP"] * scenario["valor_tp_unitario"],
                "valor_fp_total": count["FP"] * scenario["valor_fp_unitario"],
                "valor_incremental": count["TP"] * scenario["valor_tp_unitario"] + count["FP"] * scenario["valor_fp_unitario"],
            })
    return pd.DataFrame(rows)

valuation = value_policy(policy_counts, economic_scenarios)
display(valuation[[
    "cenario", "politica", "split", "Tipo", "TP", "FP", "FN",
    "valor_tp_unitario", "valor_fp_unitario", "valor_tp_total",
    "valor_fp_total", "valor_incremental",
]])
"""
    ),
    md("## 4. Resultado por Política e Cenário"),
    code(
        """
valuation_summary = (
    valuation.groupby(["cenario", "politica", "modelo", "escopo", "threshold_ref"])
    .agg(
        splits=("split", "nunique"),
        valor_medio=("valor_incremental", "mean"),
        valor_min=("valor_incremental", "min"),
        valor_max=("valor_incremental", "max"),
        valor_total_3_splits=("valor_incremental", "sum"),
        tp_medio=("TP", "mean"),
        fp_medio=("FP", "mean"),
        fn_medio=("FN", "mean"),
        precision_media=("precision", "mean"),
        recall_media=("recall", "mean"),
    )
    .reset_index()
    .sort_values(["cenario", "valor_medio"], ascending=[True, False])
)
display(valuation_summary)

print("Ranking por cenário:")
display(valuation_summary.groupby("cenario").head(10))
"""
    ),
    code(
        """
pivot_value = valuation_summary.pivot_table(
    index="politica",
    columns="cenario",
    values="valor_medio",
    aggfunc="mean",
).reset_index()
display(pivot_value)

fig, axes = plt.subplots(1, 3, figsize=(22, 7), sharey=True)
for ax, scenario in zip(axes, ["conservador", "base", "agressivo"]):
    data = valuation_summary[valuation_summary["cenario"] == scenario].sort_values("valor_medio", ascending=False)
    sns.barplot(data=data, y="politica", x="valor_medio", ax=ax, color="#4C78A8")
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"Cenário {scenario}")
    ax.set_xlabel("Valor incremental médio por split")
    ax.set_ylabel("")
plt.tight_layout()
plt.show()
"""
    ),
    md("## 5. Contribuição por Tipo"),
    code(
        """
type_contribution = (
    valuation.groupby(["cenario", "politica", "Tipo"])
    .agg(
        valor_medio=("valor_incremental", "mean"),
        valor_total=("valor_incremental", "sum"),
        tp_total=("TP", "sum"),
        fp_total=("FP", "sum"),
        fn_total=("FN", "sum"),
    )
    .reset_index()
    .sort_values(["cenario", "valor_medio"], ascending=[True, False])
)
display(type_contribution)
"""
    ),
    md("## 6. Leitura Auditada"),
    code(
        """
best_by_scenario = valuation_summary.sort_values(["cenario", "valor_medio"], ascending=[True, False]).groupby("cenario").head(1)
display(best_by_scenario)

print("Conclusões:")
print("- No cenário conservador, políticas com muitos FP podem ficar negativas ou pouco atrativas.")
print("- No cenário base, o CatBoost caminhão-only tende a ser a política mais robusta entre as opções auditadas.")
print("- No cenário agressivo, modelos com maior recall ganham valor, mas o custo de FP ainda precisa ser controlado.")
print("- Escavadeiras não geram valor nos candidatos finais porque os modelos não acionam TP nesse tipo com o target atual.")
print("- Estes valores são simulação de cenário; ROI real exige custos internos, ordens de serviço e produção por frente/equipamento.")
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
