-- SQL queries for advanced inverter data analysis

-- 1. Inverter efficiency analysis by temperature ranges
SELECT 
    inverter_id,
    width_bucket(inverter_temp, 30, 80, 10) as temp_bucket,
    (width_bucket(inverter_temp, 30, 80, 10) * 5) + 30 as temp_range_min,
    ((width_bucket(inverter_temp, 30, 80, 10) * 5) + 35) as temp_range_max,
    COUNT(*) as sample_count,
    ROUND(AVG(efficiency)::numeric, 4) as avg_efficiency,
    ROUND(STDDEV(efficiency)::numeric, 4) as stddev_efficiency
FROM 
    inverter_data
WHERE 
    dc_power > 0
GROUP BY 
    inverter_id, width_bucket(inverter_temp, 30, 80, 10)
ORDER BY 
    inverter_id, temp_bucket;

-- 2. Daily energy production with weather correlation
SELECT 
    date(id.timestamp) as date,
    id.inverter_id,
    ROUND(SUM(id.ac_power)::numeric, 2) as total_energy_kwh,
    ROUND(AVG(id.ambient_temp)::numeric, 1) as avg_ambient_temp,
    ROUND(MAX(id.ambient_temp)::numeric, 1) as max_ambient_temp,
    ROUND(MIN(id.ambient_temp)::numeric, 1) as min_ambient_temp,
    ROUND(AVG(id.efficiency)::numeric, 4) as avg_efficiency
FROM 
    inverter_data id
GROUP BY 
    date(id.timestamp), id.inverter_id
ORDER BY 
    date(id.timestamp), id.inverter_id;

-- 3. Hourly production pattern analysis
SELECT 
    EXTRACT(HOUR FROM timestamp) as hour_of_day,
    ROUND(AVG(dc_power)::numeric, 2) as avg_dc_power,
    ROUND(AVG(ac_power)::numeric, 2) as avg_ac_power,
    ROUND(AVG(efficiency)::numeric, 4) as avg_efficiency,
    ROUND(AVG(inverter_temp)::numeric, 1) as avg_inverter_temp,
    ROUND(AVG(ambient_temp)::numeric, 1) as avg_ambient_temp,
    COUNT(*) as sample_count
FROM 
    inverter_data
WHERE 
    dc_power > 0
GROUP BY 
    EXTRACT(HOUR FROM timestamp)
ORDER BY 
    hour_of_day;

-- 4. Fault analysis by hour and type
SELECT 
    EXTRACT(HOUR FROM timestamp) as hour_of_day,
    SUM(high_temp_fault) as high_temp_faults,
    SUM(grid_fault) as grid_faults,
    SUM(comm_fault) as comm_faults,
    SUM(dc_input_fault) as dc_input_faults,
    SUM(total_faults) as total_faults,
    COUNT(*) as total_records,
    ROUND((SUM(total_faults)::numeric / COUNT(*)::numeric), 4) as fault_rate
FROM 
    inverter_data
GROUP BY 
    EXTRACT(HOUR FROM timestamp)
ORDER BY 
    hour_of_day;

-- 5. Inverter comparison with stats ranking
WITH inverter_stats AS (
    SELECT 
        inverter_id,
        ROUND(AVG(efficiency)::numeric, 4) as avg_efficiency,
        ROUND(AVG(ac_power)::numeric, 2) as avg_ac_power,
        ROUND(SUM(ac_power)::numeric, 2) as total_energy,
        SUM(total_faults) as total_faults,
        ROUND(AVG(inverter_temp)::numeric, 1) as avg_temp,
        ROUND(MAX(inverter_temp)::numeric, 1) as max_temp,
        COUNT(*) as record_count
    FROM 
        inverter_data
    GROUP BY 
        inverter_id
)
SELECT 
    inverter_id,
    avg_efficiency,
    RANK() OVER (ORDER BY avg_efficiency DESC) as efficiency_rank,
    avg_ac_power,
    RANK() OVER (ORDER BY avg_ac_power DESC) as power_rank,
    total_energy,
    RANK() OVER (ORDER BY total_energy DESC) as energy_rank,
    total_faults,
    RANK() OVER (ORDER BY total_faults) as fault_rank,
    avg_temp,
    max_temp,
    RANK() OVER (ORDER BY max_temp) as temp_rank,
    -- Calculate overall ranking score (lower is better)
    (
        RANK() OVER (ORDER BY avg_efficiency DESC) + 
        RANK() OVER (ORDER BY avg_ac_power DESC) + 
        RANK() OVER (ORDER BY total_energy DESC) + 
        RANK() OVER (ORDER BY total_faults) + 
        RANK() OVER (ORDER BY max_temp)
    ) as overall_score
FROM 
    inverter_stats
ORDER BY 
    overall_score;

-- 6. Temperature vs Efficiency correlation by inverter
SELECT 
    inverter_id,
    ROUND(
        CORR(inverter_temp, efficiency)::numeric, 4
    ) as temp_efficiency_correlation,
    ROUND(
        REGR_SLOPE(efficiency, inverter_temp)::numeric, 6
    ) as efficiency_temp_slope,
    ROUND(
        REGR_INTERCEPT(efficiency, inverter_temp)::numeric, 4
    ) as efficiency_temp_intercept
FROM 
    inverter_data
WHERE 
    dc_power > 0
GROUP BY 
    inverter_id
ORDER BY 
    inverter_id;

-- 7. Efficiency degradation over time
WITH daily_efficiency AS (
    SELECT 
        date(timestamp) as date,
        inverter_id,
        AVG(efficiency) as avg_efficiency
    FROM 
        inverter_data
    WHERE 
        ac_power > 0
    GROUP BY 
        date(timestamp), inverter_id
)
SELECT 
    de.inverter_id,
    de.date,
    de.avg_efficiency,
    FIRST_VALUE(de.avg_efficiency) OVER (
        PARTITION BY de.inverter_id 
        ORDER BY de.date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) as initial_efficiency,
    ROUND(
        (de.avg_efficiency - FIRST_VALUE(de.avg_efficiency) OVER (
            PARTITION BY de.inverter_id 
            ORDER BY de.date
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ))::numeric * 100, 2
    ) as efficiency_change_pct
FROM 
    daily_efficiency de
ORDER BY 
    de.inverter_id, de.date;

-- 8. Anomaly detection using standard deviation
WITH inverter_metrics AS (
    SELECT 
        inverter_id,
        AVG(efficiency) as avg_efficiency,
        STDDEV(efficiency) as stddev_efficiency,
        AVG(inverter_temp) as avg_temp,
        STDDEV(inverter_temp) as stddev_temp,
        AVG(total_faults) as avg_faults,
        STDDEV(total_faults) as stddev_faults
    FROM 
        inverter_data
    GROUP BY 
        inverter_id
)
SELECT 
    id.timestamp,
    id.inverter_id,
    id.efficiency,
    im.avg_efficiency,
    im.stddev_efficiency,
    ROUND(
        (id.efficiency - im.avg_efficiency) / NULLIF(im.stddev_efficiency, 0)::numeric, 2
    ) as efficiency_zscore,
    id.inverter_temp,
    im.avg_temp,
    im.stddev_temp,
    ROUND(
        (id.inverter_temp - im.avg_temp) / NULLIF(im.stddev_temp, 0)::numeric, 2
    ) as temp_zscore,
    id.total_faults,
    im.avg_faults,
    im.stddev_faults,
    ROUND(
        (id.total_faults - im.avg_faults) / NULLIF(im.stddev_faults, 0)::numeric, 2
    ) as faults_zscore
FROM 
    inverter_data id
JOIN 
    inverter_metrics im ON id.inverter_id = im.inverter_id
WHERE 
    ABS((id.efficiency - im.avg_efficiency) / NULLIF(im.stddev_efficiency, 0)) > 2 OR
    ABS((id.inverter_temp - im.avg_temp) / NULLIF(im.stddev_temp, 0)) > 2 OR
    ABS((id.total_faults - im.avg_faults) / NULLIF(im.stddev_faults, 0)) > 2
ORDER BY 
    id.timestamp;

-- 9. Rolling average efficiency to detect trends
SELECT 
    timestamp,
    inverter_id,
    efficiency,
    ROUND(
        AVG(efficiency) OVER (
            PARTITION BY inverter_id 
            ORDER BY timestamp 
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        )::numeric, 4
    ) as efficiency_24h_avg,
    ROUND(
        AVG(efficiency) OVER (
            PARTITION BY inverter_id 
            ORDER BY timestamp 
            ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
        )::numeric, 4
    ) as efficiency_7d_avg
FROM 
    inverter_data
WHERE 
    ac_power > 0
ORDER BY 
    inverter_id, timestamp;

-- 10. Maintenance prediction score calculation
WITH recent_stats AS (
    SELECT 
        inverter_id,
        -- Fault rate (last 7 days)
        SUM(total_faults) as recent_faults,
        -- Temperature trend (slope)
        REGR_SLOPE(inverter_temp, EXTRACT(EPOCH FROM timestamp)) * 86400 as temp_daily_change,
        -- Efficiency trend (slope)
        REGR_SLOPE(efficiency, EXTRACT(EPOCH FROM timestamp)) * 86400 as efficiency_daily_change,
        -- Correlation stats
        CORR(inverter_temp, efficiency) as temp_efficiency_corr,
        -- Current vs historical efficiency
        AVG(efficiency) as recent_efficiency,
        -- Peak temperature
        MAX(inverter_temp) as peak_temp
    FROM 
        inverter_data
    WHERE 
        timestamp >= NOW() - INTERVAL '7 DAYS'
    GROUP BY 
        inverter_id
),
historical_stats AS (
    SELECT 
        inverter_id,
        AVG(efficiency) as historical_efficiency
    FROM 
        inverter_data
    WHERE 
        timestamp < NOW() - INTERVAL '7 DAYS'
    GROUP BY 
        inverter_id
)
SELECT 
    rs.inverter_id,
    rs.recent_faults,
    ROUND(rs.temp_daily_change::numeric, 4) as temp_daily_change,
    ROUND(rs.efficiency_daily_change::numeric, 6) as efficiency_daily_change,
    ROUND(rs.temp_efficiency_corr::numeric, 4) as temp_efficiency_corr,
    ROUND(rs.recent_efficiency::numeric, 4) as recent_efficiency,
    ROUND(hs.historical_efficiency::numeric, 4) as historical_efficiency,
    ROUND((rs.recent_efficiency - hs.historical_efficiency)::numeric * 100, 2) as efficiency_change_pct,
    ROUND(rs.peak_temp::numeric, 1) as peak_temp,
    -- Calculate maintenance score
    ROUND((
        CASE WHEN rs.recent_faults > 3 THEN rs.recent_faults * 2 ELSE 0 END +
        CASE WHEN rs.efficiency_daily_change < -0.001 THEN ABS(rs.efficiency_daily_change) * 10000 ELSE 0 END +
        CASE WHEN rs.temp_daily_change > 0.1 THEN rs.temp_daily_change * 10 ELSE 0 END +
        CASE WHEN rs.peak_temp > 70 THEN (rs.peak_temp - 70) * 0.5 ELSE 0 END +
        CASE WHEN (rs.recent_efficiency - hs.historical_efficiency) < -0.02 THEN ABS(rs.recent_efficiency - hs.historical_efficiency) * 100 ELSE 0 END
    )::numeric, 2) as maintenance_score,
    -- Determine status based on maintenance score
    CASE
        WHEN (
            CASE WHEN rs.recent_faults > 3 THEN rs.recent_faults * 2 ELSE 0 END +
            CASE WHEN rs.efficiency_daily_change < -0.001 THEN ABS(rs.efficiency_daily_change) * 10000 ELSE 0 END +
            CASE WHEN rs.temp_daily_change > 0.1 THEN rs.temp_daily_change * 10 ELSE 0 END +
            CASE WHEN rs.peak_temp > 70 THEN (rs.peak_temp - 70) * 0.5 ELSE 0 END +
            CASE WHEN (rs.recent_efficiency - hs.historical_efficiency) < -0.02 THEN ABS(rs.recent_efficiency - hs.historical_efficiency) * 100 ELSE 0 END
        ) > 10 THEN 'Urgent Maintenance Required'
        WHEN (
            CASE WHEN rs.recent_faults > 3 THEN rs.recent_faults * 2 ELSE 0 END +
            CASE WHEN rs.efficiency_daily_change < -0.001 THEN ABS(rs.efficiency_daily_change) * 10000 ELSE 0 END +
            CASE WHEN rs.temp_daily_change > 0.1 THEN rs.temp_daily_change * 10 ELSE 0 END +
            CASE WHEN rs.peak_temp > 70 THEN (rs.peak_temp - 70) * 0.5 ELSE 0 END +
            CASE WHEN (rs.recent_efficiency - hs.historical_efficiency) < -0.02 THEN ABS(rs.recent_efficiency - hs.historical_efficiency) * 100 ELSE 0 END
        ) > 5 THEN 'Maintenance Recommended'
        WHEN (
            CASE WHEN rs.recent_faults > 3 THEN rs.recent_faults * 2 ELSE 0 END +
            CASE WHEN rs.efficiency_daily_change < -0.001 THEN ABS(rs.efficiency_daily_change) * 10000 ELSE 0 END +
            CASE WHEN rs.temp_daily_change > 0.1 THEN rs.temp_daily_change * 10 ELSE 0 END +
            CASE WHEN rs.peak_temp > 70 THEN (rs.peak_temp - 70) * 0.5 ELSE 0 END +
            CASE WHEN (rs.recent_efficiency - hs.historical_efficiency) < -0.02 THEN ABS(rs.recent_efficiency - hs.historical_efficiency) * 100 ELSE 0 END
        ) > 2 THEN 'Monitor Closely'
        ELSE 'Healthy'
    END as status
FROM 
    recent_stats rs
LEFT JOIN 
    historical_stats hs ON rs.inverter_id = hs.inverter_id
ORDER BY 
    maintenance_score DESC;