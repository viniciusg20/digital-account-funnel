# Taxonomia de UTMs

Padrão único para todas as campanhas. Link fora do padrão quebra o agrupamento de canais e o CAC por canal. O validador [`utm_builder.py`](utm_builder.py) gera e confere links antes de subirem para as plataformas.

## Regras gerais
- Tudo em **minúsculas**, sem acento, sem espaço. Separador de palavras `-`; separador de blocos `_`.
- `utm_source` e `utm_medium` só aceitam os valores das tabelas abaixo.
- No Google Ads use **auto-tagging (gclid)** + UTM manual (o QA sinaliza sessões só com gclid).

## `utm_source` × `utm_medium` permitidos

| Canal (relatório) | utm_source | utm_medium |
|---|---|---|
| Paid Search | `google` | `cpc` |
| Paid Social | `meta`, `tiktok` | `paid_social` |
| Afiliados | `afiliados` | `affiliate` |
| Influenciadores | `influenciador` | `influencer` |
| CRM / E-mail | `crm` | `email` |

## `utm_campaign`

```
{pais}_{tipo}_{produto}_{objetivo}
 br  _ search _ conta-digital _ brand
```

| Bloco | Valores |
|---|---|
| país | `br` |
| tipo | `search`, `social`, `affiliate`, `influencer`, `crm`, `video` |
| produto | `conta-digital`, `investimentos`, `cartao`, `cdb` |
| objetivo | `brand`, `generic`, `prospecting`, `remarketing`, `jovens`, `newsletter`, `cashback`, `financas-pessoais` |

## `utm_content` e `utm_term` (opcionais)
- `utm_content`: criativo/variação → `video-15s-cdb120`, `carrossel-pix`.
- `utm_term`: palavra-chave (Search) ou público (Social) → `conta-digital-gratuita`, `lal-1pct-clientes`.

## Exemplos

| ✅ certo | ❌ errado (achado no QA) |
|---|---|
| `utm_source=meta&utm_medium=paid_social&utm_campaign=br_social_conta-digital_prospecting` | `utm_source=Facebook&utm_medium=Paid-Social` |
| `utm_source=google&utm_medium=cpc&utm_campaign=br_search_conta-digital_brand` + gclid | só `gclid`, sem campanha |
