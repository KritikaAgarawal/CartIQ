-- Business Question: Which customers are new/one-time buyers, repeat customers, 
-- or top-tier VIP customers, based on their order count and overall spend?
--
-- Note on Logic: The segmentation thresholds (e.g., >= 4 orders or >= $500 LTV 
-- for the VIP segment) are a reasonable, pragmatic starting point for immediate 
-- business analysis. They are simple heuristic rules of thumb, not a scientifically 
-- derived predictive clustering model.

DROP VIEW IF EXISTS vw_customer_segments CASCADE;

CREATE VIEW vw_customer_segments AS
SELECT 
    customer_id,
    acquisition_source,
    acquisition_medium,
    total_orders,
    historical_ltv,
    CASE 
        -- VIP takes top priority: a customer with just 2 massive orders is still highly valuable
        WHEN total_orders >= 4 OR historical_ltv >= 500 THEN 'VIP'
        WHEN total_orders = 0 OR total_orders IS NULL THEN 'No Purchase'
        WHEN total_orders = 1 THEN 'One-Time Buyer'
        WHEN total_orders BETWEEN 2 AND 3 THEN 'Repeat Customer'
        ELSE 'Unknown'
    END AS segment
FROM vw_customer_ltv;
