/**
 * Common JavaScript functions for the Inverter Monitoring Dashboard
 */

// Format number with thousands separator
function formatNumber(number, decimals = 0) {
    return number.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// Format percentage
function formatPercent(number, decimals = 1) {
    return number.toLocaleString('en-US', {
        style: 'percent',
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// Format date string to locale format
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

// Get color based on value and threshold
function getColorByValue(value, thresholds) {
    if (value <= thresholds.low) {
        return '#36b37e'; // Green
    } else if (value <= thresholds.medium) {
        return '#ffab00'; // Amber
    } else {
        return '#ff5630'; // Red
    }
}

// Get status color
function getStatusColor(status) {
    switch (status.toLowerCase()) {
        case 'urgent':
            return '#ff5630';
        case 'monitor':
            return '#ffab00';
        case 'healthy':
            return '#36b37e';
        default:
            return '#0052cc';
    }
}

// Get trend icon and class
function getTrendHTML(value, isPositiveGood = true) {
    let iconClass, className;
    
    if (value > 0) {
        iconClass = 'fa-arrow-up';
        className = isPositiveGood ? 'trend-up' : 'trend-up-bad';
    } else if (value < 0) {
        iconClass = 'fa-arrow-down';
        className = isPositiveGood ? 'trend-down-bad' : 'trend-down-good';
    } else {
        iconClass = 'fa-minus';
        className = 'trend-neutral';
    }
    
    return `<span class="trend ${className}"><i class="fas ${iconClass}"></i> ${Math.abs(value).toFixed(1)}%</span>`;
}

// Show loading spinner
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }
}

// Show error message
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `<div class="alert alert-danger" role="alert">${message}</div>`;
    }
}

// Get date range from URL parameters
function getDateRangeFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const start = urlParams.get('start');
    const end = urlParams.get('end');
    
    if (start && end) {
        return { start, end };
    }
    
    // Default to last 30 days
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 29);
    
    return {
        start: startDate.toISOString().split('T')[0],
        end: endDate.toISOString().split('T')[0]
    };
}

// Update URL with date range parameters
function updateURLWithDateRange(start, end) {
    const url = new URL(window.location);
    url.searchParams.set('start', start);
    url.searchParams.set('end', end);
    window.history.pushState({}, '', url);
}

// Get days between two dates
function getDaysBetween(startDate, endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const diffTime = Math.abs(end - start);
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

// Handle API errors
function handleAPIError(error, elementId) {
    console.error('API Error:', error);
    showError(elementId || 'error-container', 'Failed to load data. Please try again later.');
}

// Format datetime with time
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Get chart color palette for inverters
function getInverterColorPalette() {
    return [
        '#0078d4', // Blue
        '#ffaa44', // Orange
        '#33aa55', // Green
        '#8b5cf6', // Purple
        '#f43f5e', // Red
        '#0ea5e9', // Light Blue
        '#fbbf24', // Yellow
        '#ec4899'  // Pink
    ];
}