import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Set up absolute paths so the script can be run from anywhere
# __file__ is this script; parent.parent.parent navigates up to the CartIQ root folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
env_path = PROJECT_ROOT / '.env'

# Load the environment variables from .env to securely access database credentials
load_dotenv(dotenv_path=env_path)

def get_engine():
    """
    Creates and returns a SQLAlchemy engine connected to our PostgreSQL database.
    Reuses the connection string logic we use across the project.
    """
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    # Fast-fail if credentials aren't loaded properly
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Missing one or more database credentials in the .env file.")

    # Build the connection string for psycopg2 and create the engine pool
    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return create_engine(connection_string)

def load_csv_to_table(csv_path, table_name, engine):
    """
    Reads a processed CSV and loads it into a PostgreSQL staging table.
    We truncate the table first to ensure we never duplicate data when re-running.
    """
    file_path = PROJECT_ROOT / csv_path
    
    try:
        # 1. Read the CSV file into a pandas DataFrame
        print(f"Reading {csv_path}...")
        df = pd.read_csv(file_path)
        row_count = len(df)
        
        # 2. Truncate the table before loading
        # TRUNCATE empties the table instantly without logging every deleted row (unlike DELETE).
        # CASCADE ensures we don't hit errors if other tables depend on this one.
        # We wrap this in engine.begin() so it automatically commits.
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE;"))
            print(f"Truncated {table_name}.")
            
        # 3. Load the DataFrame into the database table
        # if_exists='append' means we insert rows into the empty table.
        # index=False means we don't insert the arbitrary row numbers from pandas into the DB.
        print(f"Loading data into {table_name}...")
        df.to_sql(name=table_name, con=engine, if_exists='append', index=False)
        
        # 4. Print the success message with row count
        print(f"Successfully loaded {row_count} rows into {table_name}.\n")
        
    except FileNotFoundError:
        # We catch missing files and print a friendly message rather than crashing
        print(f"Error: The file {file_path} does not exist. Skipping {table_name}.\n")
    except SQLAlchemyError as e:
        # Catch database specific errors (e.g. data type mismatches, missing tables)
        print(f"Database Error while loading {table_name}:\n{e}\nContinuing to next file...\n")
    except Exception as e:
        # Catch any other unexpected errors (like memory issues)
        print(f"Unexpected Error while loading {table_name}:\n{e}\nContinuing to next file...\n")

def main():
    try:
        # Initialize the database engine once for all operations
        engine = get_engine()
    except Exception as e:
        print(f"Failed to initialize database engine: {e}")
        return

    # Define the mapping of CSV files to their corresponding staging tables.
    # The order respects basic logical dependencies (loading simple dimension-like data first).
    load_jobs = [
        ("data/processed/marketing_channels.csv", "stg_marketing_channels"),
        ("data/processed/campaigns.csv", "stg_campaigns"),
        ("data/processed/ad_spend.csv", "stg_ad_spend"),
        ("data/processed/ga4_events.csv", "stg_ga4_events")
    ]
    
    print("Starting data load into staging tables...\n")
    print("=" * 60)
    
    # Process each pair
    for csv_path, table_name in load_jobs:
        load_csv_to_table(csv_path, table_name, engine)
        
    # 5. After all loads, query the database directly to print a final summary
    print("=" * 60)
    print("LOAD SUMMARY - DATABASE ROW COUNTS")
    print("=" * 60)
    
    # We use engine.connect() here because we are just reading (SELECT) and don't need a transaction
    with engine.connect() as conn:
        for _, table_name in load_jobs:
            try:
                # Execute the count query and fetch the scalar (single number) result
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"Table '{table_name}': {count} rows")
            except SQLAlchemyError as e:
                print(f"Table '{table_name}': Error fetching count - {e}")

if __name__ == "__main__":
    main()
