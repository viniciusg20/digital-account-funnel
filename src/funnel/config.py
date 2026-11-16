"""Parâmetros do cenário simulado: um banco digital fictício ("Banco Aurum") captando
contas digitais por mídia paga, orgânico, CRM, afiliados e influenciadores."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("FUNNEL_DATA", ROOT / "data"))
GA4 = DATA / "ga4_export"          # events_AAAAMMDD.parquet (schema do export GA4 → BigQuery)
MMP = DATA / "mmp"                 # installs / in-app events no formato AppsFlyer raw data
MIDIA = DATA / "midia"             # custo diário por campanha
SAMPLE = ROOT / "data" / "sample"  # 3 dias versionados no Git
OUT = ROOT / "data" / "processed"
SQL = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
LOOKER = ROOT / "looker_studio" / "dados"

SEED = 7
INICIO = "2026-08-01"
DIAS = 61
USUARIOS = 90_000
DOMINIO = "https://aurum.example.com.br"


@dataclass(frozen=True)
class Canal:
    source: str
    medium: str
    campanhas: tuple[str, ...]
    peso: float          # participação na aquisição de novos usuários
    intencao: float      # multiplicador de conversão (qualidade do tráfego)
    pct_mobile: float
    cpc: float | None    # custo por clique (R$); None = sem mídia paga por clique


CANAIS = (
    Canal("google", "cpc", ("br_search_conta-digital_brand", "br_search_conta-digital_generic"), 0.20, 1.45, 0.62, 2.4),
    Canal("meta", "paid_social", ("br_social_conta-digital_prospecting", "br_social_investimentos_remarketing"), 0.20, 0.85, 0.88, 1.6),
    Canal("tiktok", "paid_social", ("br_social_conta-digital_jovens",), 0.09, 0.55, 0.95, 0.8),
    Canal("afiliados", "affiliate", ("br_affiliate_cashback",), 0.06, 1.10, 0.80, None),
    Canal("influenciador", "influencer", ("br_influencer_financas-pessoais",), 0.05, 0.95, 0.92, None),
    Canal("crm", "email", ("br_crm_investimentos_newsletter",), 0.05, 1.60, 0.55, None),
    Canal("google", "organic", ("(organic)",), 0.19, 1.15, 0.58, None),
    Canal("(direct)", "(none)", ("(direct)",), 0.12, 1.30, 0.50, None),
    Canal("blog-financas.com.br", "referral", ("(referral)",), 0.04, 1.00, 0.60, None),
)

# Custos fixos/variáveis de canais que não cobram por clique
CPA_AFILIADO = 55.0              # R$ por conta aberta
FEE_INFLUENCER_SEMANA = 7_000.0  # R$ por semana de campanha

# Teste A/B no onboarding: v1 (3 etapas) x v2 (formulário enxuto de 2 etapas)
LIFT_REAL_V2 = 0.10              # +10% relativo na conclusão do formulário

TAXA_APROVACAO_KYC = 0.86
TAXA_PRIMEIRO_DEPOSITO = 0.58
MARGEM_SOBRE_DEPOSITO = 0.035    # receita anual estimada por R$ depositado (spread + tarifas)

for _p in (GA4, MMP, MIDIA, SAMPLE, OUT, FIGURES, LOOKER):
    _p.mkdir(parents=True, exist_ok=True)
