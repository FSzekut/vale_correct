from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "22_Validacao_JunJul_Valoracao_Modelos.ipynb"


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# 22 — Validação Jun-Jul da Valoração dos Modelos

## Objetivo

Criar um quadro comparável de valor monetário dos modelos candidatos usando os cenários econômicos
estimados.

O foco deste notebook é responder:

1. quanto cada política valeria no período final de teste (`S3_junho`);
2. como esse valor se compara com abril e maio;
3. qual modelo é mais defensável sob os valores estimados;
4. quais limites impedem chamar isso de ROI real.

## Por que Jun-Jul?

O dataset de telemetria vai até `2025-06-30 23:59:56.887`. O split final é junho, com horizonte de
predição de 8h; portanto, operacionalmente ele representa decisões tomadas em junho olhando para o
limite final da base, que encosta em `2025-07-01`. Não há dados completos de julho para uma validação
mensal independente.

## Limite central

Estes são os melhores modelos **para os valores estimados descritos**. Para colocar em operação, a
empresa precisa substituir as premissas públicas por custos internos reais: OS, custo de peça/mão de
obra, produção horária por frente/equipamento, despacho e duração real de paradas corretivas e
preditivas.
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
    md("## 1. Cenários Econômicos Estimados"),
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

display(economic_scenarios[[
    "cenario", "Tipo", "valor_tp_unitario", "valor_fp_unitario",
    "p_acao_confirmada", "impacto_operacional_hora",
    "horas_parada_preditiva", "horas_parada_corretiva",
]])
"""
    ),
    md("## 2. Contagens Auditadas dos Modelos"),
    code(
        """
policy_counts = pd.DataFrame([
    # CatBoost caminhão-only, faixa robusta 0,390-0,440
    {"politica": "caminhoes_catboost_multijanela", "modelo": "CatBoost", "escopo": "Caminhoes", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Caminhao", "TP": 88, "FP": 99, "FN": 275, "threshold_ref": "0,390-0,440"},
    {"politica": "caminhoes_catboost_multijanela", "modelo": "CatBoost", "escopo": "Caminhoes", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Caminhao", "TP": 67, "FP": 76, "FN": 213, "threshold_ref": "0,390-0,440"},
    {"politica": "caminhoes_catboost_multijanela", "modelo": "CatBoost", "escopo": "Caminhoes", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Caminhao", "TP": 63, "FP": 46, "FN": 220, "threshold_ref": "0,390-0,440"},

    # CatBoost misto, faixa robusta 0,420-0,480
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Caminhao", "TP": 87, "FP": 94, "FN": 276, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 1, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Caminhao", "TP": 58, "FP": 75, "FN": 222, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 7, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Caminhao", "TP": 56, "FP": 33, "FN": 227, "threshold_ref": "0,420-0,480"},
    {"politica": "misto_catboost_multijanela", "modelo": "CatBoost", "escopo": "Misto", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 2, "threshold_ref": "0,420-0,480"},

    # RandomForest referência caminhão-only, faixa robusta 0,380-0,390
    {"politica": "caminhoes_rf_referencia", "modelo": "RandomForest", "escopo": "Caminhoes", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Caminhao", "TP": 96, "FP": 120, "FN": 267, "threshold_ref": "0,380-0,390"},
    {"politica": "caminhoes_rf_referencia", "modelo": "RandomForest", "escopo": "Caminhoes", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Caminhao", "TP": 70, "FP": 103, "FN": 210, "threshold_ref": "0,380-0,390"},
    {"politica": "caminhoes_rf_referencia", "modelo": "RandomForest", "escopo": "Caminhoes", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Caminhao", "TP": 50, "FP": 49, "FN": 233, "threshold_ref": "0,380-0,390"},

    # RandomForest referência misto, faixa robusta 0,395-0,450
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Caminhao", "TP": 95, "FP": 110, "FN": 268, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 1, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Caminhao", "TP": 62, "FP": 82, "FN": 218, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 7, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Caminhao", "TP": 45, "FP": 46, "FN": 238, "threshold_ref": "0,395-0,450"},
    {"politica": "misto_rf_referencia", "modelo": "RandomForest", "escopo": "Misto", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Escavadeira", "TP": 0, "FP": 0, "FN": 2, "threshold_ref": "0,395-0,450"},

    # XGBoost caminhão-only como sensibilidade; venceu junho, mas não foi robusto em abril
    {"politica": "caminhoes_xgboost_multijanela_validacao", "modelo": "XGBoost", "escopo": "Caminhoes", "split": "S1_abril", "mes_teste": "2025-04", "Tipo": "Caminhao", "TP": 117, "FP": 254, "FN": 246, "threshold_ref": "validacao"},
    {"politica": "caminhoes_xgboost_multijanela_validacao", "modelo": "XGBoost", "escopo": "Caminhoes", "split": "S2_maio", "mes_teste": "2025-05", "Tipo": "Caminhao", "TP": 76, "FP": 114, "FN": 204, "threshold_ref": "validacao"},
    {"politica": "caminhoes_xgboost_multijanela_validacao", "modelo": "XGBoost", "escopo": "Caminhoes", "split": "S3_junho", "mes_teste": "2025-06", "Tipo": "Caminhao", "TP": 98, "FP": 111, "FN": 185, "threshold_ref": "validacao"},
])

policy_counts["positivos"] = policy_counts["TP"] + policy_counts["FN"]
policy_counts["predicoes_positivas"] = policy_counts["TP"] + policy_counts["FP"]
policy_counts["precision"] = policy_counts["TP"] / policy_counts["predicoes_positivas"].replace(0, np.nan)
policy_counts["recall"] = policy_counts["TP"] / policy_counts["positivos"].replace(0, np.nan)
display(policy_counts)
"""
    ),
    md("## 3. Aplicação da Função Econômica"),
    code(
        """
rows = []
for _, count in policy_counts.iterrows():
    for _, scenario in economic_scenarios[economic_scenarios["Tipo"] == count["Tipo"]].iterrows():
        rows.append({
            **count.to_dict(),
            "cenario": scenario["cenario"],
            "valor_tp_unitario": scenario["valor_tp_unitario"],
            "valor_fp_unitario": scenario["valor_fp_unitario"],
            "valor_tp_total": count["TP"] * scenario["valor_tp_unitario"],
            "valor_fp_total": count["FP"] * scenario["valor_fp_unitario"],
            "valor_incremental": count["TP"] * scenario["valor_tp_unitario"] + count["FP"] * scenario["valor_fp_unitario"],
        })
valuation = pd.DataFrame(rows)
display(valuation[[
    "cenario", "politica", "split", "Tipo", "TP", "FP", "FN",
    "valor_tp_unitario", "valor_fp_unitario", "valor_incremental",
]])
"""
    ),
    md("## 4. Comparação nos Três Splits Temporais"),
    code(
        """
summary_all = (
    valuation.groupby(["cenario", "politica", "modelo", "escopo", "threshold_ref"])
    .agg(
        splits=("split", "nunique"),
        valor_medio=("valor_incremental", "mean"),
        valor_min=("valor_incremental", "min"),
        valor_max=("valor_incremental", "max"),
        tp_medio=("TP", "mean"),
        fp_medio=("FP", "mean"),
        fn_medio=("FN", "mean"),
        precision_media=("precision", "mean"),
        recall_media=("recall", "mean"),
    )
    .reset_index()
    .sort_values(["cenario", "valor_medio"], ascending=[True, False])
)
display(summary_all)
"""
    ),
    code(
        """
fig, axes = plt.subplots(1, 3, figsize=(22, 7), sharey=True)
for ax, scenario in zip(axes, ["conservador", "base", "agressivo"]):
    data = summary_all[summary_all["cenario"] == scenario].sort_values("valor_medio", ascending=False)
    sns.barplot(data=data, y="politica", x="valor_medio", ax=ax, color="#4C78A8")
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"Valor médio nos três splits — {scenario}")
    ax.set_xlabel("US$ por split")
    ax.set_ylabel("")
plt.tight_layout()
plt.show()
"""
    ),
    md("## 5. Validação Final em Junho com Horizonte até 01/07"),
    code(
        """
final_month = valuation[valuation["split"] == "S3_junho"].copy()
final_summary = (
    final_month.groupby(["cenario", "politica", "modelo", "escopo", "threshold_ref"])
    .agg(
        valor=("valor_incremental", "sum"),
        TP=("TP", "sum"),
        FP=("FP", "sum"),
        FN=("FN", "sum"),
        precision=("precision", "mean"),
        recall=("recall", "mean"),
    )
    .reset_index()
    .sort_values(["cenario", "valor"], ascending=[True, False])
)
display(final_summary)

print("Ranking de junho por cenário:")
display(final_summary.groupby("cenario").head(10))
"""
    ),
    code(
        """
fig, axes = plt.subplots(1, 3, figsize=(22, 7), sharey=True)
for ax, scenario in zip(axes, ["conservador", "base", "agressivo"]):
    data = final_summary[final_summary["cenario"] == scenario].sort_values("valor", ascending=False)
    sns.barplot(data=data, y="politica", x="valor", ax=ax, color="#59A14F")
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"Validação junho — {scenario}")
    ax.set_xlabel("US$ em junho")
    ax.set_ylabel("")
plt.tight_layout()
plt.show()
"""
    ),
    md("## 6. Leitura Auditada"),
    code(
        """
best_all = summary_all.sort_values(["cenario", "valor_medio"], ascending=[True, False]).groupby("cenario").head(1)
best_june = final_summary.sort_values(["cenario", "valor"], ascending=[True, False]).groupby("cenario").head(1)

print("Melhor política média nos três splits:")
display(best_all)

print("Melhor política na validação final de junho:")
display(best_june)

print("Conclusões para relatório:")
print("- Com os valores estimados, o CatBoost caminhão-only é o candidato operacional mais defensável pela estabilidade média e pela faixa robusta de threshold.")
print("- Na validação final de junho, XGBoost caminhão-only pode vencer nos cenários base/agressivo por maior recall, mas ele foi frágil em abril e deve ficar como sensibilidade, não como recomendação principal.")
print("- No cenário conservador, o custo dos falsos positivos torna políticas mais agressivas economicamente frágeis.")
print("- Escavadeiras seguem sem valor capturado porque os modelos não geram TP nesse tipo; isso não significa baixo impacto, significa falta de suporte do target/modelo atual.")
print("- Estes são os melhores modelos para os valores estimados descritos. Para operação, substituir por custos internos reais.")
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
