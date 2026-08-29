-- Truncate all mart tables in dependency order (children before parents) to safely allow re-runs
TRUNCATE TABLE customer_touchpoints CASCADE;
TRUNCATE TABLE ad_spend CASCADE;
TRUNCATE TABLE order_items CASCADE;
TRUNCATE TABLE events CASCADE;
TRUNCATE TABLE orders CASCADE;
TRUNCATE TABLE campaigns CASCADE;
TRUNCATE TABLE prices CASCADE;
TRUNCATE TABLE sessions CASCADE;
TRUNCATE TABLE marketing_channels CASCADE;
TRUNCATE TABLE products CASCADE;
TRUNCATE TABLE customers CASCADE;

-- 1. Insert distinct marketing channels from the staging table
INSERT INTO marketing_channels (channel_id, channel_name, channel_type)
SELECT DISTINCT channel_id, channel_name, channel_type 
FROM stg_marketing_channels;

-- 2. Insert distinct ad campaigns, linking back to their parent marketing channels
INSERT INTO campaigns (campaign_id, channel_id, campaign_name, start_date, end_date, budget)
SELECT DISTINCT campaign_id, channel_id, campaign_name, start_date, end_date, budget 
FROM stg_campaigns;

-- 3. Insert daily ad spend records for each campaign
INSERT INTO ad_spend (spend_id, channel_id, campaign_id, spend_date, amount)
SELECT DISTINCT spend_id, channel_id, campaign_id, spend_date, amount 
FROM stg_ad_spend;

-- 4. Insert unique products, using DISTINCT ON to grab the most recent price seen as the base_price
INSERT INTO products (product_id, product_name, category, base_price)
SELECT DISTINCT ON (item_id) item_id, item_name, item_category, price 
FROM stg_ga4_items 
ORDER BY item_id, event_datetime DESC;

-- 5. Insert customers, calculating their first visit date and approximating their country
INSERT INTO customers (customer_id, first_seen_date, country)
SELECT user_pseudo_id, 
       MIN(event_date) AS first_seen_date, 
       MAX(country) AS country -- approximation: most recently seen country
FROM stg_ga4_events 
GROUP BY user_pseudo_id;

-- 6. Insert sessions, taking the very first event of the session to establish its traffic source
INSERT INTO sessions (session_id, customer_id, session_date, traffic_source, traffic_medium, campaign_name, device_category)
SELECT DISTINCT ON (session_id) 
       session_id, 
       user_pseudo_id AS customer_id, 
       event_date AS session_date, 
       traffic_source, 
       traffic_medium, 
       campaign_name, 
       device_category 
FROM stg_ga4_events
WHERE session_id IS NOT NULL 
ORDER BY session_id, event_datetime ASC;

-- 7. Insert all raw interaction events (pageviews, clicks, etc.), deliberately leaving product_id null here
INSERT INTO events (session_id, event_name, event_datetime, product_id)
SELECT session_id, event_name, event_datetime, NULL AS product_id 
FROM stg_ga4_events 
WHERE session_id IS NOT NULL;

-- 8. Insert completed purchase orders, taking the transaction timestamp from its earliest recorded event
INSERT INTO orders (order_id, customer_id, session_id, order_date, order_status, order_total)
SELECT DISTINCT ON (transaction_id) 
       transaction_id AS order_id, 
       user_pseudo_id AS customer_id, 
       session_id, 
       event_date AS order_date, 
       'completed' AS order_status, 
       items_value AS order_total
FROM stg_ga4_events 
WHERE event_name = 'purchase' 
  AND transaction_id IS NOT NULL 
ORDER BY transaction_id, event_datetime ASC;

-- 9. Insert individual line items mapped to their parent purchase orders
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT transaction_id AS order_id, 
       item_id AS product_id, 
       quantity, 
       price AS unit_price 
FROM stg_ga4_items
WHERE event_name = 'purchase' 
  AND transaction_id IS NOT NULL;
