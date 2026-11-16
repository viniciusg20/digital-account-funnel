-- Coortes semanais pela semana da 1ª visita: % que abriu conta e % que ativou (1º depósito)
-- em até N semanas. Mostra o "tempo de maturação" do lead, que importa para avaliar campanhas recentes.
CREATE OR REPLACE TABLE coortes AS
WITH usuarios AS (
    SELECT user_pseudo_id,
           date_trunc('week', min(inicio_sessao))::DATE                     AS semana_coorte,
           min(inicio_sessao)                                               AS primeira_visita,
           min(sign_up_ts)                                                  AS cadastro_ts,
           max(user_id)                                                     AS user_id
    FROM sessoes
    GROUP BY user_pseudo_id
),
u AS (
    SELECT us.*, b.first_deposit_at
    FROM usuarios us
    LEFT JOIN backend b ON b.customer_id = us.user_id
)
SELECT
    semana_coorte,
    count(*)                                                                         AS usuarios,
    avg(CASE WHEN cadastro_ts < primeira_visita + INTERVAL 7 DAY  THEN 1.0 ELSE 0 END)  AS conta_s0,
    avg(CASE WHEN cadastro_ts < primeira_visita + INTERVAL 14 DAY THEN 1.0 ELSE 0 END)  AS conta_s1,
    avg(CASE WHEN cadastro_ts < primeira_visita + INTERVAL 28 DAY THEN 1.0 ELSE 0 END)  AS conta_s3,
    avg(CASE WHEN first_deposit_at < primeira_visita + INTERVAL 7 DAY  THEN 1.0 ELSE 0 END) AS ativo_s0,
    avg(CASE WHEN first_deposit_at < primeira_visita + INTERVAL 14 DAY THEN 1.0 ELSE 0 END) AS ativo_s1,
    avg(CASE WHEN first_deposit_at < primeira_visita + INTERVAL 28 DAY THEN 1.0 ELSE 0 END) AS ativo_s3
FROM u
GROUP BY semana_coorte
ORDER BY semana_coorte;
