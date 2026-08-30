import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Set up paths to safely locate the .env file relative to this script
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_path = PROJECT_ROOT / '.env'

# Load the environment variables from .env to securely access database credentials
load_dotenv(dotenv_path=env_path)

def get_engine():
    """
    Creates and returns a SQLAlchemy engine connected to our PostgreSQL database.
    This safely manages our database connection using credentials from the .env file.
    """
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Missing one or more database credentials in the .env file.")

    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(connection_string)

def build_touchpoints():
    engine = get_engine()
    
    print("Reading data from database...")
    
    # 1. Read all sessions into a DataFrame
    # We order them chronologically so we can figure out the sequence of events later.
    sessions_query = """
        SELECT session_id, customer_id, session_date, traffic_source, traffic_medium 
        FROM sessions 
        ORDER BY customer_id, session_date ASC
    """
    sessions_df = pd.read_sql(sessions_query, engine)
    
    # 2. Read all orders into a DataFrame
    orders_query = "SELECT order_id, customer_id, order_date FROM orders"
    orders_df = pd.read_sql(orders_query, engine)
    
    # Read the mapping of channel names to channel IDs
    channels_query = "SELECT channel_id, channel_name FROM marketing_channels"
    channels_df = pd.read_sql(channels_query, engine)

    print("Processing touchpoints logic...")
    
    # 3. For each order, find all of that customer's sessions that happened on or before the purchase
    # We do this by temporarily joining EVERY session a customer had to EVERY order they made.
    touchpoints = pd.merge(orders_df, sessions_df, on='customer_id', how='inner')
    
    # Then we strictly filter down to only sessions that happened BEFORE or ON the order date.
    touchpoints = touchpoints[touchpoints['session_date'] <= touchpoints['order_date']]
    
    # We only want to keep the most recent 10 sessions leading up to the purchase. 
    # To do this, we sort backwards (most recent first), take the top 10 per order, 
    # and then sort forwards again so they are in chronological order.
    touchpoints = touchpoints.sort_values(by=['order_id', 'session_date'], ascending=[True, False])
    touchpoints = touchpoints.groupby('order_id').head(10)
    touchpoints = touchpoints.sort_values(by=['order_id', 'session_date'], ascending=[True, True])
    
    # 4. Look up the channel_id for each touchpoint
    # First, reconstruct the channel_name string exactly as it looks in the marketing_channels table
    touchpoints['channel_name'] = touchpoints['traffic_source'].astype(str) + ' / ' + touchpoints['traffic_medium'].astype(str)
    
    # Merge on the channels lookup table. Using how='left' ensures that if there's no match, 
    # the row isn't deleted; it just gets a NaN (null) channel_id.
    touchpoints = pd.merge(touchpoints, channels_df, on='channel_name', how='left')
    
    # Count how many touchpoints didn't perfectly match a known marketing channel
    unmatched_count = touchpoints['channel_id'].isna().sum()
    
    # 5. Assign touchpoint chronological ordering
    # cumcount() starts at 0, so we add 1. This numbers the touchpoints 1, 2, 3... per order.
    touchpoints['touchpoint_order'] = touchpoints.groupby('order_id').cumcount() + 1
    
    # Set the timestamp to the session_date (since we only have date-level granularity for sessions right now)
    touchpoints['touchpoint_timestamp'] = pd.to_datetime(touchpoints['session_date'])
    
    # Select only the columns that physically exist in the customer_touchpoints table
    final_cols = ['customer_id', 'order_id', 'channel_id', 'touchpoint_timestamp', 'touchpoint_order']
    final_df = touchpoints[final_cols].copy()
    
    # Convert channel_id to a 'nullable integer' type so pandas doesn't accidentally 
    # turn the whole column into decimals just because a few nulls exist.
    final_df['channel_id'] = final_df['channel_id'].astype('Int64')
    
    # 6. Write the result to the database
    print("Writing touchpoints to the database...")
    with engine.begin() as conn:
        # We use CASCADE here just in case, though touchpoints shouldn't have children. 
        # This allows the script to be run over and over without creating duplicates.
        conn.execute(text("TRUNCATE TABLE customer_touchpoints CASCADE;"))
        print("Truncated customer_touchpoints.")
        
    final_df.to_sql('customer_touchpoints', engine, if_exists='append', index=False)
    
    # 7. Print summary metrics
    total_touchpoints = len(final_df)
    total_orders = len(final_df['order_id'].unique())
    
    # Avoid division by zero if there are no orders
    avg_touchpoints = (total_touchpoints / total_orders) if total_orders > 0 else 0.0
    
    print("\n--- Touchpoints Summary ---")
    print(f"Total touchpoints created: {total_touchpoints}")
    print(f"Average touchpoints per order: {avg_touchpoints:.2f}")
    print(f"Unmatched channel_id count: {unmatched_count}")

if __name__ == "__main__":
    build_touchpoints()
