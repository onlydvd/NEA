/**
 * Flag Student for Help
 * Sends a flag message to the general message board
 */

async function flagStudent(studentId) {
    const button = document.getElementById('flag-btn');
    
    try {
        // Show loading state
        button.disabled = true;
        const originalText = button.textContent;
        button.textContent = 'Flagging...';
        
        // Send flag request to server
        const response = await fetch(`/flag_student/${studentId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Success - show confirmation
            button.textContent = '✓ Flagged';
            button.style.backgroundColor = '#28a745';
            button.style.color = 'white';
            
            showNotification(data.message, 'success');
            
            // Reset button after 3 seconds
            setTimeout(() => {
                button.disabled = false;
                button.textContent = originalText;
                button.style.backgroundColor = '';
                button.style.color = '';
            }, 3000);
        } else {
            // Error
            showNotification(`Error: ${data.error}`, 'error');
            button.disabled = false;
            button.textContent = originalText;
        }
    } catch (error) {
        console.error('Error flagging student:', error);
        showNotification('Failed to flag student', 'error');
        button.disabled = false;
        button.textContent = originalText;
    }
}

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Style the notification
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.padding = '15px 20px';
    notification.style.borderRadius = '4px';
    notification.style.color = 'white';
    notification.style.zIndex = '9999';
    notification.style.animation = 'slideInRight 0.3s ease';
    
    if (type === 'success') {
        notification.style.backgroundColor = '#28a745';
    } else if (type === 'error') {
        notification.style.backgroundColor = '#dc3545';
    } else {
        notification.style.backgroundColor = '#007bff';
    }
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}
