"""Atribuição data-driven por cadeia de Markov (efeito de remoção).

Cada jornada vira uma sequência START > canal_1 > ... > canal_n > CONV (ou NULL, se não
converteu). O crédito de um canal é quanto a probabilidade de conversão cai quando ele é
removido do grafo. É o mesmo princípio dos modelos data-driven das plataformas, só que
transparente e auditável.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd


def _transicoes(caminhos: list[tuple[list[str], bool]]) -> dict:
    cont = defaultdict(lambda: defaultdict(float))
    for passos, conv in caminhos:
        seq = ["START", *passos, "CONV" if conv else "NULL"]
        for a, b in zip(seq[:-1], seq[1:]):
            cont[a][b] += 1
    return {a: {b: n / sum(d.values()) for b, n in d.items()} for a, d in cont.items()}


def _prob_conversao(T: dict, removido: str | None = None, iters: int = 200) -> float:
    estados = sorted({s for a, d in T.items() for s in [a, *d]})
    idx = {s: i for i, s in enumerate(estados)}
    M = np.zeros((len(estados), len(estados)))
    for a, d in T.items():
        for b, p in d.items():
            destino = "NULL" if b == removido else b
            M[idx[a], idx[destino]] += p
    for s in ("CONV", "NULL"):
        M[idx[s], :] = 0
        M[idx[s], idx[s]] = 1
    if removido in idx:   # tráfego que entra no canal removido se perde
        M[idx[removido], :] = 0
        M[idx[removido], idx["NULL"]] = 1
    v = np.zeros(len(estados))
    v[idx["START"]] = 1
    for _ in range(iters):
        v = v @ M
    return float(v[idx["CONV"]])


def atribuir(sessoes: pd.DataFrame) -> pd.DataFrame:
    s = sessoes.sort_values("inicio_sessao")
    caminhos = []
    for _, g in s.groupby("user_pseudo_id", sort=False):
        canais, conv = [], False
        for canal, su in zip(g["canal"], g["sign_up"]):
            canais.append(canal)
            if su == 1:
                conv = True
                break
        caminhos.append((canais, conv))
    T = _transicoes(caminhos)
    base = _prob_conversao(T)
    canais = sorted({c for p, _ in caminhos for c in p})
    efeito = {c: 1 - _prob_conversao(T, c) / base for c in canais}
    total_conv = sum(conv for _, conv in caminhos)
    soma = sum(efeito.values())
    return (pd.DataFrame({"canal": canais,
                          "efeito_remocao": [efeito[c] for c in canais],
                          "conversoes": [total_conv * efeito[c] / soma for c in canais]})
            .assign(modelo="markov")
            .sort_values("conversoes", ascending=False))
