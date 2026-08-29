import os
import sys
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
    
    # Check if we successfully loaded the credentials to prevent confusing errors later
    if not all([db_user, db_password, db_host, db_port, db_name]):
        raise ValueError("Missing one or more database credentials in the .env file.")

    # Build the connection string in the format expected by SQLAlchemy for PostgreSQL
    # Example format: postgresql+psycopg2://user:password@localhost:5432/dbname
    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # The engine is our core interface to the database. It manages connection pools efficiently.
    return create_engine(connection_string)

def run_sql_file(filepath):
    """
    Reads a SQL file and executes its contents against the database.
    It wraps the execution in a transaction: if one statement fails, 
    nothing is permanently applied to the database (rollback).
    """
    # 1. Verify the file exists before trying to read it
    file_path = Path(filepath)
    if not file_path.is_file():
        print(f"Error: The file '{filepath}' does not exist.")
        sys.exit(1)

    # 2. Read the entire SQL file into a single string
    with open(file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # If the file is just empty lines or spaces, there is nothing to do
    if not sql_content.strip():
        print(f"The file '{filepath}' is empty. Nothing to execute.")
        return

    # 3. Initialize the database engine
    try:
        engine = get_engine()
    except Exception as e:
        print(f"Failed to initialize database engine: {e}")
        sys.exit(1)

    # 4. Connect to the database and start a transaction
    # The 'with engine.begin() as conn:' block automatically manages the transaction.
    # If the block finishes successfully, it automatically COMMITS the changes.
    # If an exception is raised inside the block, it automatically ROLLS BACK.
    try:
        with engine.begin() as conn:
            # We wrap our raw SQL string in SQLAlchemy's text() construct.
            # psycopg2 (our driver) supports executing a block of multiple SQL statements 
            # separated by semicolons at once, so we don't need to manually split the string.
            conn.execute(text(sql_content))
            
        # If we reach this point, the block completed and committed successfully
        print(f"Success: ran {filepath}")
        
    except SQLAlchemyError as e:
        # Catch database-specific errors (like bad SQL syntax, missing tables, constraint violations)
        print("\n=== Database Error ===")
        print(f"Failed to execute '{filepath}'. The transaction has been rolled back safely.")
        print(f"Details: {e}")
        sys.exit(1)
    except Exception as e:
        # Catch any other unexpected errors (like memory issues or connection drops)
        print("\n=== Unexpected Error ===")
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # If the script is run directly from the terminal (e.g., 'python run_sql_file.py myscript.sql')
    # sys.argv contains the command-line arguments.
    # sys.argv[0] is the script name itself, sys.argv[1] is the first argument we passed.
    
    if len(sys.argv) < 2:
        print("Usage: python run_sql_file.py <path_to_sql_file>")
        sys.exit(1)
        
    target_filepath = sys.argv[1]
    run_sql_file(target_filepath)
