# Plano de tracking: onboarding de conta digital

> Documento vivo que define **o que** medir, **onde** dispara, **com quais parâmetros** e **para qual pergunta de negócio**. É o contrato entre produto, desenvolvimento, mídia e dados.

## Objetivos de negócio → KPIs

| Objetivo | KPI | Evento-fonte |
|---|---|---|
| Aumentar contas abertas | Cadastros / sessões | `sign_up` |
| Reduzir abandono no formulário | Conclusão do onboarding = `sign_up` / `begin_onboarding` | `begin_onboarding`, `onboarding_step_complete`, `form_error` |
| Trazer clientes que usam a conta | Taxa de ativação = 1º depósito / contas | `first_deposit` (server-side) |
| Comprar mídia com eficiência | CAC, custo por ativação, ROAS 12m | conversões + custo de mídia |
| Crescer no app | Installs, cadastros no app | MMP (AppsFlyer) |

## Eventos

Convenções: `snake_case`, nomes de evento recomendados do GA4 sempre que existirem (`sign_up`, `login`, `view_promotion`), no máximo 25 parâmetros por evento e **nunca PII** (CPF, nome, e-mail, telefone ou valor digitado em campo).

| Evento | Quando dispara | Parâmetros | Tipo | Conversão? |
|---|---|---|---|---|
| `page_view` | Carregamento e troca de rota (SPA) | `page_location`, `page_title` | automático GA4 | – |
| `consent_update` | Usuário escolhe no banner LGPD | `consent_choice` (`todos` \| `essenciais`) | dataLayer | – |
| `view_promotion` | Selo de promoção ≥ 60% visível | `promotion_name`, `creative_slot` | dataLayer | – |
| `scroll_depth` | 50% e 90% da página | `percent_scrolled` | dataLayer | – |
| `cta_click` | Clique em "Abrir minha conta" | `cta_location` (`hero` \| `header` \| `footer`), `cta_text` | dataLayer | – |
| `begin_onboarding` | 1ª abertura do formulário na sessão | `form_variant`, `experiment_onboarding` | dataLayer | micro |
| `onboarding_step_complete` | Cada etapa validada | `step_number`, `step_name`, `form_variant` | dataLayer | – |
| `form_error` | Validação falha | `step_number`, `error_field` (nome do campo, nunca o valor), `form_variant` | dataLayer | – |
| `sign_up` | Cadastro enviado com sucesso | `method`, `account_type`, `form_variant`, `user_id` (hash do servidor) | dataLayer | **sim** |
| `app_download_click` | Clique nos botões das lojas | `cta_location`, `store` | dataLayer | – |
| `login` | Cliente existente entra | `method` | dataLayer | – |
| `first_deposit` | Core bancário confirma o 1º depósito | `transaction_id`, `value`, `currency`, `event_source=server` | **server-side** (sGTM / Measurement Protocol) | **sim** |

### Por que `first_deposit` é server-side?
O depósito acontece horas ou dias depois do cadastro, muitas vezes no app, e não depende de o usuário estar no site. Disparar do servidor garante que 100% das conversões cheguem, sem bloqueador nem cookie expirado, e permite enviar a mesma conversão para Google Ads e Meta (CAPI) com **`transaction_id` para deduplicação**.

## Dimensões personalizadas (GA4 → Admin → Definições personalizadas)

| Nome | Escopo | Parâmetro |
|---|---|---|
| Variante do onboarding | Evento | `form_variant` |
| Experimento onboarding | Usuário | `experiment_onboarding` |
| Local do CTA | Evento | `cta_location` |
| Etapa do formulário | Evento | `step_number` |
| Campo com erro | Evento | `error_field` |
| Origem do evento | Evento | `event_source` |

## Consentimento (LGPD + Consent Mode v2)

1. `gtag('consent','default', {...denied})` **antes** do GTM carregar.
2. Banner com "Aceitar todos" e "Só essenciais", atualizado via `gtag('consent','update', ...)`.
3. Sem consentimento, o GA4 envia pings sem cookie (modelagem de conversões). Por isso existe o teste de QA "cliques pagos sem sessão medida".

## QA antes de publicar

- [ ] GTM Preview: cada evento aparece uma vez, com os parâmetros da tabela.
- [ ] GA4 DebugView: parâmetros chegam tipados (número como número).
- [ ] Nenhum parâmetro contém CPF, e-mail ou telefone (regex no QA SQL).
- [ ] `sign_up` não dispara em refresh da página de sucesso.
- [ ] `first_deposit` com `transaction_id` único (teste `07_qualidade_tracking.sql`).
- [ ] UTMs das campanhas novas validadas com `tracking/utm_builder.py`.
