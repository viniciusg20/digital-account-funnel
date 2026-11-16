"""Teste A/B do onboarding: v1 (3 etapas) x v2 (2 etapas).

Métrica primária: conclusão do formulário (sign_up / begin_onboarding), por USUÁRIO
(unidade de randomização). Usar sessão inflaria o n e violaria a independência.

Análises:
- checagem de SRM (Sample Ratio Mismatch): a divisão 50/50 aconteceu de verdade?
- z-teste de duas proporções + IC 95% do lift absoluto e relativo
- tamanho de amostra necessário (poder 80%) para o efeito mínimo de interesse
- leitura bayesiana (Beta-Binomial): P(v2 > v1) e perda esperada
- segmentação por dispositivo (efeito heterogêneo)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest

RNG = np.random.default_rng(0)


def por_usuario(sessoes: pd.DataFrame) -> pd.DataFrame:
    # ordena para que "first" seja determinístico (dispositivo da 1ª sessão com o experimento)
    s = sessoes[sessoes["variante"].notna()].sort_values(["user_pseudo_id", "inicio_sessao"])
    return (s.groupby("user_pseudo_id")
             .agg(variante=("variante", "first"), device=("device", "first"),
                  iniciou=("begin_onboarding", "max"), converteu=("sign_up", "max"))
             .query("iniciou == 1"))


def srm(n_a: int, n_b: int) -> dict:
    chi2, p = stats.chisquare([n_a, n_b])
    return {"n_a": n_a, "n_b": n_b, "p_valor": float(p), "srm_detectado": bool(p < 0.001)}


def frequentista(xa, na, xb, nb, alpha=0.05) -> dict:
    pa, pb = xa / na, xb / nb
    z, p = proportions_ztest([xb, xa], [nb, na], alternative="two-sided")
    ep = np.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    zc = stats.norm.ppf(1 - alpha / 2)
    return {"conv_a": pa, "conv_b": pb, "lift_abs": pb - pa, "lift_rel": pb / pa - 1,
            "ic95_lift_abs": [pb - pa - zc * ep, pb - pa + zc * ep], "z": float(z), "p_valor": float(p),
            "significativo": bool(p < alpha)}


def amostra_necessaria(p_base: float, mde_rel: float, alpha=0.05, poder=0.8) -> int:
    es = proportion_effectsize(p_base * (1 + mde_rel), p_base)
    return int(np.ceil(NormalIndPower().solve_power(es, alpha=alpha, power=poder, ratio=1)))


def bayesiano(xa, na, xb, nb, n=200_000) -> dict:
    a = RNG.beta(1 + xa, 1 + na - xa, n)
    b = RNG.beta(1 + xb, 1 + nb - xb, n)
    return {"prob_b_melhor": float((b > a).mean()),
            "perda_esperada_escolher_b": float(np.maximum(a - b, 0).mean()),
            "lift_rel_mediano": float(np.median(b / a - 1)),
            "ic95_lift_rel": [float(np.quantile(b / a - 1, 0.025)), float(np.quantile(b / a - 1, 0.975))]}


def analisar(sessoes: pd.DataFrame) -> dict:
    u = por_usuario(sessoes)
    g = u.groupby("variante")["converteu"].agg(["sum", "count"])
    a, b = g.loc["v1_3_etapas"], g.loc["v2_2_etapas"]
    res = {
        "unidade": "usuário que iniciou o onboarding",
        "srm": srm(int(a["count"]), int(b["count"])),
        "frequentista": frequentista(a["sum"], a["count"], b["sum"], b["count"]),
        "bayesiano": bayesiano(a["sum"], a["count"], b["sum"], b["count"]),
        "amostra_por_braco_para_mde_5pct": amostra_necessaria(a["sum"] / a["count"], 0.05),
        "amostra_por_braco_para_mde_10pct": amostra_necessaria(a["sum"] / a["count"], 0.10),
        "por_dispositivo": {},
    }
    for dev, d in u.groupby("device"):
        gd = d.groupby("variante")["converteu"].agg(["sum", "count"])
        if {"v1_3_etapas", "v2_2_etapas"} <= set(gd.index):
            ad, bd = gd.loc["v1_3_etapas"], gd.loc["v2_2_etapas"]
            res["por_dispositivo"][dev] = frequentista(ad["sum"], ad["count"], bd["sum"], bd["count"])
    return res
