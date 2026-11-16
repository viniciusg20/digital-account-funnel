-- Sessões com origem normalizada e agrupamento de canais próprio.
-- Normalizar UTM (lower/trim + de-para) é governança: sem isso, "Facebook / Paid-Social"
-- e "meta / paid_social" viram dois canais diferentes no relatório.
CREATE OR REPLACE TABLE dim_de_para_utm AS
SELECT * FROM (VALUES
    ('facebook', 'meta'), ('fb', 'meta'), ('ig', 'meta'), ('instagram', 'meta'),
    ('paid-social', 'paid_social'), ('social', 'paid_social')
) AS t(valor_bruto, valor_padrao);

CREATE OR REPLACE TABLE sessoes AS
WITH base AS (
    SELECT
        session_key,
        user_pseudo_id,
        any_value(ga_session_number)                                          AS ga_session_number,
        min(event_ts)                                                         AS inicio_sessao,
        arg_min(page_path, event_ts)                                          AS landing_page,
        arg_min(device, event_ts)                                             AS device,
        arg_min(os, event_ts)                                                 AS os,
        arg_min(regiao, event_ts)                                             AS regiao,
        any_value(first_medium)                                               AS first_medium,
        max(user_id)                                                          AS user_id,
        max(utm_source_raw)                                                   AS utm_source_raw,
        max(utm_medium_raw)                                                   AS utm_medium_raw,
        max(utm_campaign)                                                     AS utm_campaign,
        max(gclid)                                                            AS gclid,
        max(variante)                                                         AS variante,
        max(CASE WHEN session_engaged = '1' THEN 1 ELSE 0 END)                AS engajada,
        max(CASE WHEN event_name = 'cta_click' THEN 1 ELSE 0 END)             AS cta_click,
        max(CASE WHEN event_name = 'begin_onboarding' THEN 1 ELSE 0 END)      AS begin_onboarding,
        max(CASE WHEN event_name = 'onboarding_step_complete' AND step_number = 1 THEN 1 ELSE 0 END) AS etapa_1,
        max(CASE WHEN event_name = 'form_error' THEN 1 ELSE 0 END)            AS teve_erro_form,
        max(CASE WHEN event_name = 'sign_up' THEN 1 ELSE 0 END)               AS sign_up,
        min(CASE WHEN event_name = 'sign_up' THEN event_ts END)               AS sign_up_ts,
        max(CASE WHEN event_name = 'app_download_click' THEN 1 ELSE 0 END)    AS app_click,
        count(*)                                                              AS eventos
    FROM stg_events
    WHERE ga_session_id IS NOT NULL
    GROUP BY session_key, user_pseudo_id
),
normalizada AS (
    SELECT
        b.*,
        CASE WHEN b.gclid IS NOT NULL THEN 'google'
             ELSE coalesce(ds.valor_padrao, lower(trim(b.utm_source_raw))) END AS source,
        CASE WHEN b.gclid IS NOT NULL THEN 'cpc'
             ELSE coalesce(dm.valor_padrao, lower(trim(b.utm_medium_raw))) END AS medium,
        coalesce(b.utm_campaign,
                 CASE WHEN b.gclid IS NOT NULL THEN '(auto-tagging sem utm)' END) AS campanha
    FROM base b
    LEFT JOIN dim_de_para_utm ds ON lower(trim(b.utm_source_raw)) = ds.valor_bruto
    LEFT JOIN dim_de_para_utm dm ON lower(trim(b.utm_medium_raw)) = dm.valor_bruto
)
SELECT
    *,
    CASE
        WHEN medium = 'cpc'                                  THEN 'Paid Search'
        WHEN medium = 'paid_social'                          THEN 'Paid Social'
        WHEN medium = 'affiliate'                            THEN 'Afiliados'
        WHEN medium = 'influencer'                           THEN 'Influenciadores'
        WHEN medium = 'email'                                THEN 'CRM / E-mail'
        -- sem UTM: no export real viria de page_referrer; aqui, do primeiro toque do usuário
        WHEN ga_session_number = 1 AND first_medium = 'organic'  THEN 'Organic Search'
        WHEN ga_session_number = 1 AND first_medium = 'referral' THEN 'Referral'
        ELSE 'Direct'
    END                                                      AS canal
FROM normalizada;
