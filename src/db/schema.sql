-- Database: inverter_monitoring

-- Create database (run this as superuser)
CREATE DATABASE inverter_monitoring
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TEMPLATE = template0;

-- Connect to the database
\c inverter_monitoring

-- Create inverters table
CREATE TABLE IF NOT EXISTS inverters (
    inverter_id VARCHAR(20) PRIMARY KEY,
    installation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    location VARCHAR(100),
    model VARCHAR(50),
    max_capacity FLOAT
);

-- Create inverter_data table
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

-- Create materialized view for daily statistics
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

-- Create index on timestamp and inverter_id
CREATE INDEX idx_inverter_data_timestamp ON inverter_data(timestamp);
CREATE INDEX idx_inverter_data_inverter_id ON inverter_data(inverter_id);
CREATE INDEX idx_inverter_data_combined ON inverter_data(inverter_id, timestamp);

-- Create weekly statistics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS weekly_inverter_stats AS
SELECT 
    date_trunc('week', timestamp) AS week_start,
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
    date_trunc('week', timestamp), inverter_id
ORDER BY 
    date_trunc('week', timestamp), inverter_id;

-- Create a table to store maintenance predictions
CREATE TABLE IF NOT EXISTS maintenance_predictions (
    id SERIAL PRIMARY KEY,
    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    inverter_id VARCHAR(20) NOT NULL REFERENCES inverters(inverter_id),
    maintenance_score FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL,
    fault_rate FLOAT,
    efficiency_trend FLOAT,
    temperature_trend FLOAT,
    recommended_action TEXT,
    expected_maintenance_date DATE
);

-- Create view for efficiency vs temperature analysis
CREATE VIEW efficiency_temp_analysis AS
SELECT 
    inverter_id,
    width_bucket(inverter_temp, 30, 80, 10) as temp_bucket,
    (width_bucket(inverter_temp, 30, 80, 10) * 5) + 30 as temp_range_start,
    ((width_bucket(inverter_temp, 30, 80, 10) * 5) + 35) as temp_range_end,
    COUNT(*) as sample_count,
    AVG(efficiency) as avg_efficiency,
    STDDEV(efficiency) as stddev_efficiency
FROM 
    inverter_data
WHERE 
    dc_power > 0
GROUP BY 
    inverter_id, width_bucket(inverter_temp, 30, 80, 10)
ORDER BY 
    inverter_id, temp_bucket;

-- Create view for fault analysis
CREATE VIEW fault_analysis AS
SELECT
    inverter_id,
    date(timestamp) as date,
    extract(hour from timestamp) as hour,
    SUM(high_temp_fault) as high_temp_faults,
    SUM(grid_fault) as grid_faults,
    SUM(comm_fault) as comm_faults,
    SUM(dc_input_fault) as dc_input_faults,
    SUM(total_faults) as total_faults
FROM
    inverter_data
GROUP BY
    inverter_id, date(timestamp), extract(hour from timestamp)
ORDER BY
    inverter_id, date(timestamp), extract(hour from timestamp);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO your_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;