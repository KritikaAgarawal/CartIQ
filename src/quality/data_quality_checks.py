import os
import sys
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

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
    
    # Check if we successfully loaded the credentials
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Missing one or more database credentials in the .env file.")

    # Build the connection string in the format expected by SQLAlchemy for PostgreSQL
    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    return create_engine(connection_string)

def run_checks():
    """
    Connects to the database and runs a series of data quality checks,
    collecting the results and printing a summary report.
    """
    try:
        engine = get_engine()
    except Exception as e:
        print(f"Failed to initialize database engine: {e}")
        sys.exit(1)

    results = []

    try:
        # Connect to the database and run queries
        with engine.connect() as conn:
            
            # --- 1. NULL CHECKS ---
            # These checks ensure that columns which are required for data integrity 
            # (like IDs and quantities) do not contain null (empty) values.
            null_check_configs = [
                ("customers", "customer_id"),
                ("orders", "customer_id"),
                ("orders", "order_id"),
                ("orders", "order_total"),
                ("order_items", "product_id"),
                ("order_items", "quantity"),
                ("sessions", "session_id"),
                ("sessions", "customer_id"),
            ]
            
            for table, column in null_check_configs:
                # Query counts the number of rows where the specific column is null
                query = text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")
                count = conn.execute(query).scalar()
                
                status = "FAIL" if count > 0 else "PASS"
                details = f"{count} null values found"
                results.append({
                    "check_name": f"Null Check: {column}",
                    "table_name": table,
                    "status": status,
                    "details": details
                })
                
            # --- 2. DUPLICATE PRIMARY KEY CHECKS ---
            # These checks ensure that entities which should be unique (like a single 
            # order or customer) don't appear more than once in the table.
            duplicate_pk_configs = [
                ("customers", "customer_id"),
                ("orders", "order_id"),
                ("products", "product_id"),
                ("sessions", "session_id"),
            ]
            
            for table, column in duplicate_pk_configs:
                # Group by the primary key and find keys that have a count > 1 (duplicates)
                query = text(f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} HAVING COUNT(*) > 1")
                rows = conn.execute(query).fetchall()
                
                if len(rows) > 0:
                    status = "FAIL"
                    details = f"{len(rows)} duplicate keys found"
                else:
                    status = "PASS"
                    details = "0 duplicate keys found"
                    
                results.append({
                    "check_name": f"Duplicate PK Check: {column}",
                    "table_name": table,
                    "status": status,
                    "details": details
                })
                
            # --- 3. ORPHAN FOREIGN KEY CHECKS ---
            # These checks ensure referential integrity, meaning that if a row references 
            # a parent row (e.g., an order referencing a customer), that parent row actually exists.
            orphan_fk_configs = [
                ("orders", "customer_id", "customers", "customer_id"),
                ("order_items", "order_id", "orders", "order_id"),
                ("order_items", "product_id", "products", "product_id"),
                ("sessions", "customer_id", "customers", "customer_id"),
            ]
            
            for child_table, child_fk, parent_table, parent_pk in orphan_fk_configs:
                # LEFT JOIN pattern: try to match child rows to parent rows.
                # If a match isn't found, the parent's columns will be NULL in the result.
                query = text(f"""
                    SELECT COUNT(*) 
                    FROM {child_table} 
                    LEFT JOIN {parent_table} ON {child_table}.{child_fk} = {parent_table}.{parent_pk}
                    WHERE {parent_table}.{parent_pk} IS NULL 
                      AND {child_table}.{child_fk} IS NOT NULL
                """)
                count = conn.execute(query).scalar()
                
                status = "FAIL" if count > 0 else "PASS"
                details = f"{count} orphaned rows found"
                results.append({
                    "check_name": f"Orphan FK Check: {child_fk} -> {parent_table}.{parent_pk}",
                    "table_name": child_table,
                    "status": status,
                    "details": details
                })

            # --- 4. INVALID VALUE CHECKS ---
            # These checks ensure that values fall within logically expected ranges.
            invalid_value_configs = [
                ("orders", "order_total", "order_total < 0"),
                ("order_items", "quantity", "quantity <= 0"),
                ("order_items", "unit_price", "unit_price < 0"),
                ("products", "base_price", "base_price < 0"),
                ("ad_spend", "amount", "amount < 0"),
                ("orders", "order_date", "order_date < '2020-11-01' OR order_date > '2020-11-30'"),
                ("campaigns", "dates", "end_date < start_date"),
            ]
            
            for table, check_name_part, condition in invalid_value_configs:
                query = text(f"SELECT COUNT(*) FROM {table} WHERE {condition}")
                count = conn.execute(query).scalar()
                
                status = "FAIL" if count > 0 else "PASS"
                details = f"{count} invalid values found"
                results.append({
                    "check_name": f"Invalid Value Check: {check_name_part}",
                    "table_name": table,
                    "status": status,
                    "details": details
                })

    except SQLAlchemyError as e:
        print("\n=== Database Error ===")
        print(f"Failed to execute data quality checks.")
        print(f"Details: {e}")
        sys.exit(1)
    except Exception as e:
        print("\n=== Unexpected Error ===")
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

    # --- Print Report ---
    print("\n--- Data Quality Check Report ---")
    print(f"{'TABLE':<15} | {'CHECK NAME':<45} | {'STATUS':<6} | {'DETAILS'}")
    print("-" * 90)
    
    passed_count = 0
    for r in results:
        print(f"{r['table_name']:<15} | {r['check_name']:<45} | {r['status']:<6} | {r['details']}")
        if r['status'] == 'PASS':
            passed_count += 1
            
    print("-" * 90)
    print(f"{passed_count} of {len(results)} checks passed.\n")

    # --- Log Results to Database ---
    try:
        with engine.connect() as conn:
            run_timestamp = conn.execute(text("SELECT NOW()")).scalar()
            
        df = pd.DataFrame(results)
        df['run_timestamp'] = run_timestamp
        
        # We reorder columns to match the DB schema (excluding log_id which is SERIAL)
        df = df[['run_timestamp', 'check_name', 'table_name', 'status', 'details']]
        
        df.to_sql('data_quality_log', engine, if_exists='append', index=False)
        print(f"Logged {len(df)} data quality checks to data_quality_log at {run_timestamp}")
    except Exception as e:
        print(f"Warning: Failed to log data quality checks to database. {e}")

if __name__ == "__main__":
    run_checks()
