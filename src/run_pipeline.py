import subprocess
import sys
from src.utils.logger import get_logger

# Initialize the logger for this orchestrator script
logger = get_logger('run_pipeline')

def main():
    logger.info("Initializing full CartIQ pipeline run...")

    # We define the sequence of scripts to execute.
    # We use the subprocess module to run these scripts as separate terminal commands 
    # (e.g. running `python src/cleaning/clean_data.py`) rather than importing their 
    # functions directly. This is crucial during development, because it ensures each 
    # script remains completely independent and individually runnable when you're 
    # working on them. It also guarantees they run in a fresh memory environment.
    scripts = [
        "src/cleaning/clean_data.py",
        "src/ingestion/load_staging.py",
        "src/db/rebuild_all.py",
        "src/attribution/build_touchpoints.py",
        "src/attribution/calculate_attribution.py",
        "src/quality/data_quality_checks.py"
    ]

    success_count = 0
    failed_steps = []
    total_steps = len(scripts)

    for i, script in enumerate(scripts, start=1):
        logger.info(f"Starting step {i}: {script}")
        
        try:
            # We use subprocess.run to execute the script in a new Python process.
            # check=False means if the script crashes, it won't crash THIS script (we handle it below).
            # capture_output=True grabs whatever the script prints or errors out so we can log it.
            # text=True decodes the output from bytes into standard strings.
            result = subprocess.run(
                [sys.executable, script], 
                check=False, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Step {i} ({script}) completed successfully.")
                success_count += 1
            else:
                # If the script failed (non-zero exit code), we log its output to see what went wrong.
                # We continue to the next step regardless of this failure.
                error_msg = f"Step {i} ({script}) failed with return code {result.returncode}.\nOutput:\n{result.stdout}\nError:\n{result.stderr}"
                logger.error(error_msg)
                failed_steps.append(script)
                
        except Exception as e:
            # Catching unexpected errors (like if the script file doesn't exist)
            logger.error(f"Step {i} ({script}) encountered an unexpected error: {e}")
            failed_steps.append(script)

    # After all scripts have attempted to run, log a summary warning if there were any failures.
    if failed_steps:
        logger.warning(f"The following steps failed during the pipeline run: {', '.join(failed_steps)}")

    # Log the final summary count
    logger.info(f"Pipeline run complete. {success_count}/{total_steps} steps succeeded.")

if __name__ == "__main__":
    main()
