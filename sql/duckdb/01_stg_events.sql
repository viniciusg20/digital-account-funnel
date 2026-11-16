-- Mesmo staging de sql/bigquery/01_stg_events.sql, no dialeto DuckDB (execução local).
-- As macros imitam o idioma (SELECT value.x FROM UNNEST(event_params) WHERE key = ...).
CREATE OR REPLACE MACRO ga_str(params, k) AS list_extract(list_filter(params, lambda p: p.key = k), 1).value.string_value;
CREATE OR REPLACE MACRO ga_int(params, k) AS list_extract(list_filter(params, lambda p: p.key = k), 1).value.int_value;
CREATE OR REPLACE MACRO ga_num(params, k) AS coalesce(
    list_extract(list_filter(params, lambda p: p.key = k), 1).value.double_value,
    list_extract(list_filter(params, lambda p: p.key = k), 1).value.int_value::DOUBLE);

CREATE OR REPLACE TABLE stg_events AS
SELECT
    strptime(event_date, '%Y%m%d')::DATE                                AS event_date,
    make_timestamp(event_timestamp)                                     AS event_ts,
    event_name,
    user_pseudo_id,
    user_id,
    ga_int(event_params, 'ga_session_id')                               AS ga_session_id,
    ga_int(event_params, 'ga_session_number')                           AS ga_session_number,
    user_pseudo_id || '.' || ga_int(event_params, 'ga_session_id')::VARCHAR AS session_key,
    ga_str(event_params, 'page_location')                               AS page_location,
    regexp_extract(ga_str(event_params, 'page_location'), 'https?://[^/]+([^?#]*)', 1) AS page_path,
    ga_str(event_params, 'session_engaged')                             AS session_engaged,
    ga_int(event_params, 'step_number')                                 AS step_number,
    ga_str(event_params, 'experiment_onboarding')                       AS variante,
    ga_str(event_params, 'cta_location')                                AS cta_location,
    ga_str(event_params, 'error_field')                                 AS error_field,
    ga_str(event_params, 'transaction_id')                              AS transaction_id,
    ga_str(event_params, 'event_source')                                AS event_source,
    ga_num(event_params, 'value')                                       AS value,
    traffic_source.source AS first_source,
    traffic_source.medium AS first_medium,
    collected_traffic_source.manual_source                              AS utm_source_raw,
    collected_traffic_source.manual_medium                              AS utm_medium_raw,
    collected_traffic_source.manual_campaign_name                       AS utm_campaign,
    collected_traffic_source.gclid                                      AS gclid,
    device.category                                                     AS device,
    device.operating_system                                             AS os,
    geo.region                                                          AS regiao
FROM events;
