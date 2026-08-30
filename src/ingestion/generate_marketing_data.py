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
    np.random.seed(42)
    random.seed(42)

    # -------------------------------------------------------------------------
    # STEP 1: Read GA4 data and get distinct channels & user volumes
    # -------------------------------------------------------------------------
    ga4_path = DATA_DIR / 'ga4_events.csv'
    print(f"Reading {ga4_path}...")
    
    try:
        # We now read user_pseudo_id as well to calculate real customer volume per channel
        ga4_df = pd.read_csv(ga4_path, usecols=['user_pseudo_id', 'traffic_source', 'traffic_medium'])
    except FileNotFoundError:
        print(f"Error: {ga4_path} not found. Please run pull_ga4_events.py first.")
        return

    # Drop duplicate rows to get unique combinations of source and medium
    unique_channels = ga4_df.drop_duplicates(subset=['traffic_source', 'traffic_medium']).dropna()

    # Calculate the approximate number of distinct customers per channel
    customer_counts = ga4_df.groupby(['traffic_source', 'traffic_medium'])['user_pseudo_id'].nunique().to_dict()

    # -------------------------------------------------------------------------
    # STEP 2: Build marketing_channels table
    # -------------------------------------------------------------------------
    print("Building marketing_channels table...")
    channels_data = []
    
    for idx, row in enumerate(unique_channels.itertuples(), start=1):
        source = str(row.traffic_source).lower()
        medium = str(row.traffic_medium).lower()
        
        channel_name = f"{source} / {medium}"
        
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
            'channel_type': channel_type,
            'source': row.traffic_source, # kept temporarily to map to customer_counts later
            'medium': row.traffic_medium
        })
        
    channels_df = pd.DataFrame(channels_data)
    
    # -------------------------------------------------------------------------
    # NEW STEP: Calibrate Spend per Paid Channel based on real customer volume
    # -------------------------------------------------------------------------
    # By calibrating spend directly to the actual volume of customers in the raw 
    # dataset, we ensure that our generated CAC and ROAS metrics are realistic.
    paid_channels = channels_df[channels_df['channel_type'] == 'paid'].copy()
    
    channel_spend_targets = {}
    channel_cacs = {}
    
    for row in paid_channels.itertuples():
        # 1. Get approximate real customers for this channel from the raw data
        approx_channel_customers = customer_counts.get((row.source, row.medium), 0)
        
        # 2. Generate a realistic target CAC ($15 - $60)
        target_cac = np.random.uniform(15, 60)
        
        # 3. Calculate total monthly spend needed to acquire this exact volume of customers
        total_month_spend = target_cac * approx_channel_customers
        
        channel_spend_targets[row.channel_id] = total_month_spend
        channel_cacs[row.channel_id] = target_cac

    # We can drop the temporary source/medium columns before saving later
    channels_df.drop(columns=['source', 'medium'], inplace=True)

    # -------------------------------------------------------------------------
    # STEP 3: Build campaigns table
    # -------------------------------------------------------------------------
    print("Building campaigns table...")
    campaigns_data = []
    campaign_id_counter = 1
    
    nov_start = datetime(2020, 11, 1)
    nov_end = datetime(2020, 11, 30)
    
    for row in paid_channels.itertuples():
        num_campaigns = random.randint(3, 8)
        
        # Generate initial raw budget weights using the right-skewed lognormal distribution
        raw_weights = []
        for _ in range(num_campaigns):
            weight = -1
            while weight < 500 or weight > 10000:
                weight = np.random.lognormal(mean=7.5, sigma=1.0)
            raw_weights.append(weight)
            
        # Normalize weights so they sum perfectly to 1.0, then scale to the channel's target spend
        total_weight = sum(raw_weights)
        normalized_weights = [w / total_weight for w in raw_weights]
        
        channel_total_spend = channel_spend_targets[row.channel_id]
        
        for i in range(num_campaigns):
            budget = normalized_weights[i] * channel_total_spend
            
            start_offset = random.randint(0, 28)
            start_date = nov_start + timedelta(days=start_offset)
            
            max_duration = (nov_end - start_date).days
            duration = random.randint(1, max(1, max_duration))
            end_date = start_date + timedelta(days=duration)
            
            campaigns_data.append({
                'campaign_id': campaign_id_counter,
                'channel_id': row.channel_id,
                'campaign_name': f"{row.channel_name} - Campaign {campaign_id_counter}",
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
    
    dow_multipliers = {
        0: 1.2,  # Monday
        1: 1.2,  # Tuesday
        2: 1.1,  # Wednesday
        3: 1.1,  # Thursday
        4: 1.0,  # Friday
        5: 0.7,  # Saturday
        6: 0.7   # Sunday
    }
    
    for row in paid_channels.itertuples():
        channel_id = row.channel_id
        total_month_spend = channel_spend_targets[channel_id]
        
        if total_month_spend == 0:
            continue # No customers, no spend needed
            
        # 1. Generate the daily pattern curve (seasonality + noise + spikes)
        spike_days = random.sample(range(1, 31), random.randint(2, 3))
        daily_pattern_weights = []
        
        for day in range(1, 31):
            current_date = datetime(2020, 11, day)
            dow = current_date.weekday()
            seasonality = dow_multipliers[dow]
            
            # Baseline is roughly 1.0; noise is relative to that
            noise = np.random.normal(loc=0, scale=0.1)
            weight = seasonality + noise
            
            if day in spike_days:
                weight *= random.uniform(1.5, 2.0)
                
            weight = max(0, weight)
            daily_pattern_weights.append((current_date.strftime('%Y-%m-%d'), weight))
            
        # 2. Normalize the curve so it sums exactly to 1.0
        total_pattern_weight = sum(w for _, w in daily_pattern_weights)
        
        # 3. Apply the normalized curve to the channel's total month spend
        for date_str, weight in daily_pattern_weights:
            normalized_weight = weight / total_pattern_weight
            amount = total_month_spend * normalized_weight
            
            active_campaigns = campaigns_df[
                (campaigns_df['channel_id'] == channel_id) &
                (campaigns_df['start_date'] <= date_str) &
                (campaigns_df['end_date'] >= date_str)
            ]
            
            # Map the spend to an active campaign. If none are currently active, 
            # we safely fallback to the channel's first campaign to ensure total spend is preserved.
            if not active_campaigns.empty:
                campaign_id = active_campaigns.iloc[0]['campaign_id']
            else:
                all_campaigns_for_channel = campaigns_df[campaigns_df['channel_id'] == channel_id]
                campaign_id = all_campaigns_for_channel.iloc[0]['campaign_id'] if not all_campaigns_for_channel.empty else None
            
            if campaign_id is not None:
                ad_spend_data.append({
                    'spend_id': spend_id_counter,
                    'channel_id': channel_id,
                    'campaign_id': campaign_id,
                    'spend_date': date_str,
                    'amount': round(amount, 2)
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
    
    print("\nTotal Ad Spend per Paid Channel (Calibrated to Real Volume):")
    for row in paid_channels.itertuples():
        c_id = row.channel_id
        target_cac = channel_cacs.get(c_id, 0)
        total_spend = channel_spend_targets.get(c_id, 0)
        print(f"- {row.channel_name}: Target CAC ${target_cac:.2f} -> Total Month Spend ${total_spend:,.2f}")

if __name__ == "__main__":
    generate_marketing_data()
