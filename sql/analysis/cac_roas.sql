-- Business Question: For each marketing channel, what did we spend, how much
-- revenue did it drive, how many true new customers did it acquire, what is 
-- our Customer Acquisition Cost (CAC), and what is our Return on Ad Spend (ROAS)?
DROP VIEW IF EXISTS vw_channel_cac_roas CASCADE;

CREATE VIEW vw_channel_cac_roas AS
WITH spend_by_channel AS (
    -- 1. Calculate total ad spend per channel
    SELECT 
        channel_id, 
        SUM(amount) AS total_spend
    FROM ad_spend
    GROUP BY channel_id
),
orders_by_channel AS (
    -- 2. Link orders back to sessions, and then dynamically build the channel_name 
    -- string (source / medium) to map revenue back to the marketing_channels lookup table.
    SELECT 
        mc.channel_id,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(o.order_total) AS total_revenue
    FROM orders o
    JOIN sessions s ON o.session_id = s.session_id
    JOIN marketing_channels mc ON (s.traffic_source || ' / ' || s.traffic_medium) = mc.channel_name
    GROUP BY mc.channel_id
),
customer_first_session AS (
    -- 3a. Use a window function (ROW_NUMBER) to isolate every customer's very first session
    -- on our website, so we can attribute their "acquisition" to that specific channel.
    SELECT 
        customer_id,
        traffic_source,
        traffic_medium,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY session_date ASC) as session_rank
    FROM sessions
),
new_customers_by_channel AS (
    -- 3b. Count the distinct PAYING customers acquired by each channel using that rank 1 session.
    SELECT 
        mc.channel_id,
        COUNT(DISTINCT cfs.customer_id) AS new_paying_customers
    FROM customer_first_session cfs
    JOIN marketing_channels mc ON (cfs.traffic_source || ' / ' || cfs.traffic_medium) = mc.channel_name
    WHERE cfs.session_rank = 1
      AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = cfs.customer_id)
    GROUP BY mc.channel_id
)
-- 4. Bring it all together, ensuring every marketing channel is listed via LEFT JOINs.
SELECT 
    mc.channel_id,
    mc.channel_name,
    mc.channel_type,
    COALESCE(sbc.total_spend, 0) AS total_spend,
    COALESCE(obc.total_orders, 0) AS total_orders,
    COALESCE(obc.total_revenue, 0) AS total_revenue,
    COALESCE(ncb.new_paying_customers, 0) AS new_paying_customers,
    
    -- CAC and ROAS are mathematically and logically meaningful only for 'paid' channels. 
    -- Organic search, direct traffic, and email (usually) don't have direct ad spend in this context.
    -- Attempting to divide by zero spend on non-paid channels would result in errors or 
    -- infinite ROI, which isn't actionable for budget allocation. Thus, we force NULL.
    -- Note: CAC is calculated per PAYING customer acquired, not per casual site visitor.
    CASE 
        WHEN mc.channel_type = 'paid' THEN ROUND((sbc.total_spend / NULLIF(ncb.new_paying_customers, 0))::numeric, 2)
        ELSE NULL 
    END AS cac,
    
    CASE 
        WHEN mc.channel_type = 'paid' THEN ROUND((obc.total_revenue / NULLIF(sbc.total_spend, 0))::numeric, 2)
        ELSE NULL 
    END AS roas

FROM marketing_channels mc
LEFT JOIN spend_by_channel sbc ON mc.channel_id = sbc.channel_id
LEFT JOIN orders_by_channel obc ON mc.channel_id = obc.channel_id
LEFT JOIN new_customers_by_channel ncb ON mc.channel_id = ncb.channel_id
ORDER BY total_revenue DESC;
