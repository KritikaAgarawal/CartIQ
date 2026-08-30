-- Business Question: How does each channel's attributed revenue differ 
-- between last-click, linear, and time-decay attribution models?
--
-- Note: Channel matching for last-click uses case-insensitive comparison (LOWER)
-- because traffic_source/medium values like '<Other>' can appear with inconsistent 
-- casing between pipeline stages.

DROP VIEW IF EXISTS vw_attribution_comparison CASCADE;

CREATE VIEW vw_attribution_comparison AS
WITH last_click AS (
    -- Last-click attribution natively exists in our orders -> sessions join.
    -- The session that immediately triggered the purchase gets 100% of the credit.
    SELECT 
        mc.channel_id,
        'last_click' AS attribution_model,
        SUM(o.order_total) AS attributed_revenue,
        COUNT(DISTINCT o.order_id) AS attributed_orders
    FROM orders o
    JOIN sessions s ON o.session_id = s.session_id
    JOIN marketing_channels mc 
        ON LOWER(s.traffic_source || ' / ' || s.traffic_medium) = LOWER(mc.channel_name)
    GROUP BY mc.channel_id
),
combined_models AS (
    -- Union the native last-click calculation with our pre-calculated 
    -- multi-touch models (linear and time_decay) from the data warehouse.
    SELECT 
        channel_id, 
        attribution_model, 
        attributed_revenue, 
        attributed_orders 
    FROM last_click
    
    UNION ALL
    
    SELECT 
        channel_id, 
        attribution_model, 
        attributed_revenue, 
        attributed_orders 
    FROM channel_attribution
)
-- Bring in the readable channel_name for final output and sort the models logically.
SELECT 
    mc.channel_name,
    cm.attribution_model,
    ROUND(cm.attributed_revenue, 2) AS attributed_revenue,
    cm.attributed_orders
FROM combined_models cm
JOIN marketing_channels mc ON cm.channel_id = mc.channel_id
ORDER BY 
    mc.channel_name ASC,
    CASE cm.attribution_model
        WHEN 'last_click' THEN 1
        WHEN 'linear' THEN 2
        WHEN 'time_decay' THEN 3
        ELSE 4
    END ASC;
