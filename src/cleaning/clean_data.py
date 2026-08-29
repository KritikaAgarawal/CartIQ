import pandas as pd
import numpy as np
from pathlib import Path

# Get absolute paths to the raw and processed data directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / 'data' / 'raw'
PROCESSED_DIR = PROJECT_ROOT / 'data' / 'processed'

# Ensure the processed directory exists before we try to write to it
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def initialize_log():
    # A helper function to create a standard logging dictionary for each file
    return {
        'rows_in': 0,
        'rows_out': 0,
        'duplicates_removed': 0,
        'nulls_fixed': 0,
        'invalid_values_fixed': 0
    }

def clean_ga4_events(logs):
    file_name = 'ga4_events.csv'
    log = initialize_log()
    
    try:
        # 1. Load the data using pandas
        df = pd.read_csv(RAW_DIR / file_name)
        log['rows_in'] = len(df)
        
        # 2. Convert event_date (e.g. 20201115) from a number/string to a proper date object
        # errors='coerce' turns invalid dates into NaT (Not a Time) rather than crashing
        df['event_date'] = pd.to_datetime(df['event_date'], format='%Y%m%d', errors='coerce').dt.date
        
        # 3. Convert event_timestamp from microseconds to a proper datetime column
        df['event_datetime'] = pd.to_datetime(df['event_timestamp'], unit='us', errors='coerce')
        
        # 4. Drop exact duplicates based on user, event name, and timestamp
        initial_len = len(df)
        df.drop_duplicates(subset=['user_pseudo_id', 'event_name', 'event_timestamp'], inplace=True)
        log['duplicates_removed'] += (initial_len - len(df))
        
        # 5. Drop rows missing critical IDs
        # We don't count these under a specific 'removed' key, they'll be reflected in rows_out
        df.dropna(subset=['user_pseudo_id', 'event_name'], inplace=True)
        
        # 6. Fill nulls in descriptive categorical columns with 'unknown'
        fill_cols = ['traffic_source', 'traffic_medium', 'campaign_name', 'device_category', 'country']
        for col in fill_cols:
            # Count how many nulls exist in this column before filling
            null_count = df[col].isnull().sum()
            log['nulls_fixed'] += null_count
            df[col].fillna('unknown', inplace=True)
            
        # Ensure session_id is filled with 'unknown_session' if missing
        if 'session_id' in df.columns:
            null_count = df['session_id'].isnull().sum()
            log['nulls_fixed'] += null_count
            df['session_id'].fillna('unknown_session', inplace=True)
            
        # 7. Handle impossible negative values for items_value
        # If someone "bought" negative value, it's bad data. We set it to null (np.nan).
        mask_negative = df['items_value'] < 0
        log['invalid_values_fixed'] += mask_negative.sum()
        df.loc[mask_negative, 'items_value'] = np.nan
        
        # 8. Flag purchases that are missing a transaction ID
        # Instead of deleting them, we create a boolean (True/False) flag column
        df['is_flagged_incomplete_purchase'] = False
        mask_incomplete = (df['event_name'] == 'purchase') & (df['transaction_id'].isnull())
        df.loc[mask_incomplete, 'is_flagged_incomplete_purchase'] = True
        
        # Save the cleaned file
        df.to_csv(PROCESSED_DIR / file_name, index=False)
        log['rows_out'] = len(df)
        logs[file_name] = log
        print(f"Successfully cleaned {file_name}")
        
    except FileNotFoundError:
        print(f"Error: {file_name} not found in {RAW_DIR}. Skipping.")

def clean_marketing_channels(logs):
    file_name = 'marketing_channels.csv'
    log = initialize_log()
    
    try:
        # 1. Load data
        df = pd.read_csv(RAW_DIR / file_name)
        log['rows_in'] = len(df)
        
        # 2. Drop duplicate channel IDs, keeping the first occurrence
        initial_len = len(df)
        df.drop_duplicates(subset=['channel_id'], keep='first', inplace=True)
        log['duplicates_removed'] += (initial_len - len(df))
        
        # 3. Fill missing channel types
        null_count = df['channel_type'].isnull().sum()
        log['nulls_fixed'] += null_count
        df['channel_type'].fillna('unknown', inplace=True)
        
        # Save
        df.to_csv(PROCESSED_DIR / file_name, index=False)
        log['rows_out'] = len(df)
        logs[file_name] = log
        print(f"Successfully cleaned {file_name}")
        
    except FileNotFoundError:
        print(f"Error: {file_name} not found in {RAW_DIR}. Skipping.")

def clean_campaigns(logs):
    file_name = 'campaigns.csv'
    log = initialize_log()
    
    try:
        # 1. Load data and parse dates
        df = pd.read_csv(RAW_DIR / file_name)
        log['rows_in'] = len(df)
        
        df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
        df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')
        
        # 2. Swap start/end dates if end_date occurs before start_date (data entry error)
        mask_swap = df['end_date'] < df['start_date']
        log['invalid_values_fixed'] += mask_swap.sum()
        
        # We use a temporary variable to securely swap values in a DataFrame
        temp = df.loc[mask_swap, 'start_date'].copy()
        df.loc[mask_swap, 'start_date'] = df.loc[mask_swap, 'end_date']
        df.loc[mask_swap, 'end_date'] = temp
        
        # Format the dates properly back to date-only formats for saving
        df['start_date'] = df['start_date'].dt.date
        df['end_date'] = df['end_date'].dt.date
        
        # 3. Drop campaigns missing critical mapping IDs
        df.dropna(subset=['campaign_id', 'channel_id'], inplace=True)
        
        # Save
        df.to_csv(PROCESSED_DIR / file_name, index=False)
        log['rows_out'] = len(df)
        logs[file_name] = log
        print(f"Successfully cleaned {file_name}")
        
    except FileNotFoundError:
        print(f"Error: {file_name} not found in {RAW_DIR}. Skipping.")

def clean_ad_spend(logs):
    file_name = 'ad_spend.csv'
    log = initialize_log()
    
    try:
        # 1. Load data and parse dates
        df = pd.read_csv(RAW_DIR / file_name)
        log['rows_in'] = len(df)
        
        df['spend_date'] = pd.to_datetime(df['spend_date'], errors='coerce').dt.date
        
        # 2. Fix invalid negative or null spend amounts by forcing them to 0.0
        mask_invalid = (df['amount'] < 0) | (df['amount'].isnull())
        log['invalid_values_fixed'] += mask_invalid.sum()
        df.loc[mask_invalid, 'amount'] = 0.0
        
        # 3. Drop exact duplicates for a given campaign on a given day
        initial_len = len(df)
        df.drop_duplicates(subset=['channel_id', 'campaign_id', 'spend_date'], inplace=True)
        log['duplicates_removed'] += (initial_len - len(df))
        
        # Save
        df.to_csv(PROCESSED_DIR / file_name, index=False)
        log['rows_out'] = len(df)
        logs[file_name] = log
        print(f"Successfully cleaned {file_name}")
        
    except FileNotFoundError:
        print(f"Error: {file_name} not found in {RAW_DIR}. Skipping.")

def clean_ga4_items(logs):
    file_name = 'ga4_items.csv'
    log = initialize_log()
    
    try:
        # 1. Load data
        df = pd.read_csv(RAW_DIR / file_name)
        log['rows_in'] = len(df)
        
        # 2. Convert dates exactly like ga4_events
        df['event_date'] = pd.to_datetime(df['event_date'], format='%Y%m%d', errors='coerce').dt.date
        df['event_timestamp'] = pd.to_datetime(df['event_timestamp'], unit='us', errors='coerce')
        
        # 3. Drop rows missing critical item_id
        df.dropna(subset=['item_id'], inplace=True)
        
        # 4. Fill null descriptive columns with 'unknown'
        for col in ['item_name', 'item_category']:
            null_count = df[col].isnull().sum()
            log['nulls_fixed'] += null_count
            df[col].fillna('unknown', inplace=True)
            
        # 5. Fix price (negative or null -> 0.0)
        mask_bad_price = (df['price'] < 0) | (df['price'].isnull())
        log['invalid_values_fixed'] += mask_bad_price.sum()
        df.loc[mask_bad_price, 'price'] = 0.0
        
        # 6. Fix quantity (negative or null -> 1)
        mask_bad_qty = (df['quantity'] < 0) | (df['quantity'].isnull())
        log['invalid_values_fixed'] += mask_bad_qty.sum()
        df.loc[mask_bad_qty, 'quantity'] = 1
        
        # 7. Drop duplicates based on the compound key of user + event + item
        initial_len = len(df)
        df.drop_duplicates(subset=['user_pseudo_id', 'event_name', 'event_timestamp', 'item_id'], inplace=True)
        log['duplicates_removed'] += (initial_len - len(df))
        
        # Save
        df.to_csv(PROCESSED_DIR / file_name, index=False)
        log['rows_out'] = len(df)
        logs[file_name] = log
        print(f"Successfully cleaned {file_name}")
        
    except FileNotFoundError:
        print(f"Error: {file_name} not found in {RAW_DIR}. Skipping.")

def main():
    # This dictionary will collect logs from all cleaning functions
    logs = {}
    
    print("Starting data cleaning process...")
    clean_ga4_events(logs)
    clean_marketing_channels(logs)
    clean_campaigns(logs)
    clean_ad_spend(logs)
    clean_ga4_items(logs)
    
    # If we successfully logged anything, print out the final summary table
    if logs:
        print("\n" + "="*85)
        print("CLEANING LOG SUMMARY")
        print("="*85)
        
        # Convert our dictionary to a DataFrame just to take advantage of its 
        # built-in clean table printing format
        summary_df = pd.DataFrame.from_dict(logs, orient='index')
        print(summary_df.to_string())
        print("="*85)
    else:
        print("\nNo files were cleaned.")

if __name__ == "__main__":
    main()
