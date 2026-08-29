import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

# Get the absolute path to the project root directory
# __file__ is the path to this script (src/ingestion/pull_ga4_events.py)
# .parent.parent.parent navigates up three levels to the CartIQ folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load environment variables from the .env file located in the project root
# This safely loads sensitive info like credentials without hardcoding them in the script
env_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=env_path)

def pull_ga4_data():
    # 1. Retrieve the environment variables loaded from .env
    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    
    # We don't explicitly pass GOOGLE_APPLICATION_CREDENTIALS to the client.
    # The bigquery.Client() automatically looks for this environment variable
    # to authenticate with Google Cloud behind the scenes.
    
    try:
        # 2. Initialize the BigQuery client
        # This client object acts as our connection to the BigQuery service
        print("Connecting to Google BigQuery...")
        client = bigquery.Client(project=gcp_project_id)
        
        # 3. Define the SQL query
        # We query a public dataset of Google Analytics 4 (GA4) sample ecommerce data
        # The _TABLE_SUFFIX filter allows us to efficiently query a specific date range 
        # (November 2020) across multiple daily partitioned tables.
        query = """
            SELECT
                event_date,
                event_timestamp,
                event_name,
                user_pseudo_id,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_location,
                traffic_source.source AS traffic_source,
                traffic_source.medium AS traffic_medium,
                traffic_source.name AS campaign_name,
                device.category AS device_category,
                geo.country AS country,
                ecommerce.transaction_id AS transaction_id,
                (SELECT SUM(item.price * item.quantity) FROM UNNEST(items) AS item) AS items_value
            FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
            WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20201130'
                AND event_name IN ('page_view','view_item','add_to_cart','begin_checkout','purchase')
        """
        
        # 4. Execute the query
        print("Executing SQL query...")
        query_job = client.query(query)
        
        # 5. Wait for the query to finish and convert the results to a pandas DataFrame
        # A DataFrame is a powerful 2D data structure in Python, similar to a spreadsheet
        df = query_job.to_dataframe()
        print("Query successful!")
        
        # 6. Ensure the target directory for our raw data exists
        # parents=True means it will create parent folders like 'data' if they don't exist
        # exist_ok=True prevents an error if the directory is already there
        output_dir = PROJECT_ROOT / 'data' / 'raw'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 7. Save the DataFrame to a CSV file
        output_path = output_dir / 'ga4_events.csv'
        df.to_csv(output_path, index=False)
        print(f"Data saved successfully to {output_path}")
        
        # 8. Print out some basic information about the data we just pulled
        print(f"\nNumber of rows pulled: {len(df)}")
        print("First 5 rows of the dataset:")
        print(df.head())
        
    except GoogleAPIError as e:
        # Catch and print Google-specific API errors (like authentication failures or bad SQL)
        print("\nAn error occurred while interacting with BigQuery.")
        print(f"Error Details: {e}")
        print("Please check your .env file to ensure GOOGLE_APPLICATION_CREDENTIALS and GCP_PROJECT_ID are correctly configured and valid.")
    except Exception as e:
        # Catch any other unexpected errors (like missing folders or pandas-related errors)
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    pull_ga4_data()
