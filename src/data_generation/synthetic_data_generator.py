import os
import random
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Set random seed for reproducibility
np.random.seed(42)

def generate_inverter_data(num_records=300, num_inverters=5):
    """
    Generate synthetic inverter performance data
    
    Parameters:
    - num_records: Number of records to generate per inverter
    - num_inverters: Number of unique inverters
    
    Returns:
    - pandas DataFrame containing synthetic inverter data
    """
    # Create inverter IDs
    inverter_ids = [f"INV-{uuid.uuid4().hex[:8]}" for _ in range(num_inverters)]
    
    # Generate timestamps (starting 30 days ago, hourly readings)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    timestamps = [start_date + timedelta(hours=i) for i in range(num_records)]
    
    # Initialize lists to store data
    data = []
    
    # Generate data for each inverter
    for inv_id in inverter_ids:
        # Base efficiency varies by inverter (between 88% and 96%)
        base_efficiency = np.random.uniform(0.88, 0.96)
        
        # Base temperature behavior (some inverters run hotter than others)
        base_temp = np.random.uniform(40, 55)
        
        # Generate reading for each timestamp
        for ts in timestamps:
            # Time factors - solar availability depends on time of day
            hour = ts.hour
            is_daytime = 6 <= hour <= 18
            solar_factor = max(0, np.sin(np.pi * (hour - 6) / 12)) if is_daytime else 0
            
            # Ambient temperature: varies by time of day and has some random fluctuation
            ambient_temp = 20 + 10 * solar_factor + np.random.normal(0, 2)
            
            # Inverter temperature: influenced by ambient temp, load, and base characteristics
            inverter_temp = base_temp + 0.5 * ambient_temp + np.random.normal(0, 3)
            
            # DC Input (depends on solar availability)
            dc_voltage = 500 + 200 * solar_factor + np.random.normal(0, 20) if is_daytime else 0
            dc_current = 10 * solar_factor + np.random.normal(0, 0.5) if is_daytime else 0
            dc_power = dc_voltage * dc_current
            
            # Efficiency (decreases with higher temperatures)
            temp_effect = max(0, 0.05 * (inverter_temp - 45) / 20)
            actual_efficiency = max(0.5, min(0.98, base_efficiency - temp_effect + np.random.normal(0, 0.01)))
            
            # AC Output
            ac_power = dc_power * actual_efficiency
            ac_voltage = 230 + np.random.normal(0, 2) if ac_power > 0 else 0
            ac_current = (ac_power / ac_voltage) if ac_voltage > 0 else 0
            
            # Uptime - hours the inverter was operational in this period (1 hour max)
            uptime = 1.0 if ac_power > 100 else max(0, min(1, ac_power / 100))
            
            # Fault indicators
            # High temperature fault
            high_temp_fault = 1 if inverter_temp > 75 else 0
            
            # Grid stability fault
            grid_fault = 1 if (np.random.random() < 0.02 and is_daytime) else 0
            
            # Communication fault
            comm_fault = 1 if np.random.random() < 0.01 else 0
            
            # DC input fault (low voltage)
            dc_fault = 1 if (dc_voltage < 100 and dc_voltage > 0 and is_daytime) else 0
            
            # Total fault count
            fault_count = high_temp_fault + grid_fault + comm_fault + dc_fault
            
            # Create record
            record = {
                'timestamp': ts,
                'inverter_id': inv_id,
                'dc_voltage': round(dc_voltage, 2),
                'dc_current': round(dc_current, 2),
                'dc_power': round(dc_power, 2),
                'ac_voltage': round(ac_voltage, 2),
                'ac_current': round(ac_current, 2),
                'ac_power': round(ac_power, 2),
                'efficiency': round(actual_efficiency, 4),
                'inverter_temp': round(inverter_temp, 2),
                'ambient_temp': round(ambient_temp, 2),
                'uptime': round(uptime, 4),
                'high_temp_fault': high_temp_fault,
                'grid_fault': grid_fault, 
                'comm_fault': comm_fault,
                'dc_input_fault': dc_fault,
                'total_faults': fault_count
            }
            data.append(record)
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    return df

def save_data(df, csv_path="inverter_data.csv"):
    """Save generated data to CSV"""
    # Try to save to data directory if it exists
    try:
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try to find or create data directory
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), 'data')
        if not os.path.exists(data_dir):
            # Try one level up
            data_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'data')
            if not os.path.exists(data_dir):
                # Try to create a data directory in the current location
                data_dir = os.path.join(current_dir, 'data')
                os.makedirs(data_dir, exist_ok=True)
        
        # Set the full path for the CSV file
        full_path = os.path.join(data_dir, os.path.basename(csv_path))
        df.to_csv(full_path, index=False)
        print(f"Data saved to {full_path}")
    except Exception as e:
        # Fall back to saving in the current directory
        print(f"Could not save to data directory: {e}")
        print("Falling back to saving in the current directory")
        df.to_csv(csv_path, index=False)
        print(f"Data saved to {csv_path}")

def generate_statistical_summary(df):
    """Generate statistical summary of the dataset"""
    # Basic statistics
    basic_stats = df.describe()
    
    # Correlation matrix for numerical columns
    numeric_cols = df.select_dtypes(include=['number']).columns
    correlation = df[numeric_cols].corr()
    
    # Group by inverter_id for per-inverter statistics
    inverter_stats = df.groupby('inverter_id').agg({
        'dc_power': ['mean', 'std', 'max'],
        'ac_power': ['mean', 'std', 'max'],
        'efficiency': ['mean', 'min'],
        'inverter_temp': ['mean', 'max'],
        'total_faults': 'sum',
        'uptime': 'sum'
    })
    
    # Daily statistics
    df['date'] = df['timestamp'].dt.date
    daily_stats = df.groupby('date').agg({
        'ac_power': ['mean', 'max', 'sum'],
        'total_faults': 'sum',
        'uptime': 'sum'
    })
    
    return {
        'basic_stats': basic_stats,
        'correlation': correlation,
        'inverter_stats': inverter_stats,
        'daily_stats': daily_stats
    }

if __name__ == "__main__":
    # Generate data with 300 records per inverter for 5 inverters (1500 total records)
    df = generate_inverter_data(300, 5)
    
    # Save to CSV
    save_data(df)
    
    # Generate and display statistical summary
    stats = generate_statistical_summary(df)
    
    print("\n=== BASIC STATISTICS ===")
    print(stats['basic_stats'])
    
    print("\n=== CORRELATION MATRIX ===")
    print(stats['correlation'])
    
    print("\n=== INVERTER STATISTICS ===")
    print(stats['inverter_stats'])
    
    print("\n=== DAILY STATISTICS ===")
    print(stats['daily_stats'])