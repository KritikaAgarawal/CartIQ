import logging
from pathlib import Path

def get_logger(script_name: str) -> logging.Logger:
    """
    Configures and returns a logger that outputs to both a file and the console.
    
    Args:
        script_name: The name of the script or module requesting the logger.
        
    Returns:
        A configured logging.Logger instance.
    """
    # Create logger and set the logging level to INFO
    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if the logger is requested multiple times
    if logger.hasHandlers():
        return logger

    # Find the project root (3 levels up from src/utils/logger.py)
    project_root = Path(__file__).resolve().parent.parent.parent
    logs_dir = project_root / "logs"
    
    # Create the 'logs' folder at the project root if it doesn't exist
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    log_file_path = logs_dir / "cartiq_pipeline.log"

    # Define the log message format (e.g., "2026-08-30 14:22:01 - script_name - INFO - message")
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. File Handler: writes to logs/cartiq_pipeline.log in append mode
    file_handler = logging.FileHandler(log_file_path, mode='a')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 2. Console Handler: prints output to the terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
