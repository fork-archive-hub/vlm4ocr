/**
 * Submits the single file OCR form to the backend and returns the streaming response.
 * @param {FormData} formData - The form data to submit.
 * @returns {Promise<Response>} A promise that resolves to the raw Response object.
 */
async function submitSingleOcr(formData) {
    const response = await fetch('/api/run_ocr', {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Server responded with status ${response.status}`);
    }
    // Return the entire response object so we can read its stream
    return response;
}

/**
 * Submits text to the backend to be rendered as HTML.
 * @param {string} text - The text to render.
 * @returns {Promise<object>} A promise that resolves to the JSON response with the HTML.
 */
async function renderMarkdown(text) {
    const response = await fetch('/api/render_markdown', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Server responded with status ${response.status}`);
    }

    return response.json();
}