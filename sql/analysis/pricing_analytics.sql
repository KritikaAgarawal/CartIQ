-- Business Question: How does a product's average selling price (and the depth 
-- of discounting applied to it) relate to its overall purchase volume and total revenue?
--
-- IMPORTANT ANALYTICAL NOTE: 
-- This view presents a descriptive CORRELATION between discount levels, purchase 
-- volume, and revenue. It does NOT definitively prove that discounts CAUSE more 
-- purchases. Other confounding variables—such as seasonality, product category 
-- popularity, out-of-stock events, or differing baseline marketing spend—could 
-- also explain these patterns. Please interpret this as descriptive, correlative 
-- analysis rather than strict causal analysis.
DROP VIEW IF EXISTS vw_pricing_analytics CASCADE;

CREATE VIEW vw_pricing_analytics AS
WITH product_metrics AS (
    -- 1. Aggregate core sales metrics from the order_items fact table.
    -- (Note: Since item-level view data was decoupled from the main events 
    -- table in our architecture, we anchor this analysis strictly on purchase data).
    SELECT 
        product_id,
        COUNT(DISTINCT order_id) AS times_purchased,
        SUM(quantity * unit_price) AS product_revenue,
        AVG(unit_price) AS avg_selling_price
    FROM order_items
    GROUP BY product_id
)
-- 2. & 3. Join back to the products dimension to fetch baseline metadata 
-- and compute the effective discount depth.
SELECT 
    p.product_id,
    p.product_name,
    p.category,
    p.base_price,
    ROUND(pm.avg_selling_price::numeric, 2) AS avg_selling_price,
    
    -- Calculate the discount percentage.
    -- We use GREATEST(..., 0) to ensure that if a product happened to sell 
    -- for MORE than its base_price (e.g., dynamic pricing or surge pricing), 
    -- it doesn't confusingly display as a "negative" discount.
    ROUND(GREATEST(((p.base_price - pm.avg_selling_price) / NULLIF(p.base_price, 0)) * 100, 0)::numeric, 2) AS discount_pct,
    
    pm.times_purchased,
    pm.product_revenue
FROM product_metrics pm
JOIN products p ON pm.product_id = p.product_id
-- 4. Order the results so top-grossing products appear first
ORDER BY pm.product_revenue DESC;
