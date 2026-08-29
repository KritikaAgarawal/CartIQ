import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
u = os.getenv('DB_USER')
p = os.getenv('DB_PASSWORD')
h = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
db = os.getenv('DB_NAME')

engine = create_engine(f'postgresql+psycopg2://{u}:{p}@{h}:{port}/{db}')

for name, path in [('stg_ga4_events', 'data/processed/ga4_events.csv'), ('stg_ga4_items', 'data/processed/ga4_items.csv')]:
    print(f"Loading {name} from {path}...")
    try:
        df = pd.read_csv(path)
        df.to_sql(name, engine, if_exists='append', index=False, chunksize=5000, method='multi')
        print(f" Successfully inserted {len(df)} rows into {name}!")
    except Exception as e:
        print(f" Failed loading {name}: {e}")
