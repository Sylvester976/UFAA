(function () {
    const INACTIVITY_LIMIT = 15 * 60 * 1000; // 15 minutes
    const WARNING_BEFORE   = 1 * 60 * 1000;  // warn 1 minute before logout
    let inactivityTimer;
    let warningTimer;
    let warningShown = false;

    function logoutUser() {
        // Clear any existing timers
        clearTimeout(inactivityTimer);
        clearTimeout(warningTimer);

        if (!window.appConfig) {
            window.location.href = '/login/';
            return;
        }

        Swal.fire({
            icon: 'warning',
            title: 'Session Expired',
            text: 'You have been logged out due to inactivity.',
            confirmButtonText: 'OK',
            allowOutsideClick: false,  // force them to click OK
            allowEscapeKey: false,
        }).then(() => {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', window.appConfig.csrfToken);
            navigator.sendBeacon(window.appConfig.logoutUrl, formData);
            window.location.href = window.appConfig.loginUrl;
        });
    }

    function showWarning() {
        if (warningShown) return;
        warningShown = true;

        Swal.fire({
            icon: 'info',
            title: 'Still there?',
            text: 'You will be logged out in 1 minute due to inactivity.',
            timer: 60000,
            timerProgressBar: true,
            showCancelButton: true,
            confirmButtonText: 'Keep me logged in',
            cancelButtonText: 'Logout now',
            allowOutsideClick: false,
            allowEscapeKey: false,
        }).then((result) => {
            if (result.isConfirmed) {
                // User is still there, reset everything
                warningShown = false;
                resetTimer();
            } else {
                // Dismissed or logout now clicked
                logoutUser();
            }
        });
    }

    function resetTimer() {
        // Don't reset if warning is already showing
        if (warningShown) return;

        clearTimeout(inactivityTimer);
        clearTimeout(warningTimer);

        // Show warning 1 minute before logout
        warningTimer = setTimeout(showWarning, INACTIVITY_LIMIT - WARNING_BEFORE);

        // Logout after full limit
        inactivityTimer = setTimeout(logoutUser, INACTIVITY_LIMIT);
    }

    // Listen for user activity
    ['click', 'mousemove', 'keydown', 'scroll', 'touchstart'].forEach(event => {
        window.addEventListener(event, resetTimer, { passive: true });
    });

    // Start timer on page load
    resetTimer();

})();


function goBack() {
    window.history.back();
}