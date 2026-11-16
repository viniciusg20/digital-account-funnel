import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tracking"))

from funnel import ab_test, markov  # noqa: E402
from utm_builder import gerar, validar_url  # noqa: E402


# ------------------------------------------------------------------ UTM
def test_utm_valida_link_correto():
    url = "https://x.com/?utm_source=meta&utm_medium=paid_social&utm_campaign=br_social_conta-digital_prospecting"
    assert validar_url(url) == []


@pytest.mark.parametrize("url,trecho", [
    ("https://x.com/?utm_source=Facebook&utm_medium=Paid-Social&utm_campaign=br_social_conta-digital_prospecting", "maiúscula"),
    ("https://x.com/?utm_source=meta&utm_medium=cpc&utm_campaign=br_social_conta-digital_prospecting", "não combina"),
    ("https://x.com/?utm_source=google&utm_medium=cpc&utm_campaign=Campanha Black Friday", "padrão"),
    ("https://x.com/?gclid=abc", "só gclid"),
])
def test_utm_pega_erros(url, trecho):
    assert any(trecho in e for e in validar_url(url))


def test_utm_gerar_rejeita_fora_do_padrao():
    with pytest.raises(ValueError):
        gerar("https://x.com", "Meta", "paid_social", "br_social_conta-digital_prospecting")
    assert "utm_term=conta-gratis" in gerar("https://x.com/a", "google", "cpc", "br_search_conta-digital_brand",
                                            term="conta-gratis")


# ------------------------------------------------------------------ A/B
def test_srm_detecta_divisao_desbalanceada():
    assert ab_test.srm(5000, 5000)["srm_detectado"] is False
    assert ab_test.srm(5000, 4500)["srm_detectado"] is True


def test_teste_ab_detecta_efeito_grande_e_ignora_ruido():
    assert ab_test.frequentista(500, 1000, 600, 1000)["significativo"] is True
    assert ab_test.frequentista(500, 1000, 505, 1000)["significativo"] is False


def test_amostra_necessaria_cai_com_mde_maior():
    assert ab_test.amostra_necessaria(0.5, 0.05) > ab_test.amostra_necessaria(0.5, 0.10) > 0


def test_bayes_prob_proxima_de_meio_sem_diferenca():
    r = ab_test.bayesiano(500, 1000, 500, 1000)
    assert 0.4 < r["prob_b_melhor"] < 0.6


# ------------------------------------------------------------------ Markov
def test_markov_canal_indispensavel_leva_todo_credito():
    # todo mundo que converte passa por "Search"; "Social" nunca leva à conversão
    linhas = []
    for i in range(50):
        linhas += [(f"u{i}", 1, "Search", 1)]
    for i in range(50, 100):
        linhas += [(f"u{i}", 1, "Social", 0)]
    s = pd.DataFrame(linhas, columns=["user_pseudo_id", "inicio_sessao", "canal", "sign_up"])
    r = markov.atribuir(s).set_index("canal")
    assert r.loc["Search", "conversoes"] == pytest.approx(50)
    assert r.loc["Social", "conversoes"] == pytest.approx(0, abs=1e-9)


# ------------------------------------------------------------------ SQL de staging (schema GA4)
def _p(k, s=None, i=None):
    return {"key": k, "value": {"string_value": s, "int_value": i, "double_value": None}}


def test_staging_duckdb_achata_event_params():
    ev = pd.DataFrame([{
        "event_date": "20260801", "event_timestamp": 1785542400000000, "event_name": "sign_up",
        "event_params": [_p("ga_session_id", i=123), _p("page_location", s="https://a.com/abrir-conta?x=1"),
                         _p("step_number", i=2), _p("experiment_onboarding", s="v2_2_etapas")],
        "user_pseudo_id": "1.2", "user_id": "C1",
        "device": {"category": "mobile", "operating_system": "Android", "web_info": {"browser": "Chrome"}},
        "geo": {"country": "Brazil", "region": "São Paulo", "city": "São Paulo"},
        "traffic_source": {"source": "google", "medium": "organic", "name": "(organic)"},
        "collected_traffic_source": {"manual_source": "meta", "manual_medium": "paid_social",
                                     "manual_campaign_name": "br_social_x_y", "gclid": None},
        "platform": "WEB"}])
    con = duckdb.connect()
    con.register("events", ev)
    con.execute((ROOT / "sql" / "duckdb" / "01_stg_events.sql").read_text(encoding="utf-8"))
    r = con.execute("SELECT * FROM stg_events").df().iloc[0]
    assert r["ga_session_id"] == 123
    assert r["session_key"] == "1.2.123"
    assert r["page_path"] == "/abrir-conta"
    assert r["step_number"] == 2
    assert r["variante"] == "v2_2_etapas"
    assert r["utm_source_raw"] == "meta"
    assert r["first_medium"] == "organic"
