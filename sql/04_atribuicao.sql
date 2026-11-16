-- Atribuição multitoque baseada em regras.
-- Jornada = todas as sessões do usuário até a sessão do cadastro (inclusive).
-- Obs.: cross-device quebra a jornada (user_pseudo_id muda); o user_id só aparece
-- depois do cadastro. É uma limitação real do GA4 web que discutimos no README.
CREATE OR REPLACE TABLE jornadas AS
WITH conv AS (
    SELECT user_pseudo_id, min(sign_up_ts) AS conv_ts
    FROM sessoes WHERE sign_up = 1 GROUP BY user_pseudo_id
)
SELECT
    s.user_pseudo_id,
    s.session_key,
    s.inicio_sessao,
    s.canal,
    row_number() OVER (PARTITION BY s.user_pseudo_id ORDER BY s.inicio_sessao)       AS posicao,
    count(*)     OVER (PARTITION BY s.user_pseudo_id)                                 AS n_toques
FROM sessoes s
JOIN conv c USING (user_pseudo_id)
WHERE s.inicio_sessao <= c.conv_ts;

CREATE OR REPLACE TABLE atribuicao_regras AS
WITH ultimo_nao_direto AS (
    -- padrão do GA4/Google Ads: o último clique que não seja "Direct" leva o crédito
    SELECT user_pseudo_id,
           coalesce(arg_max(canal, posicao) FILTER (WHERE canal <> 'Direct'), 'Direct') AS canal
    FROM jornadas GROUP BY user_pseudo_id
),
creditos AS (
    SELECT canal, 'first_click' AS modelo, 1.0 AS credito FROM jornadas WHERE posicao = 1
    UNION ALL
    SELECT canal, 'last_click', 1.0 FROM jornadas WHERE posicao = n_toques
    UNION ALL
    SELECT canal, 'last_non_direct_click', 1.0 FROM ultimo_nao_direto
    UNION ALL
    SELECT canal, 'linear', 1.0 / n_toques FROM jornadas
    UNION ALL
    -- posição (U): 40% primeiro, 40% último, 20% dividido no meio
    SELECT canal, 'position_based',
           CASE WHEN n_toques = 1 THEN 1.0
                WHEN n_toques = 2 THEN 0.5
                WHEN posicao = 1 OR posicao = n_toques THEN 0.4
                ELSE 0.2 / (n_toques - 2) END
    FROM jornadas
)
SELECT modelo, canal, sum(credito) AS conversoes
FROM creditos
GROUP BY ALL
ORDER BY modelo, conversoes DESC;

-- Caminhos mais comuns até a conversão (insumo do modelo de Markov em Python)
CREATE OR REPLACE TABLE caminhos AS
SELECT caminho, count(*) AS conversoes
FROM (
    SELECT user_pseudo_id, string_agg(canal, ' > ' ORDER BY posicao) AS caminho
    FROM jornadas GROUP BY user_pseudo_id
)
GROUP BY caminho
ORDER BY conversoes DESC;
