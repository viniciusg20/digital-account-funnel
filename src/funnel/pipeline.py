"""python -m funnel.pipeline [--simular] [--amostra]"""
from __future__ import annotations

import argparse
import json
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from . import ab_test, markov, sqlrun
from .config import FIGURES, LOOKER, OUT, REPORTS

log = logging.getLogger("funnel")
CORES = {"Paid Search": "#1f4e79", "Paid Social": "#c9a227", "Organic Search": "#2e8b57", "Direct": "#7f8c8d",
         "CRM / E-mail": "#8e44ad", "Afiliados": "#e67e22", "Influenciadores": "#c0392b", "Referral": "#5d8aa8"}
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold"})


def _salvar(fig, nome):
    fig.tight_layout()
    fig.savefig(FIGURES / nome, bbox_inches="tight")
    plt.close(fig)


def _brl(x, _p=None):
    return f"R$ {x:,.0f}".replace(",", ".")


def figuras(t: dict, ab: dict, attr: pd.DataFrame):
    # 1. funil
    f = t["funil_etapas"]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    y = np.arange(len(f))[::-1]
    cores = ["#1f4e79"] * 6 + ["#c9a227"] * 2          # site (GA4) x backend
    ax.barh(y, f["volume"], color=cores[:len(f)], height=0.7)
    ax.set_xscale("log")
    ax.set_xlim(1_000, f["volume"].max() * 8)
    ax.set_yticks(y, f["etapa"])
    for yi, (_, r) in zip(y, f.iterrows()):
        txt = f"{r['volume']:,.0f}".replace(",", ".")
        if pd.notna(r["conv_etapa_anterior"]):
            txt += f"   {r['conv_etapa_anterior']:.0%} da etapa anterior"
        ax.text(r["volume"] * 1.12, yi, txt, va="center", fontsize=9)
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_xticks([])
    ax.set_title("Funil de abertura de conta digital (azul: site/GA4 · dourado: core bancário) — escala log")
    _salvar(fig, "01_funil.png")

    # 2. conversão por canal x dispositivo
    fs = t["funil_sessao"].dropna(subset=["canal", "device"])
    p = fs.pivot_table(index="canal", columns="device", values="conv_sessao")
    p = p.loc[p.mean(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    yy = np.arange(len(p))
    ax.barh(yy - 0.2, p.get("desktop", 0), height=0.4, label="desktop", color="#1f4e79")
    ax.barh(yy + 0.2, p.get("mobile", 0), height=0.4, label="mobile", color="#c9a227")
    ax.set_yticks(yy, p.index)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    ax.set_title("Conversão sessão → cadastro por canal e dispositivo")
    ax.legend()
    _salvar(fig, "02_conversao_canal_device.png")

    # 3. CAC x taxa de ativação
    e = t["eficiencia_canal"]
    e = e[e["custo"] > 0]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for _, r in e.iterrows():
        ax.scatter(r["cac"], r["taxa_ativacao"], s=r["contas"] * 1.5, color=CORES.get(r["canal"], "#999"), alpha=0.8)
        ax.annotate(f"{r['canal']}\nROAS 12m {r['roas_12m']:.1f}x", (r["cac"], r["taxa_ativacao"]),
                    xytext=(22, 10), textcoords="offset points", fontsize=8,
                    arrowprops={"arrowstyle": "-", "color": "#999", "lw": 0.6})
    ax.margins(x=0.12, y=0.18)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_brl))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set_xlabel("CAC (custo por conta aberta)")
    ax.set_ylabel("Taxa de ativação (1º depósito)")
    ax.set_title("Eficiência dos canais pagos (tamanho = contas)")
    _salvar(fig, "03_cac_ativacao.png")

    # 4. atribuição: comparação de modelos
    a = pd.concat([t["atribuicao_regras"], attr[["modelo", "canal", "conversoes"]]])
    piv = a.pivot_table(index="canal", columns="modelo", values="conversoes", aggfunc="sum").fillna(0)
    ordem = ["first_click", "last_click", "last_non_direct_click", "linear", "position_based", "markov"]
    piv = piv[[c for c in ordem if c in piv]]
    piv = piv.loc[piv["markov"].sort_values().index]
    fig, ax = plt.subplots(figsize=(9, 5))
    piv.plot.barh(ax=ax, width=0.8, colormap="cividis")
    ax.set_title("Conversões atribuídas por modelo")
    ax.set_xlabel("contas atribuídas")
    ax.legend(fontsize=8, loc="lower right")
    _salvar(fig, "04_atribuicao_modelos.png")

    # 5. A/B
    fr = ab["frequentista"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.bar(["v1 (3 etapas)", "v2 (2 etapas)"], [fr["conv_a"], fr["conv_b"]], color=["#7f8c8d", "#1f4e79"])
    for i, v in enumerate([fr["conv_a"], fr["conv_b"]]):
        a1.text(i, v + 0.005, f"{v:.1%}", ha="center", fontweight="bold")
    a1.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    a1.set_title(f"Conclusão do onboarding · p = {fr['p_valor']:.4f}")
    lo, hi = fr["ic95_lift_abs"]
    disp = ab["por_dispositivo"]
    nomes = ["Total", *disp]
    vals = [fr["lift_abs"], *[d["lift_abs"] for d in disp.values()]]
    ics = [fr["ic95_lift_abs"], *[d["ic95_lift_abs"] for d in disp.values()]]
    a2.errorbar(vals, range(len(vals)), xerr=[[v - i[0] for v, i in zip(vals, ics)], [i[1] - v for v, i in zip(vals, ics)]],
                fmt="o", color="#1f4e79", capsize=4)
    a2.axvline(0, color="black", lw=0.8)
    a2.set_yticks(range(len(nomes)), nomes)
    a2.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=1))
    a2.set_title("Lift absoluto (IC 95%)")
    _salvar(fig, "05_teste_ab.png")

    # 6. coortes
    c = t["coortes"].set_index("semana_coorte")[["conta_s0", "conta_s1", "conta_s3", "ativo_s0", "ativo_s1", "ativo_s3"]]
    c.index = pd.to_datetime(c.index).strftime("%d/%m")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    im = ax.imshow(c.to_numpy(), aspect="auto", cmap="Blues")
    ax.set_xticks(range(c.shape[1]), ["conta 7d", "conta 14d", "conta 28d", "ativo 7d", "ativo 14d", "ativo 28d"])
    ax.set_yticks(range(len(c)), c.index)
    for i in range(c.shape[0]):
        for j in range(c.shape[1]):
            ax.text(j, i, f"{c.iat[i, j]:.1%}", ha="center", va="center", fontsize=7,
                    color="white" if c.iat[i, j] > c.to_numpy().max() * 0.6 else "black")
    ax.grid(False)
    ax.set_ylabel("semana da 1ª visita")
    ax.set_title("Coortes semanais: abertura de conta e ativação acumuladas")
    fig.colorbar(im, ax=ax, format=mtick.PercentFormatter(1.0))
    _salvar(fig, "06_coortes.png")


def exportar_looker(t: dict, attr: pd.DataFrame, ab: dict):
    """CSV prontos para subir no Google Sheets/BigQuery e conectar no Looker Studio."""
    s = t["sessoes"].copy()
    s["data"] = pd.to_datetime(s["inicio_sessao"]).dt.date
    diario = (s.groupby(["data", "canal", "device", "campanha"], dropna=False)
                .agg(sessoes=("session_key", "size"), engajadas=("engajada", "sum"), cliques_cta=("cta_click", "sum"),
                     inicios_onboarding=("begin_onboarding", "sum"), cadastros=("sign_up", "sum")).reset_index())
    diario.to_csv(LOOKER / "sessoes_diarias.csv", index=False)
    t["funil_etapas"].to_csv(LOOKER / "funil_etapas.csv", index=False)
    t["eficiencia_canal"].to_csv(LOOKER / "eficiencia_canal.csv", index=False)
    t["eficiencia_campanha"].to_csv(LOOKER / "eficiencia_campanha.csv", index=False)
    pd.concat([t["atribuicao_regras"], attr[["modelo", "canal", "conversoes"]]]).to_csv(LOOKER / "atribuicao.csv", index=False)
    t["qa_tracking"].to_csv(LOOKER / "qa_tracking.csv", index=False)
    t["coortes"].to_csv(LOOKER / "coortes.csv", index=False)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular", action="store_true", help="gera os dados sintéticos antes")
    ap.add_argument("--amostra", action="store_true", help="roda só com os 3 dias versionados")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    if args.simular:
        from . import simulate
        simulate.rodar()

    con = sqlrun.rodar(sqlrun.conectar(amostra=args.amostra))
    t = {n: con.execute(f"SELECT * FROM {n}").df() for n in sqlrun.TABELAS}
    ab = ab_test.analisar(t["sessoes"])
    attr = markov.atribuir(t["sessoes"])
    attr.to_csv(OUT / "atribuicao_markov.csv", index=False)
    figuras(t, ab, attr)
    exportar_looker(t, attr, ab)

    e = t["eficiencia_canal"]
    resumo = {
        "sessoes": int(len(t["sessoes"])),
        "usuarios": int(t["sessoes"]["user_pseudo_id"].nunique()),
        "funil": t["funil_etapas"].to_dict(orient="records"),
        "teste_ab": ab,
        "eficiencia_canal": e.to_dict(orient="records"),
        "atribuicao_markov": attr.to_dict(orient="records"),
        "qa_tracking": t["qa_tracking"].to_dict(orient="records"),
        "app": t["app_por_midia"].to_dict(orient="records"),
        "reconciliacao_mmp": t["reconciliacao_mmp"].to_dict(orient="records"),
    }
    (REPORTS / "resultados.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("pronto: reports/resultados.json, reports/figures/, looker_studio/dados/")


if __name__ == "__main__":
    main()
