import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

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

def calculate_linear_attribution():
    engine = get_engine()
    print("Reading touchpoints and orders from database...")
    
    # 1. Read touchpoints and orders into pandas DataFrames
    # We only need specific columns to calculate revenue distribution
    tp_query = "SELECT order_id, channel_id, touchpoint_order FROM customer_touchpoints"
    touchpoints_df = pd.read_sql(tp_query, engine)
    
    orders_query = "SELECT order_id, order_total FROM orders"
    orders_df = pd.read_sql(orders_query, engine)
    
    # Drop rows where channel_id is null, since we can't attribute revenue to an unknown channel
    touchpoints_df = touchpoints_df.dropna(subset=['channel_id']).copy()
    
    print("Calculating linear attribution credits...")
    
    # 2. Merge touchpoints with orders
    # This attaches the correct 'order_total' dollar amount to every single touchpoint row
    merged_df = pd.merge(touchpoints_df, orders_df, on='order_id', how='inner')
    
    # 3. For each order, count the total number of valid touchpoints it had
    # We create a mapping of how many touchpoints each order has...
    touchpoint_counts = merged_df.groupby('order_id').size().reset_index(name='num_touchpoints')
    
    # ...and merge that count back into our main dataset
    merged_df = pd.merge(merged_df, touchpoint_counts, on='order_id', how='inner')
    
    # 4. Compute linear credit
    # Linear attribution means every channel involved in the customer journey gets an EQUAL slice 
    # of the revenue pie. If a $100 order had 4 touchpoints, each touchpoint gets $25.
    merged_df['linear_credit'] = merged_df['order_total'] / merged_df['num_touchpoints']
    
    # 5. Group by marketing channel to aggregate the total attributed revenue and orders
    # We sum the linear_credit pieces to get total revenue, and count distinct order_ids to get total orders.
    channel_summary = merged_df.groupby('channel_id').agg(
        attributed_revenue=('linear_credit', 'sum'),
        attributed_orders=('order_id', 'nunique')
    ).reset_index()
    
    # Round the currency to 2 decimal places for a clean report
    channel_summary['attributed_revenue'] = channel_summary['attributed_revenue'].round(2)
    
    # 6. Add the attribution_model column so we know which model generated these numbers
    channel_summary['attribution_model'] = 'linear'
    
    # Rearrange the columns to match the requested output format
    final_cols = ['channel_id', 'attribution_model', 'attributed_revenue', 'attributed_orders']
    final_df = channel_summary[final_cols]
    
    # 7. Sort the results so the highest revenue channels appear at the top, and print them
    final_df = final_df.sort_values(by='attributed_revenue', ascending=False)
    
    print("\n--- Linear Attribution Results ---")
    print(final_df.to_string(index=False))
    
    # 8. Save the results to a CSV file in the processed data folder
    # We explicitly do NOT write this to the database yet.
    output_path = PROCESSED_DIR / 'attribution_linear.csv'
    
    # Ensure the directory exists before saving (just in case)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    final_df.to_csv(output_path, index=False)
    print(f"\nSuccessfully saved attribution results to {output_path}")

if __name__ == "__main__":
    calculate_linear_attribution()
