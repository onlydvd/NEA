/**
 * Simple Subject Selection Validation
 * Prevents the same subject from being selected in multiple dropdowns
 */

function setupSubjectValidation() {
    // Get all subject dropdowns
    const subjectSelects = [
        document.getElementById('first_subject'),
        document.getElementById('second_subject'),
        document.getElementById('third_subject'),
        document.getElementById('fourth_subject')
    ];

    // Add event listener to each dropdown
    subjectSelects.forEach(select => {
        if (select) {
            select.addEventListener('change', function() {
                updateSubjectOptions(subjectSelects);
            });
        }
    });

    // Run on page load
    updateSubjectOptions(subjectSelects);
}

function updateSubjectOptions(selects) {
    // Get all currently selected subjects
    const selectedSubjects = new Set();
    
    selects.forEach(select => {
        if (select && select.value !== '') {
            selectedSubjects.add(select.value);
        }
    });

    // For each dropdown, enable/disable options
    selects.forEach((select, index) => {
        if (!select) return;
        
        const currentValue = select.value;
        const options = select.querySelectorAll('option');

        options.forEach(option => {
            // Don't disable: empty option, or currently selected option
            if (option.value === '' || option.value === currentValue) {
                option.disabled = false;
            } else if (selectedSubjects.has(option.value)) {
                // Disable if already selected in another dropdown
                option.disabled = true;
            } else {
                option.disabled = false;
            }
        });
    });
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', setupSubjectValidation);
