import json
import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "inverter_monitoring")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your_secure_password")

app = Flask(__name__)

def get_db_connection():
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

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/inverter-comparison')
def inverter_comparison():
    """Render the inverter comparison page"""
    return render_template('inverter_comparison.html')

@app.route('/fault-analysis')
def fault_analysis():
    """Render the fault analysis page"""
    return render_template('fault_analysis.html')

@app.route('/maintenance')
def maintenance():
    """Render the maintenance page"""
    return render_template('maintenance.html')

@app.route('/api/kpi-summary')
def kpi_summary():
    """Get KPI summary data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get total energy
        cursor.execute("""
            SELECT SUM(total_energy_kwh) as total_energy
            FROM daily_inverter_stats
            WHERE date >= CURRENT_DATE - INTERVAL '30 DAYS'
        """)
        energy_result = cursor.fetchone()
        
        # Get average efficiency
        cursor.execute("""
            SELECT AVG(avg_efficiency) as avg_efficiency
            FROM daily_inverter_stats
            WHERE date >= CURRENT_DATE - INTERVAL '30 DAYS'
        """)
        efficiency_result = cursor.fetchone()
        
        # Get total faults in last 7 days
        cursor.execute("""
            SELECT SUM(total_faults) as total_faults
            FROM daily_inverter_stats
            WHERE date >= CURRENT_DATE - INTERVAL '7 DAYS'
        """)
        faults_result = cursor.fetchone()
        
        # Get inverters requiring maintenance
        cursor.execute("""
            WITH maintenance_scoring AS (
                SELECT 
                    inverter_id,
                    SUM(total_faults) as recent_faults,
                    CASE
                        WHEN SUM(total_faults) > 5 OR MAX(max_temp) > 70 THEN 'Urgent'
                        WHEN SUM(total_faults) > 2 OR MAX(max_temp) > 65 THEN 'Monitor'
                        ELSE 'Healthy'
                    END as status
                FROM daily_inverter_stats
                WHERE date >= CURRENT_DATE - INTERVAL '7 DAYS'
                GROUP BY inverter_id
            )
            SELECT COUNT(*) as maintenance_count
            FROM maintenance_scoring
            WHERE status = 'Urgent'
        """)
        maintenance_result = cursor.fetchone()
        
        # Get month-over-month changes
        cursor.execute("""
            WITH current_month AS (
                SELECT 
                    SUM(total_energy_kwh) as energy,
                    AVG(avg_efficiency) as efficiency,
                    SUM(total_faults) as faults
                FROM daily_inverter_stats
                WHERE date >= CURRENT_DATE - INTERVAL '30 DAYS'
            ),
            previous_month AS (
                SELECT 
                    SUM(total_energy_kwh) as energy,
                    AVG(avg_efficiency) as efficiency,
                    SUM(total_faults) as faults
                FROM daily_inverter_stats
                WHERE date >= CURRENT_DATE - INTERVAL '60 DAYS' AND
                      date < CURRENT_DATE - INTERVAL '30 DAYS'
            )
            SELECT 
                ((cm.energy - pm.energy) / NULLIF(pm.energy, 0)) * 100 as energy_change,
                ((cm.efficiency - pm.efficiency) / NULLIF(pm.efficiency, 0)) * 100 as efficiency_change,
                (cm.faults - pm.faults) as faults_change
            FROM current_month cm, previous_month pm
        """)
        change_result = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'total_energy': round(float(energy_result['total_energy']), 2) if energy_result['total_energy'] else 0,
            'avg_efficiency': round(float(efficiency_result['avg_efficiency']) * 100, 1) if efficiency_result['avg_efficiency'] else 0,
            'total_faults': int(faults_result['total_faults']) if faults_result['total_faults'] else 0,
            'maintenance_count': int(maintenance_result['maintenance_count']) if maintenance_result['maintenance_count'] else 0,
            'energy_change': round(float(change_result['energy_change']), 1) if change_result['energy_change'] else 0,
            'efficiency_change': round(float(change_result['efficiency_change']), 1) if change_result['efficiency_change'] else 0,
            'faults_change': int(change_result['faults_change']) if change_result['faults_change'] else 0
        })
    
    except Exception as e:
        logger.error(f"Error getting KPI summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/energy-generation')
def energy_generation():
    """Get energy generation data for trend chart"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        days = request.args.get('days', default=30, type=int)
        
        cursor.execute("""
            SELECT 
                date,
                inverter_id,
                total_energy_kwh
            FROM daily_inverter_stats
            WHERE date >= CURRENT_DATE - INTERVAL '%s DAYS'
            ORDER BY date, inverter_id
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            data.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'inverter_id': row['inverter_id'],
                'energy': float(row['total_energy_kwh'])
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting energy generation data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/efficiency-temp')
def efficiency_temp():
    """Get efficiency vs temperature data for scatter plot"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        days = request.args.get('days', default=30, type=int)
        
        cursor.execute("""
            SELECT 
                timestamp,
                inverter_id,
                efficiency,
                inverter_temp
            FROM inverter_data
            WHERE timestamp >= CURRENT_DATE - INTERVAL '%s DAYS'
                AND dc_power > 0
            ORDER BY timestamp
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            data.append({
                'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'inverter_id': row['inverter_id'],
                'efficiency': float(row['efficiency']),
                'temperature': float(row['inverter_temp'])
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting efficiency vs temperature data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fault-distribution')
def fault_distribution():
    """Get fault distribution data for donut chart"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        days = request.args.get('days', default=30, type=int)
        
        cursor.execute("""
            SELECT 
                SUM(high_temp_fault) as high_temp_faults,
                SUM(grid_fault) as grid_faults,
                SUM(comm_fault) as comm_faults,
                SUM(dc_input_fault) as dc_input_faults
            FROM inverter_data
            WHERE timestamp >= CURRENT_DATE - INTERVAL '%s DAYS'
        """, (days,))
        
        result = cursor.fetchone()
        conn.close()
        
        # Format data for chart
        data = [
            {'type': 'High Temperature', 'count': int(result['high_temp_faults'])},
            {'type': 'Grid Stability', 'count': int(result['grid_faults'])},
            {'type': 'Communication', 'count': int(result['comm_faults'])},
            {'type': 'DC Input', 'count': int(result['dc_input_faults'])}
        ]
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting fault distribution data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inverter-status')
def inverter_status():
    """Get inverter status data for gauge charts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            WITH maintenance_stats AS (
                SELECT 
                    inverter_id,
                    SUM(total_faults) as recent_faults,
                    AVG(avg_efficiency) as avg_efficiency,
                    MAX(max_temp) as max_temp,
                    CASE
                        WHEN SUM(total_faults) > 5 OR MAX(max_temp) > 70 THEN 'Urgent'
                        WHEN SUM(total_faults) > 2 OR MAX(max_temp) > 65 THEN 'Monitor'
                        ELSE 'Healthy'
                    END as status,
                    CASE
                        WHEN SUM(total_faults) > 5 OR MAX(max_temp) > 70 THEN 10
                        WHEN SUM(total_faults) > 2 OR MAX(max_temp) > 65 THEN 5
                        ELSE 1
                    END as maintenance_score
                FROM daily_inverter_stats
                WHERE date >= CURRENT_DATE - INTERVAL '7 DAYS'
                GROUP BY inverter_id
            )
            SELECT *
            FROM maintenance_stats
            ORDER BY maintenance_score DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            data.append({
                'inverter_id': row['inverter_id'],
                'status': row['status'],
                'maintenance_score': int(row['maintenance_score']),
                'recent_faults': int(row['recent_faults']),
                'avg_efficiency': float(row['avg_efficiency']),
                'max_temp': float(row['max_temp'])
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting inverter status data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inverter-comparison')
def get_inverter_comparison():
    """Get inverter comparison data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        days = request.args.get('days', default=30, type=int)
        
        cursor.execute("""
            SELECT 
                inverter_id,
                AVG(avg_efficiency) as efficiency,
                SUM(total_energy_kwh) as total_energy,
                SUM(total_faults) as total_faults,
                SUM(total_uptime) as uptime
            FROM daily_inverter_stats
            WHERE date >= CURRENT_DATE - INTERVAL '%s DAYS'
            GROUP BY inverter_id
            ORDER BY inverter_id
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            data.append({
                'inverter_id': row['inverter_id'],
                'efficiency': float(row['efficiency']),
                'total_energy': float(row['total_energy']),
                'total_faults': int(row['total_faults']),
                'uptime': float(row['uptime'])
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting inverter comparison data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fault-timeline')
def fault_timeline():
    """Get fault timeline data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        days = request.args.get('days', default=30, type=int)
        
        cursor.execute("""
            SELECT 
                date(timestamp) as date,
                SUM(high_temp_fault) as high_temp_faults,
                SUM(grid_fault) as grid_faults,
                SUM(comm_fault) as comm_faults,
                SUM(dc_input_fault) as dc_input_faults,
                SUM(total_faults) as total_faults
            FROM inverter_data
            WHERE timestamp >= CURRENT_DATE - INTERVAL '%s DAYS'
            GROUP BY date(timestamp)
            ORDER BY date(timestamp)
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            data.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'high_temp_faults': int(row['high_temp_faults']),
                'grid_faults': int(row['grid_faults']),
                'comm_faults': int(row['comm_faults']),
                'dc_input_faults': int(row['dc_input_faults']),
                'total_faults': int(row['total_faults'])
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting fault timeline data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/fault-heatmap')
def fault_heatmap():
    """Get fault heatmap data by hour and day of week"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        days = request.args.get('days', default=30, type=int)
        
        cursor.execute("""
            SELECT 
                EXTRACT(DOW FROM timestamp) as day_of_week,
                EXTRACT(HOUR FROM timestamp) as hour_of_day,
                COUNT(*) as record_count,
                SUM(total_faults) as fault_count
            FROM inverter_data
            WHERE timestamp >= CURRENT_DATE - INTERVAL '%s DAYS'
            GROUP BY 
                EXTRACT(DOW FROM timestamp),
                EXTRACT(HOUR FROM timestamp)
            ORDER BY 
                EXTRACT(DOW FROM timestamp),
                EXTRACT(HOUR FROM timestamp)
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            data.append({
                'day_of_week': int(row['day_of_week']),
                'hour_of_day': int(row['hour_of_day']),
                'fault_count': int(row['fault_count']),
                'record_count': int(row['record_count'])
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting fault heatmap data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/maintenance-prediction')
def maintenance_prediction():
    """Get maintenance prediction data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            WITH recent_stats AS (
                SELECT 
                    inverter_id,
                    SUM(total_faults) as recent_faults,
                    AVG(avg_efficiency) as recent_efficiency,
                    MAX(max_temp) as max_temp
                FROM daily_inverter_stats
                WHERE date >= CURRENT_DATE - INTERVAL '7 DAYS'
                GROUP BY inverter_id
            ),
            historical_stats AS (
                SELECT 
                    inverter_id,
                    AVG(avg_efficiency) as historical_efficiency
                FROM daily_inverter_stats
                WHERE date < CURRENT_DATE - INTERVAL '7 DAYS'
                GROUP BY inverter_id
            )
            SELECT 
                rs.inverter_id,
                rs.recent_faults,
                rs.recent_efficiency,
                hs.historical_efficiency,
                rs.max_temp,
                CASE
                    WHEN rs.recent_faults > 5 OR rs.max_temp > 70 OR (rs.recent_efficiency < hs.historical_efficiency * 0.95) THEN 'Urgent'
                    WHEN rs.recent_faults > 2 OR rs.max_temp > 65 OR (rs.recent_efficiency < hs.historical_efficiency * 0.98) THEN 'Monitor'
                    ELSE 'Healthy'
                END as status,
                CASE
                    WHEN rs.recent_faults > 5 OR rs.max_temp > 70 OR (rs.recent_efficiency < hs.historical_efficiency * 0.95) THEN 
                        (CURRENT_DATE + INTERVAL '2 DAYS')::date
                    WHEN rs.recent_faults > 2 OR rs.max_temp > 65 OR (rs.recent_efficiency < hs.historical_efficiency * 0.98) THEN 
                        (CURRENT_DATE + INTERVAL '7 DAYS')::date
                    ELSE
                        (CURRENT_DATE + INTERVAL '30 DAYS')::date
                END as recommended_date
            FROM recent_stats rs
            LEFT JOIN historical_stats hs ON rs.inverter_id = hs.inverter_id
            ORDER BY 
                CASE
                    WHEN rs.recent_faults > 5 OR rs.max_temp > 70 OR (rs.recent_efficiency < hs.historical_efficiency * 0.95) THEN 1
                    WHEN rs.recent_faults > 2 OR rs.max_temp > 65 OR (rs.recent_efficiency < hs.historical_efficiency * 0.98) THEN 2
                    ELSE 3
                END
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        # Convert results to list of dicts for JSON response
        data = []
        for row in results:
            efficiency_change = 0
            if row['historical_efficiency'] and row['recent_efficiency']:
                efficiency_change = ((row['recent_efficiency'] - row['historical_efficiency']) / row['historical_efficiency']) * 100
            
            data.append({
                'inverter_id': row['inverter_id'],
                'status': row['status'],
                'recent_faults': int(row['recent_faults']),
                'efficiency_change': round(efficiency_change, 2),
                'max_temp': float(row['max_temp']),
                'recommended_date': row['recommended_date'].strftime('%Y-%m-%d')
            })
        
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"Error getting maintenance prediction data: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)