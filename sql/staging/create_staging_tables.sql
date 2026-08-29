-- Staging table for raw GA4 website and ecommerce event data
DROP TABLE IF EXISTS stg_ga4_events CASCADE;
CREATE TABLE stg_ga4_events (
    event_date date,
    event_datetime timestamp,
    event_name text,
    user_pseudo_id text,
    page_location text,
    traffic_source text,
    traffic_medium text,
    campaign_name text,
    device_category text,
    country text,
    transaction_id text,
    items_value numeric,
    is_flagged_incomplete_purchase boolean
);

-- Staging table for mapping distinct traffic source and medium combinations to categorized channels
DROP TABLE IF EXISTS stg_marketing_channels CASCADE;
CREATE TABLE stg_marketing_channels (
    channel_id integer,
    channel_name text,
    channel_type text
);

-- Staging table for tracking individual ad campaigns and their allocated budgets
DROP TABLE IF EXISTS stg_campaigns CASCADE;
CREATE TABLE stg_campaigns (
    campaign_id integer,
    channel_id integer,
    campaign_name text,
    start_date date,
    end_date date,
    budget numeric
);

-- Staging table for tracking daily ad spend by campaign and channel
DROP TABLE IF EXISTS stg_ad_spend CASCADE;
CREATE TABLE stg_ad_spend (
    spend_id integer,
    channel_id integer,
    campaign_id integer,
    spend_date date,
    amount numeric
);
