"""Gera dados sintéticos realistas no MESMO schema do export do GA4 para o BigQuery,
mais dados de MMP (formato AppsFlyer raw data) e custo de mídia.

Por que sintético? Dados de funil de um banco são confidenciais. O gerador reproduz as
dinâmicas que importam para a análise (qualidade por canal, mobile x desktop, jornadas com
várias sessões, teste A/B com efeito real conhecido) e também os PROBLEMAS de tracking que
um analista de Web Analytics precisa achar: UTMs fora do padrão, conversões duplicadas
(client + server), eventos sem sessão e cross-device.

    python -m funnel.simulate
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .config import (CANAIS, CPA_AFILIADO, DIAS, DOMINIO, FEE_INFLUENCER_SEMANA, GA4, INICIO,
                     LIFT_REAL_V2, MIDIA, MMP, SAMPLE, SEED, TAXA_APROVACAO_KYC,
                     TAXA_PRIMEIRO_DEPOSITO, USUARIOS)

log = logging.getLogger(__name__)
rng = np.random.default_rng(SEED)

REGIOES = [("São Paulo", "São Paulo", 0.32), ("Rio de Janeiro", "Rio de Janeiro", 0.12),
           ("Minas Gerais", "Belo Horizonte", 0.10), ("Paraná", "Curitiba", 0.07),
           ("Rio Grande do Sul", "Porto Alegre", 0.07), ("Bahia", "Salvador", 0.06),
           ("Distrito Federal", "Brasília", 0.06), ("Pernambuco", "Recife", 0.05),
           ("Santa Catarina", "Florianópolis", 0.05), ("Ceará", "Fortaleza", 0.05), ("Goiás", "Goiânia", 0.05)]
HORA_PESO = np.array([1, .5, .3, .2, .2, .4, 1, 2, 3, 3.5, 3.5, 3.5, 4, 3.5, 3.5, 3.5, 3.5, 4, 4.5, 5, 5.5, 5, 4, 2.5])
HORA_PESO = HORA_PESO / HORA_PESO.sum()
PAGINAS = {"home": ("/", "Banco Aurum | Conta digital e investimentos"),
           "conta": ("/conta-digital", "Conta digital gratuita | Banco Aurum"),
           "invest": ("/investimentos", "Investimentos | Banco Aurum"),
           "cdb": ("/investimentos/cdb", "CDB que rende mais que a poupança | Banco Aurum"),
           "abrir": ("/abrir-conta", "Abra sua conta | Banco Aurum")}


def _param(key: str, v) -> dict:
    if isinstance(v, (bool, np.bool_)):
        v = int(v)
    if isinstance(v, (int, np.integer)):
        return {"key": key, "value": {"string_value": None, "int_value": int(v), "double_value": None}}
    if isinstance(v, (float, np.floating)):
        return {"key": key, "value": {"string_value": None, "int_value": None, "double_value": float(v)}}
    return {"key": key, "value": {"string_value": str(v), "int_value": None, "double_value": None}}


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


class Gerador:
    def __init__(self):
        self.eventos: list[dict] = []
        self.installs: list[dict] = []
        self.inapp: list[dict] = []
        self.backend: list[dict] = []
        self.inicio = datetime.fromisoformat(INICIO)
        pesos = np.array([c.peso for c in CANAIS])
        self.p_canal = pesos / pesos.sum()

    # ------------------------------------------------------------------ helpers
    def _utm_url(self, pagina: str, canal, campanha: str, gclid: str | None) -> str:
        path = PAGINAS[pagina][0]
        if canal.medium in ("organic", "(none)", "referral"):
            return f"{DOMINIO}{path}"
        src, med = canal.source, canal.medium
        # 4% dos links de redes sociais saem com UTM fora da taxonomia (erro humano comum)
        if canal.medium == "paid_social" and rng.random() < 0.04:
            src, med = [("Facebook", "Paid-Social"), ("ig", "social"), ("meta", "cpc ")][rng.integers(0, 3)]
        q = f"utm_source={src}&utm_medium={med}&utm_campaign={campanha}"
        if canal.source == "google" and canal.medium == "cpc":
            q = (f"gclid={gclid}&" + q) if rng.random() > 0.03 else f"gclid={gclid}"  # 3%: só auto-tagging
        return f"{DOMINIO}{path}?{q}"

    def _evento(self, ts: datetime, nome: str, u: dict, s: dict, extra: dict | None = None, server=False):
        params = [] if server and rng.random() < 0.02 else [_param("ga_session_id", s["id"]),
                                                             _param("ga_session_number", s["numero"])]
        params += [_param("page_location", s["url"]), _param("page_title", s["titulo"]),
                   _param("engagement_time_msec", int(rng.integers(800, 25000)))]
        if s.get("engajada"):
            params.append(_param("session_engaged", "1"))
        if u.get("variante"):
            params.append(_param("experiment_onboarding", u["variante"]))
        for k, v in (extra or {}).items():
            params.append(_param(k, v))
        c = s["canal"]
        self.eventos.append({
            "event_date": ts.strftime("%Y%m%d"),
            "event_timestamp": int(ts.timestamp() * 1e6),
            "event_name": nome,
            "event_params": params,
            "user_pseudo_id": s["dispositivo_id"],
            "user_id": u.get("customer_id") if u.get("logado") else None,
            "device": {"category": s["device"], "operating_system": s["os"],
                       "web_info": {"browser": s["browser"]}},
            "geo": {"country": "Brazil", "region": u["regiao"], "city": u["cidade"]},
            "traffic_source": {"source": u["first_source"], "medium": u["first_medium"], "name": u["first_campaign"]},
            "collected_traffic_source": {
                "manual_source": s["utm_source"], "manual_medium": s["utm_medium"],
                "manual_campaign_name": s["utm_campaign"], "gclid": s["gclid"]},
            "platform": "WEB",
        })

    # ------------------------------------------------------------------ jornada
    def usuario(self, i: int):
        reg = REGIOES[rng.choice(len(REGIOES), p=[r[2] for r in REGIOES])]
        dia0 = rng.integers(0, DIAS)
        canal0 = CANAIS[rng.choice(len(CANAIS), p=self.p_canal)]
        camp0 = str(rng.choice(canal0.campanhas))
        mobile = rng.random() < canal0.pct_mobile
        u = {"idx": i, "regiao": reg[0], "cidade": reg[1], "customer_id": f"C{100000 + i}",
             "variante": None, "convertido": False, "logado": False,
             "first_source": canal0.source, "first_medium": canal0.medium, "first_campaign": camp0,
             "afinidade": rng.lognormal(0, 0.55), "mobile": mobile,
             "dispositivos": [f"{rng.integers(1e9, 9e9)}.{rng.integers(1e9, 9e9)}"]}
        n_sessoes = min(1 + rng.geometric(0.55), 8)
        dia = dia0
        for k in range(n_sessoes):
            if dia >= DIAS:
                break
            if k == 0:
                canal, camp = canal0, camp0
            else:
                r = rng.random()
                if r < 0.38:
                    canal = next(c for c in CANAIS if c.medium == "(none)")
                elif r < 0.60:
                    canal = canal0
                elif r < 0.78:
                    canal = CANAIS[1]  # remarketing Meta
                elif r < 0.88:
                    canal = next(c for c in CANAIS if c.medium == "email")
                else:
                    canal = next(c for c in CANAIS if c.medium == "organic")
                camp = ("br_social_investimentos_remarketing" if canal is CANAIS[1] and k > 0
                        else str(rng.choice(canal.campanhas)))
            # 12% das sessões de retorno acontecem em outro dispositivo (cross-device)
            if k > 0 and rng.random() < 0.12:
                u["dispositivos"].append(f"{rng.integers(1e9, 9e9)}.{rng.integers(1e9, 9e9)}")
                mobile_s = not u["mobile"]
            else:
                mobile_s = u["mobile"]
            self.sessao(u, k + 1, dia, canal, camp, mobile_s)
            if u["convertido"] and rng.random() < 0.7:
                break
            dia += int(rng.integers(0, 6))

    def sessao(self, u, numero, dia, canal, camp, mobile):
        ts = self.inicio + timedelta(days=int(dia), hours=int(rng.choice(24, p=HORA_PESO)),
                                     minutes=int(rng.integers(0, 60)), seconds=int(rng.integers(0, 60)))
        device = "mobile" if mobile else "desktop"
        os_ = str(rng.choice(["Android", "iOS"], p=[0.72, 0.28]) if mobile else rng.choice(["Windows", "Macintosh"], p=[0.8, 0.2]))
        pagina = {"cpc": "conta", "paid_social": str(rng.choice(["conta", "cdb"])), "email": "invest",
                  "affiliate": "abrir", "influencer": "conta"}.get(canal.medium, str(rng.choice(["home", "conta", "invest"])))
        gclid = f"Cj0KCQ{_hash(str(rng.random()))}" if (canal.source == "google" and canal.medium == "cpc") else None
        url = self._utm_url(pagina, canal, camp, gclid)
        q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&")) if "?" in url else {}
        s = {"id": int(ts.timestamp()), "numero": numero, "url": url, "titulo": PAGINAS[pagina][1],
             "canal": canal, "device": device, "os": os_, "dispositivo_id": u["dispositivos"][-1],
             "browser": "Chrome" if os_ != "iOS" else "Safari",
             "utm_source": q.get("utm_source"), "utm_medium": q.get("utm_medium"),
             "utm_campaign": q.get("utm_campaign"), "gclid": gclid}

        def t(seg):
            nonlocal ts
            ts += timedelta(seconds=float(seg))
            return ts

        self._evento(ts, "session_start", u, s)
        self._evento(ts, "page_view", u, s)
        if numero == 1:
            self._evento(ts, "first_visit", u, s)

        # probabilidade base de cada etapa, ajustada por canal, dispositivo, recorrência e afinidade
        q_mult = canal.intencao * u["afinidade"] * (1.25 if numero > 1 else 1.0)
        dev_mult = 0.82 if mobile else 1.0
        if rng.random() > min(0.62 * q_mult ** 0.5, 0.95):          # bounce
            return
        s["engajada"] = True
        self._evento(t(rng.exponential(12)), "scroll", u, s, {"percent_scrolled": 90})
        if rng.random() < 0.25:
            self._evento(t(rng.exponential(20)), "view_promotion", u, s,
                         {"promotion_name": "cdb_120_cdi", "creative_slot": "hero"})
        if u["convertido"]:
            if rng.random() < 0.5:
                self._evento(t(5), "login", u, s, {"method": "cpf"})
            return

        # CTA "Abrir minha conta"
        if mobile and rng.random() < 0.06:
            self._evento(t(rng.exponential(15)), "app_download_click", u, s,
                         {"cta_location": "banner_app", "store": "play_store" if s["os"] == "Android" else "app_store"})
            self.install_app(u, s, ts)
        if rng.random() > min(0.034 * q_mult, 0.5):
            return
        self._evento(t(rng.exponential(25)), "cta_click", u, s, {"cta_location": str(rng.choice(["hero", "header", "footer"])),
                                                                  "cta_text": "Abrir minha conta"})
        if u["variante"] is None:
            u["variante"] = str(rng.choice(["v1_3_etapas", "v2_2_etapas"]))
        s["url"], s["titulo"] = f"{DOMINIO}/abrir-conta", PAGINAS["abrir"][1]
        self._evento(t(2), "page_view", u, s)
        self._evento(t(rng.exponential(8)), "begin_onboarding", u, s, {"form_variant": u["variante"]})

        etapas = 3 if u["variante"] == "v1_3_etapas" else 2
        # probabilidade TOTAL de concluir o formulário; v2 tem lift real conhecido
        p_total = min(0.44 * dev_mult * q_mult ** 0.35, 0.92)
        if u["variante"] == "v2_2_etapas":
            p_total = min(p_total * (1 + LIFT_REAL_V2), 0.95)
        p_etapa = p_total ** (1 / etapas)
        for e in range(1, etapas + 1):
            if rng.random() > p_etapa:
                if rng.random() < 0.6:
                    self._evento(t(rng.exponential(30)), "form_error", u, s,
                                 {"step_number": e, "error_field": str(rng.choice(["cpf", "celular", "renda", "selfie"]))})
                return
            self._evento(t(rng.exponential(40)), "onboarding_step_complete", u, s,
                         {"step_number": e, "step_name": ["dados_pessoais", "endereco_renda", "documentos"][e - 1]
                          if etapas == 3 else ["dados_pessoais", "documentos"][e - 1]})

        u["convertido"], u["logado"] = True, True
        self._evento(t(5), "sign_up", u, s, {"method": "onboarding_web", "account_type": "conta_digital"})
        self.backend_conta(u, ts, canal_web=True)

    # ------------------------------------------------------------------ servidor e app
    def backend_conta(self, u, ts, canal_web: bool, s=None):
        aprovado = rng.random() < TAXA_APROVACAO_KYC
        reg = {"customer_id": u["customer_id"], "created_at": ts, "origem": "web" if canal_web else "app",
               "kyc_aprovado": aprovado, "first_deposit_at": None, "first_deposit_value": None}
        if aprovado and rng.random() < TAXA_PRIMEIRO_DEPOSITO * min(u["afinidade"], 1.6) ** 0.5:
            dep_ts = ts + timedelta(hours=float(rng.exponential(60)))
            valor = round(float(rng.lognormal(7.4, 1.1) * (1.6 if u["first_medium"] in ("cpc", "email") else 1.0)), 2)
            reg.update(first_deposit_at=dep_ts, first_deposit_value=valor)
            if canal_web and dep_ts < self.inicio + timedelta(days=DIAS):
                # conversão server-side (Measurement Protocol / sGTM) com transaction_id para dedupe
                sess = {"id": None, "numero": None, "url": f"{DOMINIO}/app/deposito", "titulo": "Depósito",
                        "canal": CANAIS[7], "device": "server", "os": None, "browser": None,
                        "dispositivo_id": u["dispositivos"][0], "utm_source": None, "utm_medium": None,
                        "utm_campaign": None, "gclid": None}
                tid = f"DEP-{u['customer_id']}"
                extra = {"transaction_id": tid, "value": valor, "currency": "BRL", "event_source": "server"}
                self._evento(dep_ts, "first_deposit", u, sess, extra, server=True)
                # 1,5%: tag web também disparou (duplicidade client + server)
                if rng.random() < 0.015:
                    self._evento(dep_ts + timedelta(seconds=3), "first_deposit", u, sess,
                                 {**extra, "event_source": "web"}, server=True)
        self.backend.append(reg)

    def install_app(self, u, s, ts):
        if rng.random() > 0.45:
            return
        midia = {"cpc": "googleadwords_int", "paid_social": "Facebook Ads" if s["canal"].source == "meta" else "tiktokglobal_int",
                 "affiliate": "afiliados_int", "influencer": "influencer_int"}.get(s["canal"].medium, "organic")
        inst_ts = ts + timedelta(minutes=float(rng.exponential(10)))
        afid = f"{int(inst_ts.timestamp())}-{rng.integers(1e6, 9e6)}"
        self.installs.append({"install_time": inst_ts, "appsflyer_id": afid, "media_source": midia,
                              "campaign": s["utm_campaign"] if midia != "organic" else None,
                              "platform": "android" if s["os"] == "Android" else "ios",
                              "attributed_touch_type": "click" if midia != "organic" else None,
                              "customer_user_id": None})
        if not u["convertido"] and rng.random() < 0.25 * u["afinidade"] ** 0.5:
            u["convertido"] = True
            reg_ts = inst_ts + timedelta(minutes=float(rng.exponential(20)))
            self.installs[-1]["customer_user_id"] = u["customer_id"]
            self.inapp.append({"event_time": reg_ts, "appsflyer_id": afid, "event_name": "af_complete_registration",
                               "event_revenue": None, "media_source": midia, "customer_user_id": u["customer_id"]})
            self.backend_conta(u, reg_ts, canal_web=False)
            b = self.backend[-1]
            if b["first_deposit_at"] is not None:
                self.inapp.append({"event_time": b["first_deposit_at"], "appsflyer_id": afid,
                                   "event_name": "af_first_deposit", "event_revenue": b["first_deposit_value"],
                                   "media_source": midia, "customer_user_id": u["customer_id"]})


def midia_diaria(eventos: pd.DataFrame) -> pd.DataFrame:
    """Custo diário por campanha a partir dos cliques pagos simulados (com CTR/CPM plausíveis)."""
    ss = eventos[eventos["event_name"] == "session_start"]
    cliques = ss.groupby(["event_date", "src", "med", "camp"]).size().rename("cliques").reset_index()
    linhas = []
    for _, r in cliques.iterrows():
        canal = next((c for c in CANAIS if c.source == r["src"] and c.medium == r["med"]), None)
        if canal is None or canal.cpc is None:
            continue
        cl = int(r["cliques"] * rng.uniform(1.15, 1.35))   # cliques > sessões (perda de tracking/consentimento)
        cpc = canal.cpc * (0.55 if "brand" in r["camp"] else 1.0) * rng.uniform(0.85, 1.15)
        ctr = {"cpc": 0.045, "paid_social": 0.011}[canal.medium] * rng.uniform(0.8, 1.2)
        linhas.append({"data": r["event_date"], "plataforma": {"google": "Google Ads", "meta": "Meta Ads",
                                                               "tiktok": "TikTok Ads"}[canal.source],
                       "source": canal.source, "medium": canal.medium, "campanha": r["camp"],
                       "impressoes": int(cl / ctr), "cliques": cl, "custo": round(cl * cpc, 2)})
    return pd.DataFrame(linhas)


def rodar():
    g = Gerador()
    for i in range(USUARIOS):
        g.usuario(i)
        if i % 20000 == 0:
            log.info("usuário %s/%s · %s eventos", i, USUARIOS, f"{len(g.eventos):,}")

    ev = pd.DataFrame(g.eventos).sort_values("event_timestamp")
    ev = ev[ev["event_date"] < (datetime.fromisoformat(INICIO) + timedelta(days=DIAS)).strftime("%Y%m%d")]
    tabela = pa.Table.from_pandas(ev, preserve_index=False)
    for d in sorted(ev["event_date"].unique()):
        pq.write_table(tabela.filter(pa.compute.equal(tabela["event_date"], d)), GA4 / f"events_{d}.parquet",
                       compression="zstd")
    for d in sorted(ev["event_date"].unique())[:3]:
        pq.write_table(tabela.filter(pa.compute.equal(tabela["event_date"], d)), SAMPLE / f"events_{d}.parquet",
                       compression="zstd")

    aux = ev.assign(src=ev["collected_traffic_source"].map(lambda x: x["manual_source"]),
                    med=ev["collected_traffic_source"].map(lambda x: x["manual_medium"]),
                    camp=ev["collected_traffic_source"].map(lambda x: x["manual_campaign_name"]))
    aux.loc[aux["collected_traffic_source"].map(lambda x: x["gclid"] is not None), ["src", "med"]] = ["google", "cpc"]
    gc = aux["src"].eq("google") & aux["med"].eq("cpc") & aux["camp"].isna()
    aux.loc[gc, "camp"] = "br_search_conta-digital_generic"
    midia = midia_diaria(aux)

    # custos fora de leilão: afiliados por CPA, influenciadores por fee semanal
    bk = pd.DataFrame(g.backend)
    dias = pd.date_range(INICIO, periods=DIAS, freq="D")
    semanas = [d for d in dias if d.weekday() == 0]
    extra = [{"data": d.strftime("%Y%m%d"), "plataforma": "Influenciadores", "source": "influenciador",
              "medium": "influencer", "campanha": "br_influencer_financas-pessoais", "impressoes": int(rng.integers(3e5, 6e5)),
              "cliques": 0, "custo": FEE_INFLUENCER_SEMANA} for d in semanas]
    midia = pd.concat([midia, pd.DataFrame(extra)], ignore_index=True)
    midia.to_parquet(MIDIA / "custo_midia_diario.parquet", index=False)

    bk.to_parquet(MIDIA.parent / "backend_contas.parquet", index=False)
    pd.DataFrame(g.installs).to_parquet(MMP / "installs.parquet", index=False)
    pd.DataFrame(g.inapp).to_parquet(MMP / "in_app_events.parquet", index=False)
    log.info("eventos GA4: %s | contas backend: %s | installs: %s | linhas de mídia: %s | CPA afiliado R$ %.0f",
             f"{len(ev):,}", f"{len(bk):,}", f"{len(g.installs):,}", f"{len(midia):,}", CPA_AFILIADO)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
    rodar()
