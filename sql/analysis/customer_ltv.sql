-- Business Question: What is the historical lifetime value (total revenue 
-- generated to date) of each individual customer, and what marketing channel 
-- originally acquired them? 
--
-- Note: This calculates HISTORICAL LTV (actual revenue realized to date). 
-- It does not attempt to calculate PREDICTED LTV (a statistical forecast of 
-- future value), which is a possible future enhancement for this project.
DROP VIEW IF EXISTS vw_customer_ltv CASCADE;

CREATE VIEW vw_customer_ltv AS
WITH ranked_sessions AS (
    -- Assign a sequential rank to every session a customer has had, ordered by date
    SELECT 
        customer_id,
        traffic_source,
        traffic_medium,
        session_date,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY session_date ASC) AS session_rank
    FROM sessions
),
first_touch AS (
    -- 1. Isolate the rank 1 session to determine the exact channel that acquired them
    SELECT 
        customer_id,
        traffic_source AS acquisition_source,
        traffic_medium AS acquisition_medium,
        session_date AS acquisition_date
    FROM ranked_sessions
    WHERE session_rank = 1
),
customer_orders AS (
    -- 2. Aggregate all actual historical orders for each customer
    SELECT 
        customer_id,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(order_total) AS historical_ltv,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS last_order_date
    FROM orders
    GROUP BY customer_id
)
-- 3. Bring the acquisition channel and the lifetime revenue together.
-- We use a LEFT JOIN from first_touch to ensure we capture all users who 
-- visited the site, even if they haven't made a purchase yet (LTV = 0).
SELECT 
    ft.customer_id,
    ft.acquisition_source,
    ft.acquisition_medium,
    ft.acquisition_date,
    COALESCE(co.total_orders, 0) AS total_orders,
    COALESCE(co.historical_ltv, 0) AS historical_ltv,
    co.first_order_date,
    co.last_order_date,
    -- Calculate Average Order Value (AOV) for this specific customer
    ROUND((co.historical_ltv / NULLIF(co.total_orders, 0))::numeric, 2) AS average_order_value
FROM first_touch ft
LEFT JOIN customer_orders co ON ft.customer_id = co.customer_id
-- 4. Order the results so the most valuable customers appear at the top
ORDER BY historical_ltv DESC;
