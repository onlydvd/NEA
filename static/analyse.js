// Simple helper to build the same chart style for each section
function buildCompareChart(canvasId, labelText, prevValue, currValue) {
    const ctx = document.getElementById(canvasId);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Previous Week', 'Current Week'],
            datasets: [{
                label: labelText,
                data: [prevValue, currValue],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 } }
            },
            plugins: {
                legend: { display: true }
            }
        }
    });
}

// Initialize all charts using data passed from the HTML template
function initializeCharts() {
    // Get data from the global chartData object set in HTML
    const data = window.chartData;
    
    // Build comparison charts for house points, detentions, and withdrawals
    buildCompareChart('housePointsChart', 'House Points', data.prevHP, data.currHP);
    buildCompareChart('detentionsChart', 'Detentions', data.prevDet, data.currDet);
    buildCompareChart('withdrawalsChart', 'Withdrawals', data.prevWd, data.currWd);

    // Attendance chart - grouped bar chart showing all three statuses
    const attendanceCtx = document.getElementById('attendanceChart');
    new Chart(attendanceCtx, {
        type: 'bar',
        data: {
            labels: ['Present', 'Absent', 'Late'],
            datasets: [
                {
                    label: 'Previous Week',
                    data: [data.prevPresent, data.prevAbsent, data.prevLate],
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Current Week',
                    data: [data.currPresent, data.currAbsent, data.currLate],
                    backgroundColor: 'rgba(75, 192, 75, 0.5)',
                    borderColor: 'rgba(75, 192, 75, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, ticks: { precision: 0 } }
            },
            plugins: {
                legend: { display: true }
            }
        }
    });
}
