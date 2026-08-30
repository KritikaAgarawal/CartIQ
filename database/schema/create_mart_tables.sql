-- Drop dependent tables first to respect foreign key constraints
DROP TABLE IF EXISTS data_quality_log CASCADE;
DROP TABLE IF EXISTS channel_attribution CASCADE;
DROP TABLE IF EXISTS customer_touchpoints CASCADE;
DROP TABLE IF EXISTS ad_spend CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS prices CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS marketing_channels CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- One row represents a single unique customer.
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    first_seen_date DATE NOT NULL,
    country TEXT
);

-- One row represents a single unique product in the catalog.
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    base_price NUMERIC NOT NULL
);

-- One row represents a unique marketing channel categorization (source/medium pair).
CREATE TABLE marketing_channels (
    channel_id INTEGER PRIMARY KEY,
    channel_name TEXT NOT NULL,
    channel_type TEXT NOT NULL
);

-- One row represents a single user visit/session on the website.
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    session_date DATE NOT NULL,
    traffic_source TEXT,
    traffic_medium TEXT,
    campaign_name TEXT,
    device_category TEXT
);

-- One row represents a pricing record for a product starting on a specific effective date.
CREATE TABLE prices (
    price_id SERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(product_id),
    effective_date DATE NOT NULL,
    price NUMERIC NOT NULL,
    discount_pct NUMERIC
);

-- One row represents a single marketing campaign running on a specific channel.
CREATE TABLE campaigns (
    campaign_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES marketing_channels(channel_id),
    campaign_name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    budget NUMERIC
);

-- One row represents a completed transaction/purchase order.
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    session_id TEXT REFERENCES sessions(session_id),
    order_date DATE NOT NULL,
    order_status TEXT,
    order_total NUMERIC NOT NULL
);

-- One row represents a single website interaction event within a session.
CREATE TABLE events (
    event_id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    event_name TEXT NOT NULL,
    event_datetime TIMESTAMP NOT NULL,
    product_id TEXT REFERENCES products(product_id)
);

-- One row represents a single line item of a product purchased within an order.
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL
);

-- One row represents the daily ad spend amount for a specific campaign.
CREATE TABLE ad_spend (
    spend_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES marketing_channels(channel_id),
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    spend_date DATE NOT NULL,
    amount NUMERIC NOT NULL
);

-- One row represents a single marketing touchpoint along a customer's journey to a specific order.
CREATE TABLE customer_touchpoints (
    touchpoint_id SERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    channel_id INTEGER NOT NULL REFERENCES marketing_channels(channel_id),
    touchpoint_timestamp TIMESTAMP NOT NULL,
    touchpoint_order INTEGER NOT NULL
);

-- One row represents the calculated revenue and order attribution for a channel under a specific model.
CREATE TABLE channel_attribution (
    attribution_id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES marketing_channels(channel_id),
    attribution_model TEXT,
    attributed_revenue NUMERIC,
    attributed_orders INTEGER
);

-- One row represents a single data quality check result.
CREATE TABLE data_quality_log (
    log_id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP DEFAULT NOW(),
    check_name TEXT,
    table_name TEXT,
    status TEXT,
    details TEXT
);
