-- Business Question: For each marketing channel (traffic source and medium), 
-- how many distinct customers reached each key stage of the purchasing funnel 
-- (viewing an item -> adding to cart -> beginning checkout -> completing purchase), 
-- and what is the conversion drop-off rate between each of these sequential stages?
DROP VIEW IF EXISTS vw_funnel_conversion CASCADE;

CREATE VIEW vw_funnel_conversion AS
WITH customer_events AS (
    -- Link every event back to the session it occurred in, so we know 
    -- both the customer identity and the marketing channel that drove them.
    SELECT 
        s.traffic_source,
        s.traffic_medium,
        s.customer_id,
        e.event_name
    FROM events e
    JOIN sessions s ON e.session_id = s.session_id
),
funnel_counts AS (
    -- Conditionally aggregate distinct customers for each stage of the funnel.
    -- We use DISTINCT so if a user views 10 items in a session, they only count once.
    SELECT 
        traffic_source,
        traffic_medium,
        COUNT(DISTINCT CASE WHEN event_name = 'view_item' THEN customer_id END) AS view_item_customers,
        COUNT(DISTINCT CASE WHEN event_name = 'add_to_cart' THEN customer_id END) AS add_to_cart_customers,
        COUNT(DISTINCT CASE WHEN event_name = 'begin_checkout' THEN customer_id END) AS begin_checkout_customers,
        COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN customer_id END) AS purchase_customers
    FROM customer_events
    GROUP BY traffic_source, traffic_medium
)
SELECT 
    traffic_source,
    traffic_medium,
    view_item_customers,
    add_to_cart_customers,
    begin_checkout_customers,
    purchase_customers,
    
    -- Calculate stage-to-stage conversion rates as percentages.
    -- We cast to numeric for fractional division, and use NULLIF to prevent division by zero errors.
    ROUND((add_to_cart_customers::numeric / NULLIF(view_item_customers, 0)) * 100, 2) AS view_to_cart_rate_pct,
    ROUND((begin_checkout_customers::numeric / NULLIF(add_to_cart_customers, 0)) * 100, 2) AS cart_to_checkout_rate_pct,
    ROUND((purchase_customers::numeric / NULLIF(begin_checkout_customers, 0)) * 100, 2) AS checkout_to_purchase_rate_pct,
    
    -- Calculate the overall end-to-end conversion rate.
    ROUND((purchase_customers::numeric / NULLIF(view_item_customers, 0)) * 100, 2) AS overall_conversion_rate_pct
FROM funnel_counts
ORDER BY view_item_customers DESC;
