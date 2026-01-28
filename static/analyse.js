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

// Values from Flask/Jinja (numbers)
const prevHP = {{ prev_hp }};
const currHP = {{ curr_hp }};

const prevDet = {{ prev_detentions }};
const currDet = {{ curr_detentions }};

const prevWd = {{ prev_wd }};
const currWd = {{ curr_wd }};

// Attendance values
const prevPresent = {{ prev_present }};
const currPresent = {{ curr_present }};
const prevAbsent = {{ prev_absent }};
const currAbsent = {{ curr_absent }};
const prevLate = {{ prev_late }};
const currLate = {{ curr_late }};

buildCompareChart('housePointsChart', 'House Points', prevHP, currHP);
buildCompareChart('detentionsChart', 'Detentions', prevDet, currDet);
buildCompareChart('withdrawalsChart', 'Withdrawals', prevWd, currWd);

// Attendance chart - grouped bar chart showing all three statuses
const attendanceCtx = document.getElementById('attendanceChart');
new Chart(attendanceCtx, {
    type: 'bar',
    data: {
        labels: ['Present', 'Absent', 'Late'],
        datasets: [
            {
                label: 'Previous Week',
                data: [prevPresent, prevAbsent, prevLate],
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            },
            {
                label: 'Current Week',
                data: [currPresent, currAbsent, currLate],
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
