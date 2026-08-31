import os
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Set up paths to safely locate the .env file relative to this script
# __file__ is the path to this script; parent.parent.parent navigates up to the CartIQ root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_path = PROJECT_ROOT / '.env'

# Load the environment variables from .env into our script
load_dotenv(dotenv_path=env_path)

def get_engine():
    """
    Creates and returns a SQLAlchemy engine connected to our PostgreSQL database.
    It reads credentials securely from environment variables instead of hardcoding them.
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


def calculate_channel_performance():
    """
    Reads channel performance and attribution data from the database.
    
    NOTE: ALL numbers here come from deterministic SQL/Python calculation - 
    this file has zero LLM involvement, which is intentional, since the LLM's 
    only job (in a separate file) will be to explain these pre-computed numbers, 
    never calculate them.
    """
    engine = get_engine()
    
    # 1. Read vw_channel_cac_roas for channels where cac is not null
    # 2. Also read channel_attribution (linear) and join
    # Join with marketing_channels for channel_name
    query = """
        SELECT 
            v.channel_id,
            m.channel_name,
            v.total_spend,
            v.total_revenue,
            v.cac,
            v.roas,
            ca.attributed_revenue AS attributed_revenue_linear
        FROM vw_channel_cac_roas v
        JOIN marketing_channels m ON v.channel_id = m.channel_id
        LEFT JOIN channel_attribution ca 
            ON v.channel_id = ca.channel_id 
            AND ca.attribution_model = 'linear'
        WHERE v.cac IS NOT NULL
    """
    df = pd.read_sql(query, engine)
    
    # 3. Compute marginal_roas_signal (PROXY)
    df['marginal_roas_signal'] = df['attributed_revenue_linear'] / df['total_spend']
    
    # Add data_limitation text column
    df['data_limitation'] = "Single-period data - this is average ROAS, not a true marginal/incremental ROAS estimate"
    
    # Ensure specific return column order (as requested)
    columns_to_return = [
        'channel_id', 'channel_name', 'total_spend', 'total_revenue', 
        'cac', 'roas', 'attributed_revenue_linear', 'marginal_roas_signal', 'data_limitation'
    ]
    
    return df[columns_to_return]


def recommend_budget_changes(df):
    """
    Generates budget recommendations using ONLY simple deterministic rules.
    
    NOTE: ALL numbers here come from deterministic SQL/Python calculation - 
    this file has zero LLM involvement, which is intentional, since the LLM's 
    only job (in a separate file) will be to explain these pre-computed numbers, 
    never calculate them.
    """
    # - If roas > 1.5: recommend_direction = 'Increase', suggested_change_pct = 15
    # - If roas is between 0.8 and 1.5: recommend_direction = 'Maintain', suggested_change_pct = 0
    # - If roas < 0.8: recommend_direction = 'Decrease', suggested_change_pct = -20
    
    conditions = [
        df['roas'] > 1.5,
        df['roas'] < 0.8
    ]
    
    directions = ['Increase', 'Decrease']
    changes = [15, -20]
    
    df = df.copy() # Avoid SettingWithCopyWarning
    df['recommend_direction'] = np.select(conditions, directions, default='Maintain')
    df['suggested_change_pct'] = np.select(conditions, changes, default=0)
    
    return df


if __name__ == "__main__":
    df_perf = calculate_channel_performance()
    df_final = recommend_budget_changes(df_perf)
    
    # Print the final DataFrame
    print(df_final.to_string())
