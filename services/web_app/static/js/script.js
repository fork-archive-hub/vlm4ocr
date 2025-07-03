document.addEventListener('DOMContentLoaded', function () {

    // =================================================================
    // == Initialization - SINGLE ENTRY POINT
    // =================================================================
    initializeTabSwitching();
    initializeVlmOptionHandlers();
    initializeFilePreviewHandlers();


    // =================================================================
    // == Main Logic Orchestration
    // =================================================================
    const ocrForm = document.getElementById('ocr-form');
    const runOcrButton = document.getElementById('run-ocr-button');
    const ocrOutputArea = document.getElementById('ocr-output-area');
    const ocrRenderToggle = document.getElementById('ocr-render-toggle-checkbox');
    const copyOcrTextButton = document.getElementById('copy-ocr-text');
    let rawOcrResult = ''; // This variable stays here to hold the state

    // --- Handle SINGLE File Form Submission ---
    if (ocrForm) {
        ocrForm.addEventListener('submit', async function (event) {
            event.preventDefault();
            const originalButtonText = runOcrButton.innerHTML;
            rawOcrResult = ''; // Clear previous result

            setButtonState(runOcrButton, true, originalButtonText);
            displayProcessingMessage(ocrOutputArea);

            const formData = new FormData(ocrForm);
            const outputFormat = formData.get('output_format'); // Get format at the start

            try {
                const response = await submitSingleOcr(formData);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    let boundary = buffer.lastIndexOf('\n');
                    if (boundary === -1) continue;

                    let completeLines = buffer.substring(0, boundary);
                    buffer = buffer.substring(boundary + 1);

                    completeLines.split('\n').forEach(line => {
                        if (line.trim() === '') return;
                        try {
                            const jsonData = JSON.parse(line);
                            if (jsonData.type === 'ocr_chunk' && jsonData.data) {
                                rawOcrResult += jsonData.data; // Build up the full raw result
                                // **CHANGE**: Call the updated append function with the full text and format
                                appendOcrChunk(rawOcrResult, outputFormat, ocrOutputArea);
                            }
                        } catch (e) {
                            console.warn("Skipping invalid JSON line:", line, e);
                        }
                    });
                }

                // Handle any final data left in the buffer
                if (buffer.trim()) {
                    try {
                        const jsonData = JSON.parse(buffer);
                        if (jsonData.type === 'ocr_chunk' && jsonData.data) {
                            rawOcrResult += jsonData.data;
                            appendOcrChunk(rawOcrResult, outputFormat, ocrOutputArea);
                        }
                    } catch(e) {
                        console.warn("Skipping invalid JSON in final buffer:", buffer, e);
                    }
                }

                const outputFormat = formData.get('output_format');
                if (outputFormat === 'markdown' || outputFormat === 'HTML') {
                    ocrRenderToggle.checked = true;
                    // SIMPLIFIED: Just call the handler with the raw result.
                    await handleRenderOcrOutput(rawOcrResult);
                } else {
                    ocrRenderToggle.checked = false;
                    displayRawText(rawOcrResult, ocrOutputArea);
                }

            } catch (error) {
                displayOcrError(error, ocrOutputArea);
            } finally {
                setButtonState(runOcrButton, false, originalButtonText);
            }
        });
    }

    // --- Handle OCR Output Rendering (Markdown/HTML) ---
    async function handleRenderOcrOutput(text) {
        try {
            // MOVED: The cleaning logic is now here, so it runs every time.
            const cleanedText = text.replace(/^```markdown\s*?\n?/i, '').replace(/\n?```\s*$/i, '').trim();
            const data = await renderMarkdown(cleanedText); // Calls the API service
            updateRenderedMarkdown(data.html, ocrOutputArea); // Updates the DOM
        } catch (error) {
            console.error('Error rendering markdown:', error);
            ocrOutputArea.innerHTML += `<p class="error-message">Could not render preview.</p>`;
        }
    }

    if (ocrRenderToggle) {
        ocrRenderToggle.addEventListener('change', function() {
            if (this.checked) {
                handleRenderOcrOutput(rawOcrResult);
            } else {
                displayRawText(rawOcrResult, ocrOutputArea);
            }
        });
    }

    // --- Handle Copy Text functionality ---
    if (copyOcrTextButton) {
        copyOcrTextButton.addEventListener('click', function() {
            navigator.clipboard.writeText(rawOcrResult).then(() => {
                const originalTitle = this.title;
                this.classList.add('fa-check'); this.classList.remove('fa-copy');
                this.title = 'Copied!';
                setTimeout(() => {
                    this.classList.remove('fa-check'); this.classList.add('fa-copy');
                    this.title = originalTitle;
                }, 2000);
            });
        });
    }

});