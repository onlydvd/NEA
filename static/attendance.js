/**
 * Attendance Management System
 * Handles real-time attendance marking for students
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize attendance tracking
    initializeAttendance();
    setupEventListeners();
    updateSummary();
});

/**
 * Initialize attendance system
 */
function initializeAttendance() {
    const totalStudents = document.querySelectorAll('.student-row').length;
    document.getElementById('total-count').textContent = totalStudents;
    updateMarkedCount();
}

/**
 * Setup event listeners for all interactive elements
 */
function setupEventListeners() {
    // Status button clicks
    document.querySelectorAll('.status-btn').forEach(btn => {
        btn.addEventListener('click', handleStatusButtonClick);
    });

    // Mark all present button
    document.getElementById('mark-all-present').addEventListener('click', markAllPresent);

    // Save attendance button
    document.getElementById('save-attendance').addEventListener('click', saveAllAttendance);
}

/**
 * Handle individual status button clicks
 */
function handleStatusButtonClick(event) {
    const button = event.target;
    const row = button.closest('.student-row');
    const studentId = row.dataset.studentId;
    const status = button.dataset.status;
    const buttonGroup = button.closest('.button-group');

    // Remove active class from all buttons in this group
    buttonGroup.querySelectorAll('.status-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Add active class to clicked button
    button.classList.add('active');

    // Update status display
    const statusDisplay = row.querySelector('.status-display');
    statusDisplay.textContent = status;

    // Update counts
    updateMarkedCount();
    updateSummary();

    // Send to server immediately
    logAttendance(studentId, status);
}

/**
 * Mark all students as present
 */
function markAllPresent() {
    document.querySelectorAll('.student-row').forEach(row => {
        const presentBtn = row.querySelector('.btn-present');
        if (!presentBtn.classList.contains('active')) {
            presentBtn.click();
        }
    });

    showToast('All students marked as present', 'success');
}

/**
 * Save all attendance records to the server
 */
function saveAllAttendance() {
    const button = document.getElementById('save-attendance');
    button.disabled = true;
    button.textContent = 'Saving...';

    let allSaved = true;
    const promises = [];

    document.querySelectorAll('.student-row').forEach(row => {
        const studentId = row.dataset.studentId;
        const statusDisplay = row.querySelector('.status-display');
        const status = statusDisplay.textContent;

        // Only save if status is marked
        if (status !== 'Not Marked') {
            promises.push(
                logAttendance(studentId, status, false)
                    .catch(() => { allSaved = false; })
            );
        }
    });

    Promise.all(promises).then(() => {
        button.disabled = false;
        button.textContent = 'Save Attendance';

        if (allSaved) {
            showToast('Attendance saved successfully!', 'success');
        } else {
            showToast('Some attendance records failed to save', 'error');
        }
    });
}

/**
 * Log attendance for a single student
 * @param {number} studentId - Student ID
 * @param {string} status - Attendance status (Present/Absent/Late)
 * @param {boolean} silent - If true, don't show toast messages
 */
async function logAttendance(studentId, status, silent = true) {
    try {
        const response = await fetch('/log_attendance', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                student_id: studentId,
                status: status,
                period: attendanceData.period,
                date: attendanceData.date
            })
        });

        const result = await response.json();

        if (!response.ok) {
            console.error('Error logging attendance:', result.error);
            if (!silent) {
                showToast(`Error: ${result.error}`, 'error');
            }
            return false;
        }

        if (!silent) {
            showToast(result.message, 'success');
        }
        return true;

    } catch (error) {
        console.error('Network error:', error);
        if (!silent) {
            showToast('Network error while saving attendance', 'error');
        }
        return false;
    }
}

/**
 * Update the marked count display
 */
function updateMarkedCount() {
    const marked = document.querySelectorAll('.status-display').length -
                   Array.from(document.querySelectorAll('.status-display'))
                   .filter(el => el.textContent === 'Not Marked').length;
    
    document.getElementById('marked-count').textContent = marked;
}

/**
 * Update the attendance summary statistics
 */
function updateSummary() {
    let presentCount = 0;
    let lateCount = 0;
    let absentCount = 0;
    let unmarkedCount = 0;

    document.querySelectorAll('.status-display').forEach(display => {
        const status = display.textContent;
        switch (status) {
            case 'Present':
                presentCount++;
                break;
            case 'Late':
                lateCount++;
                break;
            case 'Absent':
                absentCount++;
                break;
            case 'Not Marked':
                unmarkedCount++;
                break;
        }
    });

    document.getElementById('summary-present').textContent = presentCount;
    document.getElementById('summary-late').textContent = lateCount;
    document.getElementById('summary-absent').textContent = absentCount;
    document.getElementById('summary-unmarked').textContent = unmarkedCount;
}

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type of message (success/error/info)
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

/**
 * Get attendance status for a specific student
 * @param {number} studentId - Student ID
 */
async function getAttendanceStatus(studentId) {
    try {
        const response = await fetch(`/get_attendance_status?student_id=${studentId}&period=${attendanceData.period}&date=${attendanceData.date}`);
        const result = await response.json();

        if (response.ok) {
            return result.status;
        } else {
            console.error('Error fetching status:', result.error);
            return 'Not Marked';
        }
    } catch (error) {
        console.error('Network error:', error);
        return 'Not Marked';
    }
}

/**
 * Keyboard shortcuts
 */
document.addEventListener('keydown', function(event) {
    // Alt+P for Present
    if (event.altKey && event.key === 'p') {
        event.preventDefault();
        document.getElementById('mark-all-present').click();
    }

    // Alt+S for Save
    if (event.altKey && event.key === 's') {
        event.preventDefault();
        document.getElementById('save-attendance').click();
    }
});

/**
 * Auto-load attendance status on page load
 */
function loadExistingAttendance() {
    document.querySelectorAll('.student-row').forEach(row => {
        const studentId = row.dataset.studentId;
        getAttendanceStatus(studentId).then(status => {
            if (status !== 'Not Marked') {
                const statusDisplay = row.querySelector('.status-display');
                statusDisplay.textContent = status;

                // Update button active states
                const buttonGroup = row.querySelector('.button-group');
                buttonGroup.querySelectorAll('.status-btn').forEach(btn => {
                    btn.classList.remove('active');
                    if (btn.dataset.status === status) {
                        btn.classList.add('active');
                    }
                });
            }
        });
    });

    setTimeout(() => {
        updateMarkedCount();
        updateSummary();
    }, 500);
}

// Load existing attendance when page loads
loadExistingAttendance();

/**
 * Prevent accidental page navigation
 */
window.addEventListener('beforeunload', function(event) {
    const marked = Array.from(document.querySelectorAll('.status-display'))
                   .filter(el => el.textContent !== 'Not Marked').length;
    
    if (marked > 0) {
        event.preventDefault();
        event.returnValue = '';
    }
});
