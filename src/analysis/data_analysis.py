import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg2
import seaborn as sns
from dotenv import load_dotenv
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.seasonal import seasonal_decompose

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def create_db_connection():
    """Create a database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL database: {e}")
        raise

def fetch_inverter_data(days=30):
    """
    Fetch inverter data from the database for the specified number of days
    
    Parameters:
    - days: Number of days of data to fetch
    
    Returns:
    - DataFrame containing data
    """
    try:
        conn = create_db_connection()
        query = f"""
        SELECT *
        FROM inverter_data
        WHERE timestamp >= NOW() - INTERVAL '{days} DAYS'
        ORDER BY timestamp
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise

def fetch_daily_stats(days=30):
    """
    Fetch daily inverter statistics from the materialized view
    
    Parameters:
    - days: Number of days of data to fetch
    
    Returns:
    - DataFrame containing daily statistics
    """
    try:
        conn = create_db_connection()
        query = f"""
        SELECT *
        FROM daily_inverter_stats
        WHERE date >= CURRENT_DATE - INTERVAL '{days} DAYS'
        ORDER BY date, inverter_id
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error fetching daily stats: {e}")
        raise

def analyze_inverter_efficiency():
    """
    Analyze inverter efficiency correlation with temperature
    
    Returns:
    - Dictionary containing analysis results
    """
    df = fetch_inverter_data()
    
    # Calculate correlation between temperature and efficiency
    efficiency_temp_corr = df[['inverter_temp', 'efficiency']].corr().iloc[0, 1]
    
    # Group by temperature ranges and calculate average efficiency
    df['temp_range'] = pd.cut(df['inverter_temp'], bins=10)
    temp_efficiency = df.groupby('temp_range')['efficiency'].mean().reset_index()
    
    # Get overall efficiency stats
    efficiency_stats = df.groupby('inverter_id')['efficiency'].agg(['mean', 'min', 'max', 'std']).reset_index()
    
    return {
        'efficiency_temp_correlation': efficiency_temp_corr,
        'temp_efficiency_relationship': temp_efficiency.to_dict(),
        'efficiency_stats': efficiency_stats.to_dict()
    }

def analyze_fault_patterns():
    """
    Analyze fault patterns and correlations
    
    Returns:
    - Dictionary containing analysis results
    """
    df = fetch_inverter_data()
    
    # Fault frequency by inverter
    fault_by_inverter = df.groupby('inverter_id')['total_faults'].sum().reset_index()
    
    # Calculate correlation between temperature and fault occurrence
    temp_fault_corr = df[['inverter_temp', 'total_faults']].corr().iloc[0, 1]
    
    # Analyze temporal patterns in faults
    df['hour'] = df['timestamp'].dt.hour
    fault_by_hour = df.groupby('hour')['total_faults'].sum().reset_index()
    
    # Fault type distribution
    fault_types = df[['high_temp_fault', 'grid_fault', 'comm_fault', 'dc_input_fault']].sum().reset_index()
    fault_types.columns = ['fault_type', 'count']
    
    return {
        'fault_by_inverter': fault_by_inverter.to_dict(),
        'temp_fault_correlation': temp_fault_corr,
        'fault_by_hour': fault_by_hour.to_dict(),
        'fault_types': fault_types.to_dict()
    }

def analyze_power_generation():
    """
    Analyze power generation patterns
    
    Returns:
    - Dictionary containing analysis results
    """
    # Get daily stats
    daily_df = fetch_daily_stats()
    
    # Total energy by day
    energy_by_day = daily_df.groupby('date')['total_energy_kwh'].sum().reset_index()
    
    # Calculate daily variations (percentage change)
    energy_by_day['pct_change'] = energy_by_day['total_energy_kwh'].pct_change() * 100
    
    # Power generation by inverter
    power_by_inverter = daily_df.groupby('inverter_id')['total_energy_kwh'].sum().reset_index()
    
    # Efficiency analysis by inverter
    efficiency_by_inverter = daily_df.groupby('inverter_id')['avg_efficiency'].mean().reset_index()
    
    return {
        'energy_by_day': energy_by_day.to_dict(),
        'power_by_inverter': power_by_inverter.to_dict(),
        'efficiency_by_inverter': efficiency_by_inverter.to_dict()
    }

def detect_anomalies():
    """
    Detect anomalies in inverter performance
    
    Returns:
    - Dictionary containing anomaly detection results
    """
    df = fetch_inverter_data()
    
    anomalies = {}
    
    # Detect efficiency anomalies using Z-scores
    for inverter_id in df['inverter_id'].unique():
        inverter_df = df[df['inverter_id'] == inverter_id]
        
        # Efficiency anomalies
        inverter_df['efficiency_zscore'] = stats.zscore(inverter_df['efficiency'])
        efficiency_anomalies = inverter_df[abs(inverter_df['efficiency_zscore']) > 3]
        
        if not efficiency_anomalies.empty:
            anomalies[f"{inverter_id}_efficiency"] = efficiency_anomalies[['timestamp', 'efficiency']].to_dict()
        
        # Temperature anomalies
        inverter_df['temp_zscore'] = stats.zscore(inverter_df['inverter_temp'])
        temp_anomalies = inverter_df[abs(inverter_df['temp_zscore']) > 3]
        
        if not temp_anomalies.empty:
            anomalies[f"{inverter_id}_temperature"] = temp_anomalies[['timestamp', 'inverter_temp']].to_dict()
    
    return anomalies

def predict_maintenance_needs():
    """
    Predict potential maintenance needs based on performance patterns
    
    Returns:
    - Dictionary containing maintenance prediction results
    """
    df = fetch_inverter_data()
    
    maintenance_predictions = {}
    
    for inverter_id in df['inverter_id'].unique():
        inverter_df = df[df['inverter_id'] == inverter_id]
        
        # Calculate recent fault rate
        recent_data = inverter_df.sort_values('timestamp').tail(24)  # Last 24 hours
        recent_fault_rate = recent_data['total_faults'].sum()
        
        # Check for declining efficiency trend
        efficiency_trend = np.polyfit(range(len(recent_data)), recent_data['efficiency'], 1)[0]
        
        # Check for increasing temperature trend
        temp_trend = np.polyfit(range(len(recent_data)), recent_data['inverter_temp'], 1)[0]
        
        # Calculate maintenance score based on factors
        maintenance_score = 0
        
        if recent_fault_rate > 3:
            maintenance_score += recent_fault_rate * 2
        
        if efficiency_trend < -0.01:  # Declining efficiency
            maintenance_score += abs(efficiency_trend) * 100
        
        if temp_trend > 0.1:  # Increasing temperature
            maintenance_score += temp_trend * 10
        
        # Overall health status
        if maintenance_score > 10:
            status = "Urgent Maintenance Required"
        elif maintenance_score > 5:
            status = "Maintenance Recommended"
        elif maintenance_score > 2:
            status = "Monitor Closely"
        else:
            status = "Healthy"
        
        maintenance_predictions[inverter_id] = {
            'maintenance_score': maintenance_score,
            'status': status,
            'fault_rate': recent_fault_rate,
            'efficiency_trend': efficiency_trend,
            'temperature_trend': temp_trend
        }
    
    return maintenance_predictions

def run_complete_analysis():
    """
    Run all analysis functions and return comprehensive results
    
    Returns:
    - Dictionary containing all analysis results
    """
    try:
        logger.info("Starting comprehensive inverter data analysis")
        
        results = {
            'efficiency_analysis': analyze_inverter_efficiency(),
            'fault_analysis': analyze_fault_patterns(),
            'power_analysis': analyze_power_generation(),
            'anomaly_detection': detect_anomalies(),
            'maintenance_prediction': predict_maintenance_needs()
        }
        
        logger.info("Analysis completed successfully")
        return results
    
    except Exception as e:
        logger.error(f"Error in analysis: {e}")
        raise

def export_analysis_results(results, output_dir="./analysis_results"):
    """
    Export analysis results to CSV files
    
    Parameters:
    - results: Dictionary containing analysis results
    - output_dir: Directory to save files in
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Export efficiency analysis
        efficiency_stats = pd.DataFrame(results['efficiency_analysis']['efficiency_stats'])
        efficiency_stats.to_csv(f"{output_dir}/efficiency_stats.csv", index=False)
        
        # Export fault analysis
        fault_by_inverter = pd.DataFrame(results['fault_analysis']['fault_by_inverter'])
        fault_by_inverter.to_csv(f"{output_dir}/fault_by_inverter.csv", index=False)
        
        fault_by_hour = pd.DataFrame(results['fault_analysis']['fault_by_hour'])
        fault_by_hour.to_csv(f"{output_dir}/fault_by_hour.csv", index=False)
        
        # Export power generation analysis
        energy_by_day = pd.DataFrame(results['power_analysis']['energy_by_day'])
        energy_by_day.to_csv(f"{output_dir}/energy_by_day.csv", index=False)
        
        # Export maintenance predictions
        maintenance = pd.DataFrame(results['maintenance_prediction']).T
        maintenance.reset_index(inplace=True)
        maintenance.rename(columns={'index': 'inverter_id'}, inplace=True)
        maintenance.to_csv(f"{output_dir}/maintenance_predictions.csv", index=False)
        
        logger.info(f"Analysis results exported to {output_dir}")
    
    except Exception as e:
        logger.error(f"Error exporting analysis results: {e}")
        raise

if __name__ == "__main__":
    try:
        # Run complete analysis
        results = run_complete_analysis()
        
        # Export results
        export_analysis_results(results)
        
        print("Analysis completed and results exported successfully.")
    
    except Exception as e:
        print(f"Error running analysis: {e}")