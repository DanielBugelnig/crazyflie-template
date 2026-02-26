#!/usr/bin/env python3
"""
Script to delete all log files in the logs folder
"""

import os
import shutil
from pathlib import Path


def clear_logs(logs_dir="logs"):
    """
    Delete all contents in the logs directory.
    
    Args:
        logs_dir: Path to the logs directory (default: "logs")
    """
    script_dir = Path(__file__).parent
    logs_path = script_dir / logs_dir
    
    if not logs_path.exists():
        print(f"Logs directory '{logs_path}' does not exist.")
        return
    
    if not logs_path.is_dir():
        print(f"'{logs_path}' is not a directory.")
        return
    
    items = list(logs_path.iterdir())
    if not items:
        print("Logs directory is already empty.")
        return
    
    print(f"Found {len(items)} items in logs directory ({logs_path}):")
    for item in items:
        print(f"  - {item.name}")
    
    # confirm
    response = input(f"\nDelete all {len(items)} items in {logs_path}? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    deleted_count = 0
    for item in items:
        try:
            if item.is_dir():
                shutil.rmtree(item)
                print(f"Deleted directory: {item.name}")
            else:
                item.unlink()
                print(f"Deleted file: {item.name}")
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting {item.name}: {e}")
    
    print(f"\nSuccessfully deleted {deleted_count} items from logs directory.")


if __name__ == "__main__":
    clear_logs()
