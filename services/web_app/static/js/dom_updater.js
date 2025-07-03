// =================================================================
// == DOM Manipulation Functions
// =================================================================

/**
 * Sets the state of a button, showing a spinner and disabling it while loading.
 * @param {HTMLElement} button - The button element to update.
 * @param {boolean} isLoading - Whether the button should be in a loading state.
 * @param {string} originalText - The original text to restore when not loading.
 */
function setButtonState(button, isLoading, originalText) {
    button.disabled = isLoading;
    if (isLoading) {
        button.innerHTML = '<span class="spinner"></span> Processing...';
    } else {
        button.innerHTML = originalText;
    }
}

/**
 * Displays the initial "processing" message in a target area.
 * @param {HTMLElement} outputArea - The element to update.
 */
function displayProcessingMessage(outputArea) {
    outputArea.innerHTML = '<p class="ocr-status-message">Processing... Please wait.</p>';
    // Also hide result-specific elements
    document.getElementById('output-header').style.display = 'none';
    document.getElementById('ocr-toggle-container').style.display = 'none';
}

/**
 * Displays the successful OCR result in the output area.
 * @param {object} data - The success data from the API.
 * @param {HTMLElement} ocrOutputArea - The element to display the result in.
 * @returns {string} The raw text result.
 */
function displaySingleOcrSuccess(data, ocrOutputArea) {
    ocrOutputArea.innerHTML = `<pre><code>${data.text}</code></pre>`;
    document.getElementById('output-header').style.display = 'flex';
    document.getElementById('ocr-toggle-container').style.display = 'flex';
    return data.text; // Return the raw text to be stored
}

/**
 * Displays an error message in the output area.
 * @param {Error} error - The error object.
 * @param {HTMLElement} outputArea - The element to display the error in.
 */
function displayOcrError(error, outputArea) {
    console.error('An error occurred:', error);
    outputArea.innerHTML = `<p class="ocr-status-message error-message">Error: ${error.message}</p>`;
}

/**
 * Updates the output area with HTML rendered from Markdown.
 * @param {string} html - The HTML string to render.
 * @param {HTMLElement} outputArea - The element to update.
 */
function updateRenderedMarkdown(html, outputArea) {
    outputArea.innerHTML = `<div class="rendered-markdown">${html}</div>`;
}

/**
 * Displays raw text inside a <pre><code> block.
 * @param {string} rawText - The raw text to display.
 * @param {HTMLElement} outputArea - The element to update.
 */
function displayRawText(rawText, outputArea) {
    outputArea.innerHTML = `<pre><code>${rawText}</code></pre>`;
}


/**
 * Appends a chunk of text to the OCR output area, rendering it if the format is markdown.
 * @param {string} rawOcrResult - The ENTIRE raw text accumulated so far.
 * @param {string} outputFormat - The current output format (e.g., 'markdown').
 * @param {HTMLElement} outputArea - The element to update.
 */
function appendOcrChunk(rawOcrResult, outputFormat, outputArea) {
    // On the first chunk, clear the "Processing..." message
    if (outputArea.querySelector('.ocr-status-message')) {
        outputArea.innerHTML = '';
        // Show the result headers
        document.getElementById('output-header').style.display = 'flex';
        document.getElementById('ocr-toggle-container').style.display = 'flex';
    }

    // If the format is markdown, render it. Otherwise, display as plain text.
    if (outputFormat === 'markdown' && typeof marked !== 'undefined') {
        // Clean the markdown output by removing the code fences for live rendering
        const cleanedForLiveRender = rawOcrResult.replace(/```markdown/g, '').replace(/```/g, '');
        outputArea.innerHTML = marked.parse(cleanedForLiveRender);
    } else {
        // For 'text', 'HTML', or if marked.js is missing, show raw text
        outputArea.textContent = rawOcrResult;
    }
}