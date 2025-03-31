{{ config(
    materialized='incremental',
    table_type='iceberg',
    format='parquet',
    incremental_strategy='merge',
    unique_key='hub_customer_key'
) }}

SELECT
    {{ dbt_utils.generate_surrogate_key(['customer_id']) }} AS hub_customer_key,
    customer_id,
    CAST(CURRENT_TIMESTAMP AS timestamp(6) with time zone) AS load_ts,
    record_source
FROM {{ ref('stg_customer_customer_demo') }}

{% if is_incremental() %}
WHERE customer_id NOT IN (SELECT customer_id FROM {{ this }})
{% endif %}