-- Eficiência de mídia por canal: CAC, custo por conta ativada e retorno estimado.
-- Atribuição: last non-direct click (padrão de mercado para comparar com as plataformas).
CREATE OR REPLACE TABLE eficiencia_canal AS
WITH conv AS (
    SELECT
        a.canal,
        count(*)                                                    AS contas,
        sum(CASE WHEN b.kyc_aprovado THEN 1 ELSE 0 END)             AS aprovadas,
        sum(CASE WHEN b.first_deposit_at IS NOT NULL THEN 1 ELSE 0 END) AS ativadas,
        sum(coalesce(b.first_deposit_value, 0))                     AS deposito_total
    FROM (
        SELECT j.user_pseudo_id,
               coalesce(arg_max(j.canal, j.posicao) FILTER (WHERE j.canal <> 'Direct'), 'Direct') AS canal,
               max(s.user_id) AS user_id
        FROM jornadas j JOIN sessoes s USING (session_key)
        GROUP BY j.user_pseudo_id
    ) a
    LEFT JOIN backend b ON b.customer_id = a.user_id
    GROUP BY a.canal
),
custo AS (
    SELECT
        CASE medium WHEN 'cpc' THEN 'Paid Search' WHEN 'paid_social' THEN 'Paid Social'
                    WHEN 'influencer' THEN 'Influenciadores' END     AS canal,
        sum(custo) AS custo, sum(cliques) AS cliques, sum(impressoes) AS impressoes
    FROM midia
    GROUP BY 1
),
sessoes_canal AS (
    SELECT canal, count(*) AS sessoes FROM sessoes GROUP BY canal
)
SELECT
    c.canal,
    s.sessoes,
    c.contas,
    c.aprovadas,
    c.ativadas,
    c.deposito_total,
    -- afiliados são pagos por conta aberta (CPA); os demais pelo custo de mídia
    CASE WHEN c.canal = 'Afiliados' THEN c.contas * (SELECT cpa_afiliado FROM params)
         ELSE coalesce(m.custo, 0) END                                        AS custo,
    m.cliques,
    c.contas / s.sessoes                                                      AS conv_sessao_conta,
    c.ativadas / nullif(c.contas, 0)                                          AS taxa_ativacao,
    (CASE WHEN c.canal = 'Afiliados' THEN c.contas * (SELECT cpa_afiliado FROM params)
          ELSE coalesce(m.custo, 0) END) / nullif(c.contas, 0)                AS cac,
    (CASE WHEN c.canal = 'Afiliados' THEN c.contas * (SELECT cpa_afiliado FROM params)
          ELSE coalesce(m.custo, 0) END) / nullif(c.ativadas, 0)              AS custo_por_ativacao,
    c.deposito_total * (SELECT margem FROM params)                            AS receita_anual_estimada,
    c.deposito_total * (SELECT margem FROM params)
        / nullif(CASE WHEN c.canal = 'Afiliados' THEN c.contas * (SELECT cpa_afiliado FROM params)
                      ELSE m.custo END, 0)                                    AS roas_12m
FROM conv c
LEFT JOIN custo m USING (canal)
LEFT JOIN sessoes_canal s USING (canal)
ORDER BY c.contas DESC;

-- Desempenho por campanha (paid): o que um analista olha toda segunda-feira
CREATE OR REPLACE TABLE eficiencia_campanha AS
WITH s AS (
    SELECT campanha, canal, count(*) AS sessoes, sum(sign_up) AS cadastros,
           sum(begin_onboarding) AS inicios
    FROM sessoes WHERE canal IN ('Paid Search', 'Paid Social')
    GROUP BY ALL
),
m AS (
    SELECT campanha, sum(custo) AS custo, sum(cliques) AS cliques, sum(impressoes) AS impressoes
    FROM midia GROUP BY campanha
)
SELECT s.*, m.custo, m.cliques, m.impressoes,
       m.cliques / nullif(m.impressoes, 0)       AS ctr,
       m.custo / nullif(m.cliques, 0)            AS cpc,
       s.sessoes / nullif(m.cliques, 0)          AS taxa_chegada,   -- cliques que viram sessão medida
       m.custo / nullif(s.cadastros, 0)          AS custo_por_cadastro
FROM s LEFT JOIN m USING (campanha)
ORDER BY custo DESC NULLS LAST;
