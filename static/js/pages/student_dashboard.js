document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.sidebar-link[data-section-target]');
    const sections = document.querySelectorAll('.student-dashboard-section');

    function showSection(targetId) {
        if (!targetId || targetId === '') targetId = 'groups';
        if (targetId.startsWith('#')) targetId = targetId.substring(1);

        let found = false;
        sections.forEach(sec => {
            if (sec.getAttribute('data-section') === targetId) {
                sec.classList.add('is-active');
                found = true;
            } else {
                sec.classList.remove('is-active');
            }
        });

        if (!found) {
            targetId = 'groups';
            sections.forEach(sec => {
                if (sec.getAttribute('data-section') === targetId) {
                    sec.classList.add('is-active');
                }
            });
        }

        tabs.forEach(tab => {
            if (tab.getAttribute('data-section-target') === targetId) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            const target = this.getAttribute('data-section-target');
            showSection(target);
        });
    });

    window.addEventListener('hashchange', function() {
        showSection(window.location.hash);
    });

    showSection(window.location.hash);
});
