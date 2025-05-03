import os
import sys

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

# Load environment variables
load_dotenv()

# Database connection parameters from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def create_connection():
    """Create database connection"""
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
        print(f"Error connecting to PostgreSQL database: {e}")
        sys.exit(1)

def create_tables(conn):
    """Create necessary tables in the database"""
    cursor = conn.cursor()
    
    # Create inverters table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inverters (
        inverter_id VARCHAR(20) PRIMARY KEY,
        installation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        location VARCHAR(100),
        model VARCHAR(50),
        max_capacity FLOAT
    );
    """)
    
    # Create inverter_data table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inverter_data (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        inverter_id VARCHAR(20) NOT NULL REFERENCES inverters(inverter_id),
        dc_voltage FLOAT,
        dc_current FLOAT,
        dc_power FLOAT,
        ac_voltage FLOAT,
        ac_current FLOAT,
        ac_power FLOAT,
        efficiency FLOAT,
        inverter_temp FLOAT,
        ambient_temp FLOAT,
        uptime FLOAT,
        high_temp_fault SMALLINT,
        grid_fault SMALLINT,
        comm_fault SMALLINT,
        dc_input_fault SMALLINT,
        total_faults SMALLINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Create materialized view for daily statistics
    cursor.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS daily_inverter_stats AS
    SELECT 
        date(timestamp) AS date,
        inverter_id,
        AVG(dc_power) AS avg_dc_power,
        MAX(dc_power) AS max_dc_power,
        AVG(ac_power) AS avg_ac_power,
        MAX(ac_power) AS max_ac_power,
        SUM(ac_power) AS total_energy_kwh,
        AVG(efficiency) AS avg_efficiency,
        AVG(inverter_temp) AS avg_temp,
        MAX(inverter_temp) AS max_temp,
        SUM(uptime) AS total_uptime,
        SUM(total_faults) AS total_faults
    FROM 
        inverter_data
    GROUP BY 
        date(timestamp), inverter_id
    ORDER BY 
        date(timestamp), inverter_id;
    """)
    
    # Create index on timestamp and inverter_id
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_inverter_data_timestamp ON inverter_data(timestamp);
    CREATE INDEX IF NOT EXISTS idx_inverter_data_inverter_id ON inverter_data(inverter_id);
    """)
    
    conn.commit()
    cursor.close()
    print("Tables created successfully")

def insert_sample_inverters(conn):
    """Insert sample inverter records"""
    cursor = conn.cursor()
    
    # Sample inverters
    inverters = [
        ('INV-1a2b3c4d', '2024-01-15', 'Building A - Roof', 'SolarEdge SE7600H', 7.6),
        ('INV-2e3f4g5h', '2024-01-15', 'Building A - Roof', 'SolarEdge SE7600H', 7.6),
        ('INV-3i4j5k6l', '2024-01-20', 'Building B - Roof', 'Fronius Primo 8.2', 8.2),
        ('INV-4m5n6o7p', '2024-02-01', 'Building C - Ground', 'SMA Sunny Boy 7.0', 7.0),
        ('INV-5q6r7s8t', '2024-02-05', 'Building C - Ground', 'SMA Sunny Boy 7.0', 7.0)
    ]
    
    execute_values(
        cursor,
        """
        INSERT INTO inverters (inverter_id, installation_date, location, model, max_capacity)
        VALUES %s
        ON CONFLICT (inverter_id) DO NOTHING;
        """,
        inverters
    )
    
    conn.commit()
    cursor.close()
    print("Sample inverters inserted successfully")

def main():
    """Main function to set up the database"""
    conn = create_connection()
    create_tables(conn)
    insert_sample_inverters(conn)
    conn.close()
    print("Database setup completed")

if __name__ == "__main__":
    main()