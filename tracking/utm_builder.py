"""Gera e valida links com UTM segundo tracking/taxonomia_utm.md.

    python tracking/utm_builder.py gerar https://aurum.example.com.br/conta-digital meta paid_social br_social_conta-digital_prospecting
    python tracking/utm_builder.py validar "https://...?utm_source=Facebook&utm_medium=Paid-Social"
    python tracking/utm_builder.py lote campanhas.csv        # coluna 'url'
"""
from __future__ import annotations

import csv
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

PERMITIDOS = {
    "google": {"cpc"},
    "meta": {"paid_social"},
    "tiktok": {"paid_social"},
    "afiliados": {"affiliate"},
    "influenciador": {"influencer"},
    "crm": {"email"},
}
TIPOS = {"search", "social", "affiliate", "influencer", "crm", "video"}
PRODUTOS = {"conta-digital", "investimentos", "cartao", "cdb"}
RE_CAMPANHA = re.compile(r"^br_([a-z]+)_([a-z0-9-]+)_([a-z0-9-]+)$")
RE_SLUG = re.compile(r"^[a-z0-9-]+$")


def validar_utm(source: str | None, medium: str | None, campaign: str | None,
                content: str | None = None, term: str | None = None) -> list[str]:
    erros = []
    for nome, v in (("utm_source", source), ("utm_medium", medium), ("utm_campaign", campaign)):
        if not v:
            erros.append(f"{nome} ausente")
        elif v != v.strip().lower():
            erros.append(f"{nome}='{v}' tem maiúscula ou espaço")
    if source and source not in PERMITIDOS:
        erros.append(f"utm_source='{source}' fora da taxonomia ({', '.join(sorted(PERMITIDOS))})")
    elif source and medium and medium not in PERMITIDOS[source]:
        erros.append(f"utm_medium='{medium}' não combina com source '{source}' (use {', '.join(PERMITIDOS[source])})")
    if campaign:
        m = RE_CAMPANHA.match(campaign)
        if not m:
            erros.append(f"utm_campaign='{campaign}' fora do padrão br_{{tipo}}_{{produto}}_{{objetivo}}")
        else:
            if m.group(1) not in TIPOS:
                erros.append(f"tipo '{m.group(1)}' inválido ({', '.join(sorted(TIPOS))})")
            if m.group(2) not in PRODUTOS:
                erros.append(f"produto '{m.group(2)}' inválido ({', '.join(sorted(PRODUTOS))})")
    for nome, v in (("utm_content", content), ("utm_term", term)):
        if v and not RE_SLUG.match(v):
            erros.append(f"{nome}='{v}' deve ser minúsculo, sem acento/espaço (use '-')")
    return erros


def validar_url(url: str) -> list[str]:
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    if "gclid" in q and "utm_campaign" not in q:
        return ["só gclid: adicione as UTMs manuais (o QA do GA4 sinaliza)"]
    return validar_utm(q.get("utm_source"), q.get("utm_medium"), q.get("utm_campaign"),
                       q.get("utm_content"), q.get("utm_term"))


def gerar(url: str, source: str, medium: str, campaign: str, content: str | None = None,
          term: str | None = None) -> str:
    erros = validar_utm(source, medium, campaign, content, term)
    if erros:
        raise ValueError("; ".join(erros))
    p = urlparse(url)
    q = parse_qs(p.query)
    q.update({"utm_source": [source], "utm_medium": [medium], "utm_campaign": [campaign]})
    if content:
        q["utm_content"] = [content]
    if term:
        q["utm_term"] = [term]
    return urlunparse(p._replace(query=urlencode({k: v[0] for k, v in q.items()})))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[0]
    if cmd == "gerar":
        print(gerar(*argv[1:]))
    elif cmd == "validar":
        erros = validar_url(argv[1])
        print("✅ ok" if not erros else "\n".join(f"❌ {e}" for e in erros))
        return int(bool(erros))
    elif cmd == "lote":
        ruins = 0
        with open(argv[1], encoding="utf-8") as f:
            for linha in csv.DictReader(f):
                erros = validar_url(linha["url"])
                ruins += bool(erros)
                print(("✅ " if not erros else "❌ ") + linha["url"] + ("" if not erros else "\n   " + "; ".join(erros)))
        return int(bool(ruins))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
