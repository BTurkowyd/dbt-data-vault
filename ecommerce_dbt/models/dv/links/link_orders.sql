{{ config(
    materialized='incremental',
    table_type='iceberg',
    format='parquet',
    incremental_strategy='merge',
    unique_key='link_order_key'
) }}

-- The source_data CTE is a reference to the stg_orders model
WITH source_data AS (
    SELECT * FROM {{ ref('stg_orders') }}
),
-- The hub_orders CTE is a reference to the hub_orders model
hub_orders AS (
    SELECT order_id, hub_order_key FROM {{ ref('hub_orders') }}
),
-- The hub_customers CTE is a reference to the hub_customers model
hub_customers AS (
    SELECT customer_id, hub_customer_key FROM {{ ref('hub_customers') }}
)
-- The final SELECT statement generates the surrogate key for the link table
SELECT
    {{ dbt_utils.generate_surrogate_key(['ho.hub_order_key', 'hc.hub_customer_key']) }} AS link_order_key,
    ho.hub_order_key,
    hc.hub_customer_key,
    CAST(CURRENT_TIMESTAMP AS timestamp(6) with time zone) AS load_ts,
    record_source
FROM source_data sd
-- The JOIN clause links the source_data and hub_orders CTEs on the order_id column
JOIN hub_orders ho ON sd.order_id = ho.order_id
-- The JOIN clause links the source_data and hub_customers CTEs on the customer_id column
JOIN hub_customers hc ON sd.customer_id = hc.customer_id

{% if is_incremental() %}
-- Avoid inserting duplicate link rows
WHERE {{ dbt_utils.generate_surrogate_key(['sd.order_id', 'sd.customer_id']) }}
      NOT IN (SELECT link_order_key FROM {{ this }})
{% endif %}