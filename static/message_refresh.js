function refreshMessages() {
    fetch(window.location.href)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, 'text/html');
            const newContent = newDoc.querySelector('.messages');
            const currentContent = document.querySelector('.messages');
            if (newContent && currentContent) {
                currentContent.innerHTML = newContent.innerHTML;
            }
        })
        .catch(error => console.log('Refresh failed:', error));
}

// Refresh every 5 seconds (5000 milliseconds)
setInterval(refreshMessages, 5000);
