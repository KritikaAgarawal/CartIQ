import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import random

# Get the absolute path to the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'raw'

def generate_marketing_data():
    # Set a random seed so the generated data is consistent and reproducible 
    # each time you run the script, which is helpful for debugging and learning.
    np.random.seed(42)
    random.seed(42)

    # -------------------------------------------------------------------------
    # STEP 1: Read GA4 data and get distinct channels
    # -------------------------------------------------------------------------
    ga4_path = DATA_DIR / 'ga4_events.csv'
    print(f"Reading {ga4_path}...")
    
    try:
        # We only need the source and medium columns to determine the channels
        ga4_df = pd.read_csv(ga4_path, usecols=['traffic_source', 'traffic_medium'])
    except FileNotFoundError:
        print(f"Error: {ga4_path} not found. Please run pull_ga4_events.py first.")
        return

    # Drop duplicate rows to get unique combinations of source and medium
    # For example: a row with source="google", medium="cpc"
    unique_channels = ga4_df.drop_duplicates(subset=['traffic_source', 'traffic_medium']).dropna()

    # -------------------------------------------------------------------------
    # STEP 2: Build marketing_channels table
    # -------------------------------------------------------------------------
    print("Building marketing_channels table...")
    channels_data = []
    
    # itertuples() is an efficient way to loop over DataFrame rows
    for idx, row in enumerate(unique_channels.itertuples(), start=1):
        source = str(row.traffic_source).lower()
        medium = str(row.traffic_medium).lower()
        
        # Format the channel name as "source / medium" for easier reading
        channel_name = f"{source} / {medium}"
        
        # Determine the channel type based on keywords in the 'medium' field
        if 'cpc' in medium or 'paid' in medium:
            channel_type = 'paid'
        elif 'email' in medium:
            channel_type = 'email'
        elif 'organic' in medium:
            channel_type = 'organic'
        elif '(none)' in medium or 'direct' in medium:
            channel_type = 'direct'
        elif 'referral' in medium:
            channel_type = 'referral'
        else:
            channel_type = 'other'
            
        channels_data.append({
            'channel_id': idx,
            'channel_name': channel_name,
            'channel_type': channel_type
        })
        
    channels_df = pd.DataFrame(channels_data)
    
    # We filter out just the 'paid' channels because in our logic, 
    # we only run paid ad campaigns on these platforms.
    paid_channels = channels_df[channels_df['channel_type'] == 'paid']

    # -------------------------------------------------------------------------
    # STEP 3: Build campaigns table
    # -------------------------------------------------------------------------
    print("Building campaigns table...")
    campaigns_data = []
    campaign_id_counter = 1
    
    # Set our date boundaries for November 2020
    nov_start = datetime(2020, 11, 1)
    nov_end = datetime(2020, 11, 30)
    
    for channel in paid_channels.itertuples():
        # Generate between 3 and 8 campaigns for each paid channel
        num_campaigns = random.randint(3, 8)
        
        for _ in range(num_campaigns):
            # Generate a realistic budget using a lognormal distribution.
            # A lognormal distribution is "right-skewed", meaning most campaigns 
            # will have smaller budgets, but a few will have very large budgets, 
            # which mimics real-world marketing spending better than a uniform spread.
            budget = -1
            while budget < 500 or budget > 10000:
                # mean=7.5 gives a median around $1,800
                budget = np.random.lognormal(mean=7.5, sigma=1.0)
            
            # Calculate a random start date by adding a random number of days (0 to 28)
            # to the start of November.
            start_offset = random.randint(0, 28)
            start_date = nov_start + timedelta(days=start_offset)
            
            # Ensure the end date is after the start date, but doesn't exceed Nov 30th
            max_duration = (nov_end - start_date).days
            duration = random.randint(1, max(1, max_duration))
            end_date = start_date + timedelta(days=duration)
            
            campaigns_data.append({
                'campaign_id': campaign_id_counter,
                'channel_id': channel.channel_id,
                'campaign_name': f"{channel.channel_name} - Campaign {campaign_id_counter}",
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'budget': round(budget, 2)
            })
            campaign_id_counter += 1
            
    campaigns_df = pd.DataFrame(campaigns_data)

    # -------------------------------------------------------------------------
    # STEP 4: Build ad_spend table
    # -------------------------------------------------------------------------
    print("Building ad_spend table...")
    ad_spend_data = []
    spend_id_counter = 1
    
    # Define day-of-week multipliers (Monday=0, Sunday=6)
    # This simulates real traffic behavior where weekdays perform differently from weekends.
    dow_multipliers = {
        0: 1.2,  # Monday (higher spend)
        1: 1.2,  # Tuesday (higher spend)
        2: 1.1,  # Wednesday
        3: 1.1,  # Thursday
        4: 1.0,  # Friday (baseline)
        5: 0.7,  # Saturday (lower spend)
        6: 0.7   # Sunday (lower spend)
    }
    
    for channel in paid_channels.itertuples():
        # Assign a baseline daily budget for this specific channel
        baseline_daily_spend = random.uniform(50, 300)
        
        # Pick 2-3 random days in the month for a spend spike (simulating a big ad push)
        spike_days = random.sample(range(1, 31), random.randint(2, 3))
        
        for day in range(1, 31):
            current_date = datetime(2020, 11, day)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Check if there are any active campaigns for this channel on this date
            active_campaigns = campaigns_df[
                (campaigns_df['channel_id'] == channel.channel_id) &
                (campaigns_df['start_date'] <= date_str) &
                (campaigns_df['end_date'] >= date_str)
            ]
            
            # For simplicity, if multiple campaigns are active, we just attribute 
            # the spend to the first active campaign we find.
            campaign_id = active_campaigns.iloc[0]['campaign_id'] if not active_campaigns.empty else None
            
            # Only record ad spend if there's an active campaign running
            if campaign_id is not None:
                # Apply the day of week seasonality modifier
                dow = current_date.weekday()
                seasonality = dow_multipliers[dow]
                
                # Add small random noise using a normal distribution to make the data look organic
                noise = np.random.normal(loc=0, scale=baseline_daily_spend * 0.1)
                
                # Calculate the final daily amount
                amount = baseline_daily_spend * seasonality + noise
                
                # Apply the spike multiplier if this day is one of our chosen spike days
                if day in spike_days:
                    spike_multiplier = random.uniform(1.5, 2.0)
                    amount *= spike_multiplier
                    
                # Ensure we don't have negative spend (clip at 0) and round to 2 decimals for currency
                amount = round(max(0, amount), 2)
                
                ad_spend_data.append({
                    'spend_id': spend_id_counter,
                    'channel_id': channel.channel_id,
                    'campaign_id': campaign_id,
                    'spend_date': date_str,
                    'amount': amount
                })
                spend_id_counter += 1

    ad_spend_df = pd.DataFrame(ad_spend_data)

    # -------------------------------------------------------------------------
    # STEP 5: Save tables to CSV
    # -------------------------------------------------------------------------
    print("\nSaving tables to CSV...")
    channels_df.to_csv(DATA_DIR / 'marketing_channels.csv', index=False)
    campaigns_df.to_csv(DATA_DIR / 'campaigns.csv', index=False)
    ad_spend_df.to_csv(DATA_DIR / 'ad_spend.csv', index=False)

    # -------------------------------------------------------------------------
    # STEP 6: Print summary
    # -------------------------------------------------------------------------
    print("\n--- Summary ---")
    print(f"Total marketing channels created: {len(channels_df)}")
    print(f"Total campaigns created: {len(campaigns_df)}")
    print(f"Total ad_spend rows created: {len(ad_spend_df)}")
    
    print("\nTotal Ad Spend per Channel:")
    if not ad_spend_df.empty:
        # Merge the spend table with the channels table so we can group by the channel name
        spend_summary = ad_spend_df.merge(channels_df, on='channel_id')
        spend_by_channel = spend_summary.groupby('channel_name')['amount'].sum().round(2)
        
        for channel_name, total_spend in spend_by_channel.items():
            print(f"- {channel_name}: ${total_spend:,.2f}")
    else:
        print("No ad spend generated (perhaps no paid channels were found in the source data).")

if __name__ == "__main__":
    generate_marketing_data()
