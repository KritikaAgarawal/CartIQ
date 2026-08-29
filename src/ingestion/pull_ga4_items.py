import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

# Get the absolute path to the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load environment variables from the .env file located in the project root
env_path = PROJECT_ROOT / '.env'
load_dotenv(dotenv_path=env_path)

def pull_ga4_items_data():
    # Retrieve the GCP project ID from the .env file
    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    
    try:
        # Initialize the BigQuery client
        print("Connecting to Google BigQuery...")
        client = bigquery.Client(project=gcp_project_id)
        
        # Define the SQL query for item-level data
        # We UNNEST the items array so that each individual product gets its own row
        query = """
            SELECT
              event_date,
              event_timestamp,
              user_pseudo_id,
              (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
              event_name,
              ecommerce.transaction_id AS transaction_id,
              item.item_id,
              item.item_name,
              item.item_category,
              item.price,
              item.quantity
            FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
            UNNEST(items) AS item
            WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20201130'
              AND event_name IN ('view_item','add_to_cart','begin_checkout','purchase')
        """
        
        # Execute the query
        print("Executing SQL query...")
        query_job = client.query(query)
        
        # Convert the results to a pandas DataFrame
        df = query_job.to_dataframe()
        print("Query successful!")
        
        # Build the session_id column by concatenating user_pseudo_id and ga_session_id
        # This matches the pattern we established in pull_ga4_events.py
        df['session_id'] = df['user_pseudo_id'] + '_' + df['ga_session_id'].astype(str)
        
        # Ensure the target directory for our raw data exists
        output_dir = PROJECT_ROOT / 'data' / 'raw'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the DataFrame to a CSV file
        output_path = output_dir / 'ga4_items.csv'
        df.to_csv(output_path, index=False)
        print(f"Data saved successfully to {output_path}")
        
        # Print out a summary
        print(f"\nNumber of rows pulled: {len(df)}")
        print("First 5 rows of the dataset:")
        print(df.head())
        
    except GoogleAPIError as e:
        # Catch and print Google-specific API errors
        print("\nAn error occurred while interacting with BigQuery.")
        print(f"Error Details: {e}")
        print("Please check your .env file to ensure GOOGLE_APPLICATION_CREDENTIALS and GCP_PROJECT_ID are correctly configured and valid.")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    pull_ga4_items_data()
