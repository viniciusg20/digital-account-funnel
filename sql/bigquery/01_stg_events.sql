-- =====================================================================
-- Staging dos eventos do GA4 no BigQuery (export nativo events_*)
-- Achata event_params com o padrão UNNEST, que é a primeira coisa que todo
-- analista de GA4 + BigQuery precisa dominar.
-- Troque `projeto.analytics_123456789` pelo seu dataset.
-- =====================================================================
CREATE OR REPLACE TABLE `projeto.funnel.stg_events`
PARTITION BY event_date
CLUSTER BY event_name, user_pseudo_id AS
SELECT
  PARSE_DATE('%Y%m%d', event_date)                                                   AS event_date,
  TIMESTAMP_MICROS(event_timestamp)                                                  AS event_ts,
  event_name,
  user_pseudo_id,
  user_id,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id')     AS ga_session_id,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS ga_session_number,
  CONCAT(user_pseudo_id, '.',
         CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)) AS session_key,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location')     AS page_location,
  REGEXP_EXTRACT((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
                 r'https?://[^/]+([^?#]*)')                                           AS page_path,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_engaged')   AS session_engaged,
  (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'step_number')       AS step_number,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'experiment_onboarding') AS variante,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'cta_location')      AS cta_location,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'error_field')       AS error_field,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'transaction_id')    AS transaction_id,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'event_source')      AS event_source,
  (SELECT COALESCE(value.double_value, CAST(value.int_value AS FLOAT64))
     FROM UNNEST(event_params) WHERE key = 'value')                                   AS value,
  traffic_source.source AS first_source,
  traffic_source.medium AS first_medium,
  collected_traffic_source.manual_source                                             AS utm_source_raw,
  collected_traffic_source.manual_medium                                             AS utm_medium_raw,
  collected_traffic_source.manual_campaign_name                                      AS utm_campaign,
  collected_traffic_source.gclid                                                     AS gclid,
  device.category                                                                    AS device,
  device.operating_system                                                            AS os,
  geo.region                                                                         AS regiao
FROM `projeto.analytics_123456789.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20260801' AND '20260930';   -- partição: lê só o período
