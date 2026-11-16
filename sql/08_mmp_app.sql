-- App: instalações e eventos in-app no formato AppsFlyer (raw data export) e reconciliação
-- com o backend. O MMP é a fonte de verdade de atribuição para app; o GA4 web não enxerga install.
CREATE OR REPLACE TABLE app_por_midia AS
WITH reg AS (
    SELECT media_source,
           count(*) FILTER (WHERE event_name = 'af_complete_registration') AS cadastros,
           count(*) FILTER (WHERE event_name = 'af_first_deposit')         AS primeiros_depositos,
           sum(event_revenue) FILTER (WHERE event_name = 'af_first_deposit') AS receita_deposito
    FROM in_app_events GROUP BY media_source
)
SELECT
    i.media_source,
    count(*)                                                     AS installs,
    count(*) FILTER (WHERE i.platform = 'android')               AS installs_android,
    count(*) FILTER (WHERE i.platform = 'ios')                   AS installs_ios,
    coalesce(r.cadastros, 0)                                     AS cadastros,
    coalesce(r.primeiros_depositos, 0)                           AS primeiros_depositos,
    coalesce(r.cadastros, 0) / count(*)                          AS install_para_cadastro,
    r.receita_deposito
FROM installs i
LEFT JOIN reg r USING (media_source)
GROUP BY i.media_source, r.cadastros, r.primeiros_depositos, r.receita_deposito
ORDER BY installs DESC;

-- Reconciliação MMP x backend: todo cadastro no app deveria existir no core bancário
CREATE OR REPLACE TABLE reconciliacao_mmp AS
SELECT
    (SELECT count(*) FROM in_app_events WHERE event_name = 'af_complete_registration')   AS cadastros_mmp,
    (SELECT count(*) FROM backend WHERE origem = 'app')                                   AS contas_backend_app,
    (SELECT count(*) FROM in_app_events e
       WHERE e.event_name = 'af_complete_registration'
         AND NOT EXISTS (SELECT 1 FROM backend b WHERE b.customer_id = e.customer_user_id)) AS cadastros_sem_conta,
    (SELECT count(*) FROM installs WHERE customer_user_id IS NULL)                        AS installs_sem_cadastro;
