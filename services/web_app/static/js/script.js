document.addEventListener('DOMContentLoaded', function () {
    // State and Initialization
    initializeVlmOptionHandlers();
    initializeTabSwitching();
    initializeFilePreviewHandlers();
    let pageContentsArray = [];
    let currentOutputFormat = 'markdown';

    // Element Selectors
    const ocrForm = document.getElementById('ocr-form');
    const runOcrButton = document.getElementById('run-ocr-button');
    const ocrOutputArea = document.getElementById('ocr-output-area');
    const outputFormatSelect = document.getElementById('output-format-select');
    const ocrRenderToggle = document.getElementById('ocr-render-toggle-checkbox');
    const copyOcrTextButton = document.getElementById('copy-ocr-text');
    const ocrToggleContainer = document.getElementById('ocr-toggle-container');
    const outputHeader = document.getElementById('output-header');

    // --- Event Listener for Output Format Change ---
    if (outputFormatSelect) {
        outputFormatSelect.addEventListener('change', function() {
            currentOutputFormat = this.value;
            updatePreviewIcon(currentOutputFormat);
            if (pageContentsArray.length > 0) {
                // Pass the element itself
                renderFinalOutput(pageContentsArray, currentOutputFormat, ocrOutputArea, ocrRenderToggle);
            }
        });
        currentOutputFormat = outputFormatSelect.value;
        updatePreviewIcon(currentOutputFormat);
    }

    // --- Event Listener for Form Submission ---
    if (ocrForm) {
        ocrForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            pageContentsArray = [];
            const originalButtonText = runOcrButton.innerHTML;
            setButtonState(runOcrButton, true, originalButtonText);
            displayProcessingMessage(ocrOutputArea);
            const formData = new FormData(ocrForm);
            currentOutputFormat = formData.get('output_format');
            updatePreviewIcon(currentOutputFormat);
            let streamStarted = false;
            try {
                const response = await submitSingleOcr(formData);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) {
                        // --- THIS IS THE CRUCIAL FIX ---
                        // Pass the toggle ELEMENT directly to the rendering function.
                        renderFinalOutput(pageContentsArray, currentOutputFormat, ocrOutputArea, ocrRenderToggle);
                        ocrToggleContainer.style.display = 'flex';
                        outputHeader.style.display = 'flex';
                        break;
                    }
                    buffer += decoder.decode(value, { stream: true });
                    let boundary = buffer.lastIndexOf('\n');
                    if (boundary === -1) continue;
                    if (!streamStarted) {
                        ocrOutputArea.innerHTML = '';
                        streamStarted = true;
                    }
                    let completeLines = buffer.substring(0, boundary);
                    buffer = buffer.substring(boundary + 1);
                    completeLines.split('\n').forEach(line => {
                        if (line.trim() === '') return;
                        try {
                            const jsonData = JSON.parse(line);
                            handleStreamItem(jsonData, currentOutputFormat, ocrOutputArea, pageContentsArray);
                        } catch (e) {
                            console.warn("Skipping invalid JSON line:", line, e);
                        }
                    });
                }
            } catch (error) {
                displayOcrError(error, ocrOutputArea);
            } finally {
                setButtonState(runOcrButton, false, originalButtonText);
            }
        });
    }

    // --- Event Listener for Preview Toggle ---
    if (ocrRenderToggle) {
        ocrRenderToggle.addEventListener('change', function() {
            if (pageContentsArray.length > 0) {
                // Pass the element (this) itself
                renderFinalOutput(pageContentsArray, currentOutputFormat, ocrOutputArea, this);
            }
        });
    }

    // --- Event Listener for Copy Button ---
    if (copyOcrTextButton) {
        copyOcrTextButton.addEventListener('click', function() {
            const textToCopy = pageContentsArray.join('\n\n---\n\n');
            copyTextToClipboard(textToCopy, this);
        });
    }

        // =================================================================
    // == Batch Processing Tab Elements
    // =================================================================
    const batchForm = document.getElementById('batch-ocr-form');
    const batchFileInput = document.getElementById('batch-input-file');
    const batchVlmApiSelect = document.getElementById('batch-vlm-api-select');
    const batchInputFileListArea = document.getElementById('batch-input-file-list-area');
    const batchOutputFileListhArea = document.getElementById('batch-output-file-list-area');
    const runBatchOcrButton = document.getElementById('run-batch-ocr-button');

    // =================================================================
    // == Event Listeners for Batch Tab
    // =================================================================

    // Listener for VLM API selection change in the batch tab
    if (batchVlmApiSelect) {
        batchVlmApiSelect.addEventListener('change', handleBatchVlmApiChange);
    }

    // Listener for file input changes in the batch tab
    if (batchFileInput) {
        batchFileInput.addEventListener('change', updateBatchFileList);
    }

    // Listener for the batch OCR form submission
    if (batchForm) {
        batchForm.addEventListener('submit', handleBatchFormSubmit);
    }


    // =================================================================
    // == Handler Functions for Batch Tab
    // =================================================================

    /**
     * Shows/hides conditional input fields based on the selected VLM API for the batch form.
     */
    function handleBatchVlmApiChange() {
        // Hide all conditional option divs
        document.querySelectorAll('#batch-ocr-form .conditional-options').forEach(div => {
            div.style.display = 'none';
        });

        // Show the relevant div based on selection
        const selectedApi = batchVlmApiSelect.value;
        const optionsDiv = document.getElementById(`batch-${selectedApi}-options`);
        if (optionsDiv) {
            optionsDiv.style.display = 'block';
        }
    }

    /**
     * Updates the UI to display the list of selected files for the batch process.
     * This version uses styled list-group containers for a cleaner look.
     */
    function updateBatchFileList() {
        if (!batchInputFileListArea || !batchFileInput.files) return;

        const maxFiles = parseInt(batchFileInput.getAttribute('data-max-files'), 10) || 100;
        if (batchFileInput.files.length > maxFiles) {
            alert(`You can only select a maximum of ${maxFiles} files.`);
            batchFileInput.value = ''; // Clear the selection
            batchInputFileListArea.innerHTML = '<p class="ocr-status-message">Please select files (up to ' + maxFiles + ').</p>';
            return;
        }

        batchInputFileListArea.innerHTML = ''; // Clear previous list

        if (batchFileInput.files.length === 0) {
            batchInputFileListArea.innerHTML = '<p class="ocr-status-message">Uploaded files will be listed here.</p>';
            return;
        }

        const list = document.createElement('div');
        list.className = 'list-group'; // Use a div with a list-group class

        for (const file of batchFileInput.files) {
            const listItem = document.createElement('div');
            listItem.className = 'list-group-item'; // Each file is a list-group-item

            const icon = document.createElement('i');
            icon.className = 'fas fa-file-alt me-2'; // Font Awesome file icon
            
            listItem.appendChild(icon);
            listItem.appendChild(document.createTextNode(` ${file.name}`));
            list.appendChild(listItem);
        }
        batchInputFileListArea.appendChild(list);
    }

    /**
     * Handles the submission of the batch OCR form.
     * This now uses a two-step process:
     * 1. POSTs the form data to get a unique batch ID.
     * 2. Uses that ID to open a GET EventSource connection for streaming results.
     */
    function handleBatchFormSubmit(event) {
        event.preventDefault(); // Prevent the default form submission

        const formData = new FormData(batchForm);
        const totalFiles = batchFileInput.files.length;

        if (totalFiles === 0) {
            alert("Please select files to process.");
            return;
        }

        // --- UI Updates for Processing ---
        runBatchOcrButton.disabled = true;
        runBatchOcrButton.textContent = 'Uploading...';
        batchOutputFileListhArea.innerHTML = '<p class="ocr-status-message">Uploading files and initiating batch job...</p>';

        // --- Step 1: Initiate the batch job via POST ---
        fetch('/api/initiate_batch_ocr', {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || 'Server error') });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success' && data.batch_id) {
                // --- UI Update ---
                runBatchOcrButton.textContent = 'Processing...';
                batchOutputFileListhArea.innerHTML = '<p class="ocr-status-message">Processing... waiting for first file to complete.</p>';
                
                // --- Step 2: Start streaming results via GET ---
                startStreamingResults(data.batch_id);
            } else {
                throw new Error(data.error || 'Failed to initiate batch job.');
            }
        })
        .catch(err => {
            console.error("Failed to initiate batch OCR:", err);
            batchOutputFileListhArea.innerHTML = `<p class="ocr-status-message text-danger">Error: ${err.message}</p>`;
            runBatchOcrButton.disabled = false;
            runBatchOcrButton.textContent = 'Run Batch OCR';
        });
    }

    /**
     * Connects to the SSE endpoint to stream results for a given batch ID.
     * @param {string} batchId - The unique ID for the batch job.
     */
    function startStreamingResults(batchId) {
        const eventSource = new EventSource(`/api/stream_batch_results/${batchId}`);
        let processedFiles = 0;

        // --- SSE Message Handler ---
        eventSource.onmessage = function(e) {
            const message = JSON.parse(e.data);

            // Create the list container on the first valid message
            if (processedFiles === 0 && message.type !== 'completed') {
                batchOutputFileListhArea.innerHTML = '';
                const list = document.createElement('div');
                list.className = 'list-group';
                list.id = 'batch-output-list-group';
                batchOutputFileListhArea.appendChild(list);
            }

            const outputListGroup = document.getElementById('batch-output-list-group');

            if (message.type === 'result') {
                processedFiles++;
                const link = document.createElement('a');
                link.href = message.download_url;
                link.className = 'list-group-item list-group-item-action list-group-item-success';
                link.setAttribute('download', '');
                const icon = document.createElement('i');
                icon.className = 'fas fa-download me-2';
                link.appendChild(icon);
                link.appendChild(document.createTextNode(` ${message.filename}`));
                outputListGroup.appendChild(link);

            } else if (message.type === 'error') {
                const errorItem = document.createElement('div');
                errorItem.className = 'list-group-item list-group-item-danger';
                const icon = document.createElement('i');
                icon.className = 'fas fa-exclamation-triangle me-2';
                errorItem.appendChild(icon);
                errorItem.appendChild(document.createTextNode(` Error: ${message.filename || 'a file'} - ${message.data}`));
                outputListGroup.appendChild(errorItem);
            
            } else if (message.type === 'completed') {
                // --- THIS IS THE COMPLETED LOGIC ---
                // 1. Gracefully close the connection from the client side
                eventSource.close();
                
                // 2. Re-enable the run button
                runBatchOcrButton.disabled = false;
                runBatchOcrButton.textContent = 'Run Batch OCR';

                // 3. Enable the "Download All" button
                const downloadAllLink = document.getElementById('batch-download-all-button');
                downloadAllLink.href = `/api/download_batch_zip/${message.batch_id}`;
                downloadAllLink.classList.remove('btn-disabled');
                downloadAllLink.removeAttribute('aria-disabled');
            }
        };

        // --- SSE Error Handler ---
        eventSource.onerror = function(err) {
            console.error("EventSource failed:", err);
            eventSource.close(); // Always close on error
            runBatchOcrButton.disabled = false;
            runBatchOcrButton.textContent = 'Run Batch OCR';
            
            // Avoid adding a duplicate error message if one already exists
            if (!document.querySelector('#batch-output-list-group .list-group-item-danger')) {
                const errorPara = document.createElement('p');
                errorPara.className = 'ocr-status-message text-danger';
                errorPara.textContent = 'A connection error occurred. Please check the server logs and try again.';
                batchOutputFileListhArea.appendChild(errorPara);
            }
        };
    }

    // Initialize the VLM options on page load for the batch tab
    handleBatchVlmApiChange();
});

// Utility Functions
function showCopyConfirmation(button) {
    const originalTitle = button.title;
    button.classList.add('fa-check');
    button.classList.remove('fa-copy');
    button.title = 'Copied!';
    setTimeout(() => {
        button.classList.remove('fa-check');
        button.classList.add('fa-copy');
        button.title = originalTitle;
    }, 2000);
}

function copyTextToClipboard(textToCopy, button) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            showCopyConfirmation(button);
        }).catch(err => console.error('Failed to copy with Clipboard API:', err));
    } else {
        const textArea = document.createElement('textarea');
        textArea.value = textToCopy;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            if (document.execCommand('copy')) {
                showCopyConfirmation(button);
            }
        } catch (err) {
            console.error('Fallback copy failed:', err);
        }
        document.body.removeChild(textArea);
    }
}