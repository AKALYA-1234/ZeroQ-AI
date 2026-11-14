#!/usr/bin/env python3
"""Import synthetic dataset CSV files into ZeroQ AI database"""
import sys, os, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')

def inspect_csv_files():
    print(f"Looking for CSV files in: {DATA_DIR}")
    if not os.path.exists(DATA_DIR):
        print(f"Directory not found: {DATA_DIR}")
        return []
    
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
    print(f"Found {len(csv_files)} CSV files: {csv_files}")
    return csv_files

def import_dataset():
    csv_files = inspect_csv_files()
    if not csv_files:
        print("No CSV files found. Place dataset CSV files in data/raw/ and run again.")
        return
    
    for csv_file in csv_files:
        path = os.path.join(DATA_DIR, csv_file)
        df = pd.read_csv(path)
        print(f"\n{csv_file}: {len(df)} rows, columns: {list(df.columns)}")
    
    print("\nNote: Full import logic will be implemented after inspecting actual column names from data dictionary.")

if __name__ == "__main__":
    import_dataset()
