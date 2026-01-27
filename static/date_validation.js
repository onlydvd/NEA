/**
 * Date of Birth Validation
 * Validates that the student's age is appropriate for their year group
 * Year 12: 16-17 years old
 * Year 13: 17-18 years old
 */

function validateDateOfBirth() {
    const dobInput = document.getElementById('dob');
    const yearSelect = document.querySelector('input[name="yeargroup"]:checked');
    
    if (!dobInput || !yearSelect) return true; // Skip if elements don't exist
    
    const dob = new Date(dobInput.value);
    const yeargroup = parseInt(yearSelect.value);
    
    // Calculate age
    const today = new Date();
    let age = today.getFullYear() - dob.getFullYear();
    const monthDiff = today.getMonth() - dob.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
        age--;
    }
    
    // Define valid age ranges for each year group
    const validAges = {
        12: { min: 16, max: 17 },
        13: { min: 17, max: 18 }
    };
    
    const allowedRange = validAges[yeargroup];
    
    if (age < allowedRange.min || age > allowedRange.max) {
        alert(`For Year ${yeargroup}, students should be ${allowedRange.min}-${allowedRange.max} years old. The selected date of birth makes the student ${age} years old.`);
        dobInput.value = '';
        return false;
    }
    
    return true;
}

// Set min and max dates when page loads
function setDateConstraints() {
    const dobInput = document.getElementById('dob');
    if (!dobInput) return;
    
    const today = new Date();
    
    // Max date: 16 years ago (for youngest Year 12)
    const maxDate = new Date(today.getFullYear() - 16, today.getMonth(), today.getDate());
    
    // Min date: 18 years ago (for oldest Year 13)
    const minDate = new Date(today.getFullYear() - 18, today.getMonth(), today.getDate());
    
    dobInput.max = maxDate.toISOString().split('T')[0];
    dobInput.min = minDate.toISOString().split('T')[0];
}

// Validate on DOB change
function setupDateValidation() {
    const dobInput = document.getElementById('dob');
    const yearInputs = document.querySelectorAll('input[name="yeargroup"]');
    
    if (dobInput) {
        dobInput.addEventListener('change', validateDateOfBirth);
    }
    
    if (yearInputs) {
        yearInputs.forEach(input => {
            input.addEventListener('change', validateDateOfBirth);
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    setDateConstraints();
    setupDateValidation();
});
