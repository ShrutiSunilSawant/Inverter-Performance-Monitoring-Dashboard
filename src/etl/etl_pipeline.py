import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("etl_pipeline.log"),
        logging.StreamHandler()
    ]
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

def extract_data(file_path):
    """
    Extract data from CSV file
    
    Parameters:
    - file_path: Path to CSV file
    
    Returns:
    - DataFrame containing data
    """
    try:
        logger.info(f"Extracting data from {file_path}")
        df = pd.read_csv(file_path)
        logger.info(f"Successfully extracted {len(df)} records from {file_path}")
        return df
    except Exception as e:
        logger.error(f"Error extracting data: {e}")
        raise

def transform_data(df):
    """
    Transform and clean the data
    
    Parameters:
    - df: DataFrame containing raw data
    
    Returns:
    - DataFrame containing transformed data
    """
    try:
        logger.info("Starting data transformation")
        
        # Convert timestamp to datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Check for missing values
        missing_values = df.isnull().sum()
        if missing_values.sum() > 0:
            logger.warning(f"Found missing values: {missing_values[missing_values > 0]}")
            
            # Fill missing numerical values with column means
            numerical_cols = df.select_dtypes(include=['number']).columns
            for col in numerical_cols:
                if df[col].isnull().sum() > 0:
                    median_val = df[col].median()
                    df[col].fillna(median_val, inplace=True)
                    logger.info(f"Filled missing values in {col} with median: {median_val}")
        
        # Data validation and cleaning
        
        # 1. Ensure power values are non-negative
        for col in ['dc_power', 'ac_power']:
            if col in df.columns:
                invalid_power = df[col] < 0
                if invalid_power.any():
                    logger.warning(f"Found {invalid_power.sum()} negative values in {col}, replacing with 0")
                    df.loc[invalid_power, col] = 0
        
        # 2. Ensure efficiency is between 0 and 1
        if 'efficiency' in df.columns:
            invalid_eff = (df['efficiency'] < 0) | (df['efficiency'] > 1)
            if invalid_eff.any():
                logger.warning(f"Found {invalid_eff.sum()} efficiency values outside [0,1], clipping")
                df.loc[invalid_eff, 'efficiency'] = df.loc[invalid_eff, 'efficiency'].clip(0, 1)
        
        # 3. Validate fault indicators (should be 0 or 1)
        fault_cols = ['high_temp_fault', 'grid_fault', 'comm_fault', 'dc_input_fault']
        for col in fault_cols:
            if col in df.columns:
                invalid_fault = ~df[col].isin([0, 1])
                if invalid_fault.any():
                    logger.warning(f"Found {invalid_fault.sum()} invalid values in {col}, converting to binary")
                    df.loc[invalid_fault, col] = (df.loc[invalid_fault, col] > 0).astype(int)
        
        # 4. Validate uptime (should be between 0 and 1)
        if 'uptime' in df.columns:
            invalid_uptime = (df['uptime'] < 0) | (df['uptime'] > 1)
            if invalid_uptime.any():
                logger.warning(f"Found {invalid_uptime.sum()} uptime values outside [0,1], clipping")
                df.loc[invalid_uptime, 'uptime'] = df.loc[invalid_uptime, 'uptime'].clip(0, 1)
        
        # 5. Calculate total_faults if missing (sum of individual fault indicators)
        if all(col in df.columns for col in fault_cols) and 'total_faults' in df.columns:
            calculated_faults = df[fault_cols].sum(axis=1)
            mismatch = df['total_faults'] != calculated_faults
            if mismatch.any():
                logger.warning(f"Found {mismatch.sum()} mismatches in total_faults, recalculating")
                df['total_faults'] = calculated_faults
        
        # 6. Validate inverter_id (ensure they exist in the database)
        logger.info("Validated and transformed data successfully")
        return df
    
    except Exception as e:
        logger.error(f"Error transforming data: {e}")
        raise

def load_data(df, conn):
    """
    Load data into the database
    
    Parameters:
    - df: DataFrame containing data to load
    - conn: Database connection
    
    Returns:
    - Number of records inserted
    """
    try:
        logger.info("Starting data loading")
        cursor = conn.cursor()
        
        # Check if inverter_ids exist in inverters table, add any missing ones
        inverter_ids = df['inverter_id'].unique()
        logger.info(f"Found {len(inverter_ids)} unique inverter IDs")
        
        # Check which inverter_ids already exist
        cursor.execute(
            "SELECT inverter_id FROM inverters WHERE inverter_id IN %s",
            (tuple(inverter_ids),)
        )
        existing_ids = [row[0] for row in cursor.fetchall()]
        
        # Add missing inverter_ids
        missing_ids = [id for id in inverter_ids if id not in existing_ids]
        if missing_ids:
            logger.warning(f"Found {len(missing_ids)} inverter IDs not in database: {missing_ids}")
            
            # Insert placeholder records for missing inverters
            missing_inverters = [(id, datetime.now(), 'Unknown', 'Unknown', 0.0) for id in missing_ids]
            execute_values(
                cursor,
                """
                INSERT INTO inverters (inverter_id, installation_date, location, model, max_capacity)
                VALUES %s
                """,
                missing_inverters
            )
        
        # Prepare data for insertion
        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                row['timestamp'],
                row['inverter_id'],
                row['dc_voltage'],
                row['dc_current'],
                row['dc_power'],
                row['ac_voltage'],
                row['ac_current'],
                row['ac_power'],
                row['efficiency'],
                row['inverter_temp'],
                row['ambient_temp'],
                row['uptime'],
                row['high_temp_fault'],
                row['grid_fault'],
                row['comm_fault'],
                row['dc_input_fault'],
                row['total_faults']
            ))
        
        # Insert data using execute_values for better performance
        execute_values(
            cursor,
            """
            INSERT INTO inverter_data 
            (timestamp, inverter_id, dc_voltage, dc_current, dc_power, 
             ac_voltage, ac_current, ac_power, efficiency, inverter_temp, 
             ambient_temp, uptime, high_temp_fault, grid_fault, comm_fault, 
             dc_input_fault, total_faults)
            VALUES %s
            """,
            data_to_insert
        )
        
        # Refresh materialized view
        cursor.execute("REFRESH MATERIALIZED VIEW daily_inverter_stats")
        
        # Commit and close cursor
        conn.commit()
        cursor.close()
        
        logger.info(f"Successfully loaded {len(data_to_insert)} records into database")
        return len(data_to_insert)
    
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        conn.rollback()
        raise

def run_etl_pipeline(file_path):
    """
    Run the complete ETL pipeline
    
    Parameters:
    - file_path: Path to CSV file
    
    Returns:
    - Status message
    """
    try:
        logger.info("Starting ETL pipeline")
        
        # Check if file exists
        if not os.path.exists(file_path):
            # Try to find file in data directory
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data')
            alternative_path = os.path.join(data_dir, os.path.basename(file_path))
            
            if os.path.exists(alternative_path):
                logger.info(f"File not found at {file_path}, using {alternative_path} instead")
                file_path = alternative_path
            else:
                logger.error(f"File not found at {file_path} or in data directory")
                raise FileNotFoundError(f"Could not find data file at {file_path} or in data directory")
        
        # Extract
        df = extract_data(file_path)
        
        # Transform
        transformed_df = transform_data(df)
        
        # Load
        conn = create_db_connection()
        records_inserted = load_data(transformed_df, conn)
        conn.close()
        
        logger.info(f"ETL pipeline completed successfully. {records_inserted} records processed.")
        return f"ETL pipeline completed successfully. {records_inserted} records processed."
    
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}")
        raise

if __name__ == "__main__":
    try:
        # Define possible file paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        
        # Try these paths in order
        potential_paths = [
            "inverter_data.csv",  # Current directory
            os.path.join("data", "inverter_data.csv"),  # data/ subdirectory
            os.path.join(project_root, "data", "inverter_data.csv"),  # project's data directory
            os.path.join(os.path.dirname(current_dir), "data_generation", "inverter_data.csv")  # data_generation directory
        ]
        
        # Find the first path that exists
        file_path = None
        for path in potential_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        if file_path is None:
            # If file isn't found anywhere, try to generate it first
            try:
                logger.info("CSV file not found. Attempting to generate data first...")
                data_gen_script = os.path.join(os.path.dirname(current_dir), "data_generation", "synthetic_data_generator.py")
                
                if os.path.exists(data_gen_script):
                    import subprocess
                    subprocess.run([sys.executable, data_gen_script], check=True)
                    logger.info("Data generated successfully.")
                    
                    # Check if file now exists
                    for path in potential_paths:
                        if os.path.exists(path):
                            file_path = path
                            break
                else:
                    logger.warning(f"Data generator script not found at {data_gen_script}")
            except Exception as e:
                logger.warning(f"Failed to generate data: {e}")
        
        if file_path is None:
            logger.error("Could not find or generate inverter_data.csv. Please ensure the file exists.")
            print("Error: Could not find or generate inverter_data.csv. Please run the synthetic_data_generator.py script first.")
            sys.exit(1)
        
        # Run ETL pipeline with the found file
        logger.info(f"Using data file: {file_path}")
        result = run_etl_pipeline(file_path)
        print(result)
    except Exception as e:
        print(f"Error running ETL pipeline: {e}")