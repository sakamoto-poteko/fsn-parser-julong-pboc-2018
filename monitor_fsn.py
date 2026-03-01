#!/usr/bin/env python3
"""
FSN File Directory Monitor
Monitors a directory for new FSN files and automatically parses them
"""
import os
import sys
import time
from pathlib import Path
from parse_final import parse_fsn10

def monitor_directory(directory, interval=2):
    """
    Monitor directory for new FSN files
    
    Args:
        directory: Path to directory to monitor
        interval: Check interval in seconds (default: 2)
    """
    directory = Path(directory).resolve()
    
    if not directory.exists():
        print(f"Error: Directory does not exist: {directory}")
        sys.exit(1)
    
    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}")
        sys.exit(1)
    
    print(f"{'='*80}")
    print(f"FSN File Monitor Started")
    print(f"{'='*80}")
    print(f"Monitoring directory: {directory}")
    print(f"Check interval: {interval} seconds")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*80}\n")
    
    # Track processed files
    processed_files = set()
    
    # Get initial list of FSN files
    for fsn_file in directory.glob("*.FSN"):
        processed_files.add(fsn_file.name)
        print(f"[EXISTING] {fsn_file.name}")
    
    if processed_files:
        print(f"\nFound {len(processed_files)} existing FSN file(s)")
        print("Waiting for new files...\n")
    
    try:
        while True:
            # Check for new FSN files
            current_files = set(f.name for f in directory.glob("*.FSN"))
            new_files = current_files - processed_files
            
            if new_files:
                for filename in sorted(new_files):
                    filepath = directory / filename
                    
                    # Wait a moment to ensure file is fully written
                    time.sleep(0.5)
                    
                    print(f"\n{'='*80}")
                    print(f"[NEW FILE DETECTED] {filename}")
                    print(f"{'='*80}")
                    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"Path: {filepath}")
                    print(f"Size: {filepath.stat().st_size:,} bytes")
                    print(f"{'='*80}\n")
                    
                    try:
                        # Parse the file
                        bills = parse_fsn10(str(filepath))
                        print(f"\n✓ Successfully parsed {len(bills)} records from {filename}\n")
                        
                    except Exception as e:
                        print(f"\n✗ Error parsing {filename}: {e}\n")
                    
                    # Mark as processed
                    processed_files.add(filename)
                    
                    print(f"{'='*80}")
                    print(f"Waiting for new files...")
                    print(f"{'='*80}\n")
            
            # Wait before next check
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n\n{'='*80}")
        print(f"Monitor stopped by user")
        print(f"Total files processed: {len(processed_files)}")
        print(f"{'='*80}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 monitor_fsn.py <directory> [check_interval_seconds]")
        print("\nExamples:")
        print("  python3 monitor_fsn.py /path/to/fsn/files")
        print("  python3 monitor_fsn.py . 5")
        print("  python3 monitor_fsn.py ~/Desktop/FSN")
        sys.exit(1)
    
    directory = sys.argv[1]
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    
    monitor_directory(directory, interval)

if __name__ == '__main__':
    main()
