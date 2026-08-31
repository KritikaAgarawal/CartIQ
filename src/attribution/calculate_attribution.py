import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from src.utils.logger import get_logger

logger = get_logger('calculate_attribution')

# Set up absolute paths so this script can be run from anywhere in the terminal
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_path = PROJECT_ROOT / '.env'
PROCESSED_DIR = PROJECT_ROOT / 'data' / 'processed'

# Load our database credentials from the hidden .env file
load_dotenv(dotenv_path=env_path)

def get_engine():
    """
    Creates and returns a SQLAlchemy engine connected to our PostgreSQL database.
    This manages the connection securely so we can fetch our data.
    """
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Missing database credentials in the .env file.")

    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(connection_string)

def calculate_attribution():
    engine = get_engine()
    logger.info("Reading touchpoints and orders from database...")
    
    # 1. Read touchpoints and orders into pandas DataFrames
    # We bring in touchpoint_timestamp and order_date for the time-decay model
    tp_query = "SELECT order_id, channel_id, touchpoint_order, touchpoint_timestamp FROM customer_touchpoints"
    touchpoints_df = pd.read_sql(tp_query, engine)
    
    orders_query = "SELECT order_id, order_total, order_date FROM orders"
    orders_df = pd.read_sql(orders_query, engine)
    
    # Drop rows where channel_id is null, since we can't attribute revenue to an unknown channel
    touchpoints_df = touchpoints_df.dropna(subset=['channel_id']).copy()
    
    logger.info("Calculating linear attribution credits...")
    
    # 2. Merge touchpoints with orders
    # This attaches the correct 'order_total' and 'order_date' to every single touchpoint row
    merged_df = pd.merge(touchpoints_df, orders_df, on='order_id', how='inner')
    
    # 3. For each order, count the total number of valid touchpoints it had
    touchpoint_counts = merged_df.groupby('order_id').size().reset_index(name='num_touchpoints')
    merged_df = pd.merge(merged_df, touchpoint_counts, on='order_id', how='inner')
    
    # 4. Compute linear credit
    # Linear attribution means every channel involved in the customer journey gets an EQUAL slice.
    merged_df['linear_credit'] = merged_df['order_total'] / merged_df['num_touchpoints']
    
    # 5. Group by marketing channel to aggregate the total attributed revenue and orders
    linear_summary = merged_df.groupby('channel_id').agg(
        attributed_revenue=('linear_credit', 'sum'),
        attributed_orders=('order_id', 'nunique')
    ).reset_index()
    
    linear_summary['attributed_revenue'] = linear_summary['attributed_revenue'].round(2)
    linear_summary['attribution_model'] = 'linear'
    
    final_cols = ['channel_id', 'attribution_model', 'attributed_revenue', 'attributed_orders']
    linear_summary = linear_summary[final_cols].sort_values(by='attributed_revenue', ascending=False)
    
    logger.info("\n--- Linear Attribution Results ---")
    logger.info(linear_summary.to_string(index=False))
    
    # Ensure the directory exists before saving (just in case)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    linear_output = PROCESSED_DIR / 'attribution_linear.csv'
    linear_summary.to_csv(linear_output, index=False)
    logger.info(f"\nSuccessfully saved linear attribution results to {linear_output}")

    # =========================================================================
    # TIME DECAY ATTRIBUTION
    # =========================================================================
    logger.info("\nCalculating time-decay attribution credits...")
    
    # Ensure dates are in datetime format to subtract them safely
    merged_df['order_date'] = pd.to_datetime(merged_df['order_date'])
    merged_df['touchpoint_timestamp'] = pd.to_datetime(merged_df['touchpoint_timestamp'])
    
    # 1. Compute days_before_purchase
    # This represents how far in the past the touchpoint happened relative to the actual order.
    # We clip the minimum at 0, meaning a touchpoint cannot logically occur AFTER the order happens.
    days_diff = (merged_df['order_date'] - merged_df['touchpoint_timestamp']).dt.total_seconds() / (24 * 3600)
    merged_df['days_before_purchase'] = days_diff.clip(lower=0)
    
    # 2. Compute a raw decay weight using a half-life of 7 days
    # Half-life math: 0.5 ** (days / 7)
    # If a touchpoint happened exactly on order day (0 days), weight is 1.0 (100%).
    # If it happened 7 days prior, weight is 0.5 (50%).
    # If it happened 14 days prior, weight is 0.25 (25%).
    merged_df['raw_weight'] = 0.5 ** (merged_df['days_before_purchase'] / 7.0)
    
    # 3. Normalize the weights so they sum to 1.0 within each order
    # We must distribute exactly 100% of the revenue. If the raw weights for an order are 1.0 and 0.5,
    # they sum to 1.5. Normalizing them makes them 66.6% and 33.3% respectively.
    order_weight_sums = merged_df.groupby('order_id')['raw_weight'].sum().reset_index(name='total_weight')
    merged_df = pd.merge(merged_df, order_weight_sums, on='order_id', how='inner')
    merged_df['normalized_weight'] = merged_df['raw_weight'] / merged_df['total_weight']
    
    # 4. Compute time-decay credit
    merged_df['time_decay_credit'] = merged_df['order_total'] * merged_df['normalized_weight']
    
    # 5. Group by channel to aggregate the time-decay metrics
    decay_summary = merged_df.groupby('channel_id').agg(
        attributed_revenue=('time_decay_credit', 'sum'),
        attributed_orders=('order_id', 'nunique')
    ).reset_index()
    
    decay_summary['attributed_revenue'] = decay_summary['attributed_revenue'].round(2)
    decay_summary['attribution_model'] = 'time_decay'
    decay_summary = decay_summary[final_cols].sort_values(by='attributed_revenue', ascending=False)
    
    logger.info("\n--- Time-Decay Attribution Results ---")
    logger.info(decay_summary.to_string(index=False))
    
    decay_output = PROCESSED_DIR / 'attribution_time_decay.csv'
    decay_summary.to_csv(decay_output, index=False)
    logger.info(f"\nSuccessfully saved time-decay attribution results to {decay_output}")
    
    # =========================================================================
    # LOAD TO DATABASE
    # =========================================================================
    logger.info("\nLoading combined attribution data to the database...")
    combined_df = pd.concat([linear_summary, decay_summary], ignore_index=True)
    
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE channel_attribution CASCADE;"))
        logger.info("Truncated channel_attribution table.")
        
    combined_df.to_sql('channel_attribution', engine, if_exists='append', index=False)
    logger.info(f"Successfully loaded {len(combined_df)} rows into channel_attribution table.")

if __name__ == "__main__":
    calculate_attribution()
