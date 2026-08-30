import os
import sys
from pathlib import Path

# Add project root to sys.path so we can cleanly import from src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.db.run_sql_file import run_sql_file

# We import the python-based attribution scripts to execute them alongside the SQL
from src.attribution.build_touchpoints import build_touchpoints
from src.attribution.calculate_attribution import calculate_attribution

def rebuild_all():
    # Define the exact order of SQL files required to rebuild the entire pipeline
    sql_files = [
        "database/schema/create_mart_tables.sql",
        "sql/marts/transform_to_marts.sql",
        "sql/analysis/funnel_conversion.sql",
        "sql/analysis/cac_roas.sql",
        "sql/analysis/customer_ltv.sql",
        "sql/analysis/cohort_retention.sql",
        "sql/analysis/pricing_analytics.sql",
        "sql/analysis/attribution_comparison.sql"
    ]
    
    total_steps = len(sql_files)
    
    print("Starting full database rebuild...\n")
    
    # Run each SQL file in sequence
    for i, rel_path in enumerate(sql_files, 1):
        file_path = PROJECT_ROOT / rel_path
        print(f"Step {i} of {total_steps}: running {rel_path}...")
        run_sql_file(file_path)
        
    print("\nFull rebuild complete.")
    
    # ---------------------------------------------------------
    # LIMITATION NOTE:
    # ---------------------------------------------------------
    # The SQL files above handle the core data warehouse transformations entirely in Postgres.
    # However, build_touchpoints.py and calculate_attribution.py are standalone Python scripts,
    # not SQL files, because they rely on pandas for complex multi-touch time-decay math 
    # that is difficult to express cleanly in raw SQL.
    # 
    # To make this script a true "rebuild all" button, we bypass this limitation by 
    # directly importing and calling their main logic here rather than making the user 
    # run them manually from the terminal afterwards.
    # ---------------------------------------------------------
    
    print("\n--- Running Python Attribution Scripts ---")
    print("Executing build_touchpoints logic...")
    build_touchpoints()
    
    print("\nExecuting calculate_attribution logic...")
    calculate_attribution()
    
    print("\nPipeline fully rebuilt and analytics updated!")

if __name__ == "__main__":
    rebuild_all()
