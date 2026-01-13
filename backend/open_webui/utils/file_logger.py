import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from open_webui.config import (
    ENABLE_LOG_TO_FILE,
    LOG_FILE_PATH,
    LOG_FILE_MAX_SIZE,
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_FORMAT,
    LOG_FILE_DATE_FORMAT,
)
from open_webui.env import GLOBAL_LOG_LEVEL


def parse_size_string(size_str: str) -> int:
    """
    Parse size string like '10MB', '1GB', '500KB' into bytes.
    
    Args:
        size_str: Size string with unit (B, KB, MB, GB)
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    # Extract number and unit
    if size_str.endswith('GB'):
        return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
    elif size_str.endswith('MB'):
        return int(float(size_str[:-2]) * 1024 * 1024)
    elif size_str.endswith('KB'):
        return int(float(size_str[:-2]) * 1024)
    elif size_str.endswith('B'):
        return int(size_str[:-1])
    else:
        # Assume bytes if no unit
        return int(size_str)


def setup_file_logging() -> Optional[logging.handlers.RotatingFileHandler]:
    """
    Set up file logging with rotation if enabled.
    This function is called from logger.py to integrate with Loguru.
    
    Returns:
        The file handler if logging is enabled, None otherwise
    """
    if not ENABLE_LOG_TO_FILE.value:
        return None
    
    try:
        # Import loguru here to avoid circular imports
        from loguru import logger
        
        # Generate timestamped log file name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"open-webui_{timestamp}.log"
        
        # Treat LOG_FILE_PATH as a directory path
        log_dir = Path(LOG_FILE_PATH.value)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Full path to the timestamped log file
        log_file_path = log_dir / log_filename
        
        # Parse the max file size for Loguru rotation
        max_size = LOG_FILE_MAX_SIZE.value
        
        # Use a format with milliseconds for precise timestamps
        simple_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
        
        # Add file handler to Loguru logger
        handler_id = logger.add(
            str(log_file_path),
            rotation=max_size,
            retention=LOG_FILE_BACKUP_COUNT.value,
            format=simple_format,
            level="DEBUG",  # Capture all log levels
            filter=lambda record: "auditable" not in record["extra"],  # Exclude audit logs
            encoding='utf-8'
        )
        
        # Log that file logging is enabled
        logger.info(f"File logging enabled: {log_file_path} (max size: {LOG_FILE_MAX_SIZE.value}, backups: {LOG_FILE_BACKUP_COUNT.value})")
        
        return None  # Loguru handles the file handler internally
        
    except Exception as e:
        # Use print for initial setup errors before logger is fully configured
        print(f"Failed to setup file logging: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_log_file_info() -> dict:
    """
    Get information about the current log file.
    
    Returns:
        Dictionary with log file information
    """
    if not ENABLE_LOG_TO_FILE.value:
        return {
            "enabled": False,
            "path": None,
            "size": None,
            "exists": False
        }
    
    log_dir = Path(LOG_FILE_PATH.value)
    
    info = {
        "enabled": True,
        "path": str(log_dir),
        "max_size": LOG_FILE_MAX_SIZE.value,
        "backup_count": LOG_FILE_BACKUP_COUNT.value,
        "format": LOG_FILE_FORMAT.value,
        "exists": False
    }
    
    # Find the most recent log file
    if log_dir.exists() and log_dir.is_dir():
        log_files = list(log_dir.glob("open-webui_*.log"))
        if log_files:
            # Get the most recent log file
            latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
            info["exists"] = True
            info["current_file"] = str(latest_log)
            
            try:
                stat = latest_log.stat()
                info["size"] = stat.st_size
                info["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
                info["modified"] = stat.st_mtime
            except Exception as e:
                info["error"] = str(e)
    
    return info


def get_log_files() -> list:
    """
    Get list of all log files (main + rotated backups).
    
    Returns:
        List of log file paths
    """
    if not ENABLE_LOG_TO_FILE.value:
        return []
    
    log_dir = Path(LOG_FILE_PATH.value)
    log_files = []
    
    if not log_dir.exists() or not log_dir.is_dir():
        return log_files
    
    # Find all open-webui log files in the directory
    all_log_files = list(log_dir.glob("open-webui_*.log*"))
    
    if not all_log_files:
        return log_files
    
    # Sort by modification time (newest first)
    all_log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    # The first file is the main (current) log file
    for i, log_file in enumerate(all_log_files):
        try:
            stat = log_file.stat()
            log_files.append({
                "path": str(log_file),
                "name": log_file.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_main": i == 0  # First file is the main one
            })
        except Exception as e:
            # Skip files that can't be accessed
            continue
    
    return log_files


def read_log_file(lines: int = 100, file_index: int = 0) -> dict:
    """
    Read the last N lines from a log file.
    
    Args:
        lines: Number of lines to read from the end
        file_index: Index of log file (0 = main, 1+ = backups)
        
    Returns:
        Dictionary with log content and metadata
    """
    if not ENABLE_LOG_TO_FILE.value:
        return {"error": "File logging is not enabled"}
    
    # Get the list of log files
    log_files = get_log_files()
    
    if not log_files:
        return {"error": "No log files found"}
    
    if file_index >= len(log_files):
        return {"error": f"Log file index {file_index} out of range (0-{len(log_files)-1})"}
    
    log_file_info = log_files[file_index]
    log_path = Path(log_file_info["path"])
    
    if not log_path.exists():
        return {"error": f"Log file does not exist: {log_path}"}
    
    try:
        # Read the file and get the last N lines
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            
        # Get the last N lines
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "content": ''.join(last_lines),
            "total_lines": len(all_lines),
            "returned_lines": len(last_lines),
            "file_path": str(log_path),
            "file_size": log_path.stat().st_size
        }
        
    except Exception as e:
        return {"error": f"Failed to read log file: {e}"}
