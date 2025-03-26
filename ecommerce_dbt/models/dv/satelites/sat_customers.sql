{{ config(
    materialized='incremental',
    table_type='iceberg',
    format='parquet',
    incremental_strategy='merge',
    unique_key='sat_customer_key',
    merge_update_columns=['hashdiff', 'load_ts', 'name', 'email']
) }}

WITH source_data AS (
    SELECT * FROM {{ ref('stg_customers') }}
),
hub_keys AS (
    SELECT customer_id, hub_customer_key FROM {{ ref('hub_customers') }}
),
prepared AS (
    SELECT
        sd.*,
        hk.hub_customer_key,
        {{ dbt_utils.generate_surrogate_key(['sd.name', 'sd.email']) }} AS hashdiff
    FROM source_data sd
    JOIN hub_keys hk ON sd.customer_id = hk.customer_id
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['hub_customer_key', 'hashdiff']) }} AS sat_customer_key,
    hub_customer_key,
    name,
    email,
    hashdiff,
    CAST(CURRENT_TIMESTAMP AS timestamp(6) with time zone) AS load_ts
FROM prepared

{% if is_incremental() %}
WHERE hashdiff NOT IN (SELECT hashdiff FROM {{ this }})
{% endif %}