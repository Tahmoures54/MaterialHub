document.addEventListener('DOMContentLoaded', function() {
    const notificationsContainer = document.getElementById('notifications');
    if (!notificationsContainer) {
        console.warn('Notifications container (#notifications) not found in the page.');
        return;
    }
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const notification = document.createElement('div');
        notification.className = 'alert ' + alert.className.split(' ')[1];
        notification.textContent = alert.textContent;
        notificationsContainer.appendChild(notification);
        setTimeout(() => notification.remove(), 5000);
    });
});