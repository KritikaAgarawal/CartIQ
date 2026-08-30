import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Set up paths to safely locate the .env file relative to this script
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_path = PROJECT_ROOT / '.env'

# Load the environment variables from .env into our script
load_dotenv(dotenv_path=env_path)

def get_engine():
    """
    Creates and returns a SQLAlchemy engine connected to our PostgreSQL database.
    Reuses the secure connection string logic used across the project.
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

def main():
    try:
        engine = get_engine()
    except Exception as e:
        print(f"Failed to initialize database engine: {e}")
        return

    # Pandas settings to ensure our tables print nicely in the terminal without breaking lines
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)

    # ---------------------------------------------------------
    # 1. CAC / ROAS
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("CAC / ROAS (paid channels only)")
    print("=" * 80)
    query_cac = """
        SELECT channel_id, total_spend, total_revenue, new_customers, cac, roas 
        FROM vw_channel_cac_roas 
        WHERE cac IS NOT NULL 
        ORDER BY roas DESC
    """
    try:
        df_cac = pd.read_sql(text(query_cac), engine)
        print(df_cac.to_string(index=False))
    except Exception as e:
        print(f"Error querying vw_channel_cac_roas: {e}")

    # ---------------------------------------------------------
    # 2. Customer LTV
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("Customer LTV (top 5)")
    print("=" * 80)
    # Note: We alias acquisition_source to traffic_source to match the requested output
    query_ltv = """
        SELECT customer_id, acquisition_source AS traffic_source, total_orders, historical_ltv, average_order_value 
        FROM vw_customer_ltv 
        ORDER BY historical_ltv DESC 
        LIMIT 5
    """
    try:
        df_ltv = pd.read_sql(text(query_ltv), engine)
        print(df_ltv.to_string(index=False))
    except Exception as e:
        print(f"Error querying vw_customer_ltv: {e}")

    # ---------------------------------------------------------
    # 3. Cohort Retention
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("Cohort Retention")
    print("=" * 80)
    query_cohort = """
        SELECT * 
        FROM vw_cohort_retention 
        ORDER BY cohort_month, month_number 
        LIMIT 10
    """
    try:
        df_cohort = pd.read_sql(text(query_cohort), engine)
        print(df_cohort.to_string(index=False))
    except Exception as e:
        print(f"Error querying vw_cohort_retention: {e}")

    # ---------------------------------------------------------
    # 4. Pricing Analytics
    # ---------------------------------------------------------
    print("\n" + "=" * 80)
    print("Pricing Analytics (top 5 by revenue)")
    print("=" * 80)
    query_pricing = """
        SELECT product_name, base_price, avg_selling_price, discount_pct, times_purchased, product_revenue 
        FROM vw_pricing_analytics 
        ORDER BY product_revenue DESC 
        LIMIT 5
    """
    try:
        df_pricing = pd.read_sql(text(query_pricing), engine)
        print(df_pricing.to_string(index=False))
    except Exception as e:
        print(f"Error querying vw_pricing_analytics: {e}")

    print("\n")

if __name__ == "__main__":
    main()
