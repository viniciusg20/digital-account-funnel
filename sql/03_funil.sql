-- Funil de abertura de conta: sessão (site) → usuário (cadastro) → backend (KYC e 1º depósito).

-- 1) Funil por sessão, quebrado por canal e dispositivo
CREATE OR REPLACE TABLE funil_sessao AS
SELECT
    canal,
    device,
    count(*)                                           AS sessoes,
    sum(engajada)                                      AS engajadas,
    sum(cta_click)                                     AS clique_cta,
    sum(begin_onboarding)                              AS inicio_onboarding,
    sum(etapa_1)                                       AS etapa_1,
    sum(sign_up)                                       AS cadastros,
    sum(sign_up) / count(*)                            AS conv_sessao,
    sum(sign_up) / nullif(sum(begin_onboarding), 0)    AS conclusao_formulario,
    sum(teve_erro_form) / nullif(sum(begin_onboarding), 0) AS taxa_erro_formulario
FROM sessoes
GROUP BY ROLLUP (canal, device);

-- 2) Funil em formato longo (para gráfico de funil no Looker Studio / Power BI)
CREATE OR REPLACE TABLE funil_etapas AS
WITH backend_web AS (
    SELECT count(*) AS contas, sum(CASE WHEN kyc_aprovado THEN 1 ELSE 0 END) AS aprovadas,
           sum(CASE WHEN first_deposit_at IS NOT NULL THEN 1 ELSE 0 END) AS depositaram
    FROM backend WHERE origem = 'web'
),
etapas AS (
    SELECT 1 AS ordem, 'Sessões' AS etapa, count(*)::DOUBLE AS volume FROM sessoes
    UNION ALL SELECT 2, 'Sessões engajadas', sum(engajada) FROM sessoes
    UNION ALL SELECT 3, 'Clique em "Abrir conta"', sum(cta_click) FROM sessoes
    UNION ALL SELECT 4, 'Início do onboarding', sum(begin_onboarding) FROM sessoes
    UNION ALL SELECT 5, '1ª etapa concluída', sum(etapa_1) FROM sessoes
    UNION ALL SELECT 6, 'Cadastro enviado (sign_up)', sum(sign_up) FROM sessoes
    UNION ALL SELECT 7, 'Conta aprovada (KYC)', aprovadas FROM backend_web
    UNION ALL SELECT 8, 'Primeiro depósito (ativação)', depositaram FROM backend_web
)
SELECT
    ordem, etapa, volume,
    volume / first_value(volume) OVER (ORDER BY ordem)          AS pct_do_topo,
    volume / lag(volume) OVER (ORDER BY ordem)                  AS conv_etapa_anterior,
    1 - volume / lag(volume) OVER (ORDER BY ordem)              AS abandono_etapa
FROM etapas
ORDER BY ordem;

-- 3) Onde o formulário quebra: erros por campo e por dispositivo
CREATE OR REPLACE TABLE erros_formulario AS
SELECT
    e.error_field                       AS campo,
    s.device,
    e.step_number                       AS etapa,
    count(*)                            AS erros,
    count(DISTINCT e.session_key)       AS sessoes_com_erro
FROM stg_events e
JOIN sessoes s USING (session_key)
WHERE e.event_name = 'form_error'
GROUP BY ALL
ORDER BY erros DESC;
