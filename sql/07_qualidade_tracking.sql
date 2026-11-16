-- QA de tracking: inconsistências que um analista de Web Analytics precisa achar ANTES
-- de alguém tomar decisão com o dado. Cada linha é um teste com severidade.
CREATE OR REPLACE TABLE qa_tracking AS
WITH taxonomia AS (
    SELECT * FROM (VALUES ('google'), ('meta'), ('tiktok'), ('afiliados'), ('influenciador'), ('crm'))
        AS t(source_permitido)
),
ss AS (SELECT * FROM stg_events WHERE event_name = 'session_start')
SELECT 'UTM source fora da taxonomia' AS teste, 'alta' AS severidade,
       count(*) FILTER (WHERE utm_source_raw IS NOT NULL
                        AND utm_source_raw NOT IN (SELECT source_permitido FROM taxonomia)) AS ocorrencias,
       count(*) FILTER (WHERE utm_source_raw IS NOT NULL)                                 AS base,
       string_agg(DISTINCT utm_source_raw, ', ') FILTER (
           WHERE utm_source_raw NOT IN (SELECT source_permitido FROM taxonomia))          AS exemplos
FROM ss
UNION ALL
SELECT 'UTM medium com maiúscula, espaço ou hífen', 'alta',
       count(*) FILTER (WHERE utm_medium_raw IS NOT NULL AND utm_medium_raw <> lower(trim(replace(utm_medium_raw, '-', '_')))),
       count(*) FILTER (WHERE utm_medium_raw IS NOT NULL),
       string_agg(DISTINCT '"' || utm_medium_raw || '"', ', ') FILTER (
           WHERE utm_medium_raw <> lower(trim(replace(utm_medium_raw, '-', '_'))))
FROM ss
UNION ALL
SELECT 'Sessão do Google Ads só com gclid (sem utm_campaign)', 'média',
       count(*) FILTER (WHERE gclid IS NOT NULL AND utm_campaign IS NULL),
       count(*) FILTER (WHERE gclid IS NOT NULL), NULL
FROM ss
UNION ALL
SELECT 'first_deposit duplicado (mesmo transaction_id)', 'crítica',
       coalesce(sum(n - 1), 0), (SELECT count(*) FROM stg_events WHERE event_name = 'first_deposit'),
       'client + server disparando a mesma conversão'
FROM (SELECT transaction_id, count(*) AS n FROM stg_events
      WHERE event_name = 'first_deposit' GROUP BY 1 HAVING count(*) > 1)
UNION ALL
SELECT 'Evento sem ga_session_id', 'média',
       count(*) FILTER (WHERE ga_session_id IS NULL), count(*),
       string_agg(DISTINCT event_name, ', ') FILTER (WHERE ga_session_id IS NULL)
FROM stg_events
UNION ALL
SELECT 'sign_up sem begin_onboarding na mesma sessão', 'alta',
       count(*) FILTER (WHERE sign_up = 1 AND begin_onboarding = 0),
       count(*) FILTER (WHERE sign_up = 1), NULL
FROM sessoes
UNION ALL
SELECT 'Cliques pagos sem sessão medida (consentimento/perda de tag)', 'média',
       (SELECT sum(cliques) FROM midia) - (SELECT count(*) FROM sessoes WHERE canal IN ('Paid Search', 'Paid Social')),
       (SELECT sum(cliques) FROM midia), 'esperado 10–30% com Consent Mode e bloqueadores'
UNION ALL
SELECT 'Usuários que trocaram de dispositivo (jornada quebrada)', 'informativa',
       (SELECT count(*) FROM (SELECT user_id FROM sessoes WHERE user_id IS NOT NULL
                              GROUP BY user_id HAVING count(DISTINCT user_pseudo_id) > 1)),
       (SELECT count(DISTINCT user_id) FROM sessoes WHERE user_id IS NOT NULL),
       'só detectável depois do login: motivo para enviar user_id'
;

CREATE OR REPLACE TABLE qa_tracking AS
SELECT *, ocorrencias::DOUBLE / nullif(base, 0) AS pct FROM qa_tracking;
