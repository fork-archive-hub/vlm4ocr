/**
 * Initializes the event listeners for switching between the single file and batch processing tabs.
 * This version manually manipulates classes and has no external dependencies.
 */
function initializeTabSwitching() {
    const singleFileTabLink = document.getElementById('single-file-tab-link');
    const batchProcessTabLink = document.getElementById('batch-process-tab-link');
    const singleFilePane = document.getElementById('single-file-pane');
    const batchProcessPane = document.getElementById('batch-process-pane');

    // Make sure all elements exist before adding listeners
    if (!singleFileTabLink || !batchProcessTabLink || !singleFilePane || !batchProcessPane) {
        console.error('Tab switching elements could not be found. Tab functionality will be disabled.');
        return;
    }

    // This function adds/removes the correct classes to show/hide the tab content
    function switchTabs(activeLink, inactiveLink, activePane, inactivePane) {
        // Update the tab links' active state
        activeLink.classList.add('active');
        inactiveLink.classList.remove('active');

        // Update the tab panes' active state
        activePane.classList.add('show', 'active');
        inactivePane.classList.remove('show', 'active');
    }

    singleFileTabLink.addEventListener('click', function (event) {
        event.preventDefault();
        switchTabs(singleFileTabLink, batchProcessTabLink, singleFilePane, batchProcessPane);
    });

    batchProcessTabLink.addEventListener('click', function (event) {
        event.preventDefault();
        switchTabs(batchProcessTabLink, singleFileTabLink, batchProcessPane, singleFilePane);
    });
}