-- Business Question: Of the customers who made their first purchase in a given 
-- month (their "cohort"), how many returned to make another purchase in each 
-- subsequent month?
--
-- IMPORTANT LIMITATION NOTE: 
-- The current raw data ingestion pipeline for this project is hardcoded to pull 
-- only one single month of data (November 2020) from the public GA4 dataset. 
-- Because the available data spans less than 30 days, almost all records in this 
-- view will naturally fall into month_number = 0 (the acquisition month itself). 
-- However, this SQL logic is architecturally correct and mathematically sound; 
-- it will instantly populate with real multi-month retention curves the moment 
-- the upstream Python pipeline is modified to pull a wider date range.
DROP VIEW IF EXISTS vw_cohort_retention CASCADE;

CREATE VIEW vw_cohort_retention AS
WITH first_purchase AS (
    -- 1. Identify the 'cohort' for each customer by finding the exact month 
    -- they made their very first purchase.
    SELECT 
        customer_id,
        DATE_TRUNC('month', MIN(order_date))::date AS cohort_month
    FROM orders
    GROUP BY customer_id
),
order_months AS (
    -- 2. Map every single order back to the customer's original cohort month, 
    -- and dynamically calculate how many months have passed between their first 
    -- purchase and this specific order using year and month subtraction.
    SELECT 
        o.order_id,
        o.customer_id,
        fp.cohort_month,
        DATE_TRUNC('month', o.order_date)::date AS order_month,
        
        -- Calculate the integer difference in months
        ((EXTRACT(YEAR FROM o.order_date) - EXTRACT(YEAR FROM fp.cohort_month)) * 12)
        + (EXTRACT(MONTH FROM o.order_date) - EXTRACT(MONTH FROM fp.cohort_month)) AS month_number
        
    FROM orders o
    JOIN first_purchase fp ON o.customer_id = fp.customer_id
)
-- 3. Aggregate distinct active customers grouped by their starting cohort 
-- and how many months out they are still purchasing.
SELECT 
    cohort_month,
    month_number,
    COUNT(DISTINCT customer_id) AS active_customers
FROM order_months
GROUP BY cohort_month, month_number
ORDER BY cohort_month ASC, month_number ASC;
