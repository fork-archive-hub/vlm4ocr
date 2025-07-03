document.addEventListener('DOMContentLoaded', function () {
    // State and Initialization
    initializeTabSwitching();
    initializeVlmOptionHandlers();
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