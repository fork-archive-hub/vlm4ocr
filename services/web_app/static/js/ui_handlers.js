/**
 * Attaches event listeners to the VLM API select dropdowns on both forms.
 */
function initializeVlmOptionHandlers() {
    // Handler for the single file form
    const singleFileForm = document.getElementById('ocr-form');
    const singleFileSelect = document.getElementById('vlm-api-select');
    if (singleFileSelect) {
        singleFileSelect.addEventListener('change', function () {
            updateConditionalOptions(singleFileForm, this.value, '');
        });
    }

    // Handler for the batch processing form
    const batchForm = document.getElementById('batch-ocr-form');
    const batchSelect = document.getElementById('batch-vlm-api-select');
    if (batchSelect) {
        batchSelect.addEventListener('change', function () {
            updateConditionalOptions(batchForm, this.value, 'batch-');
        });
    }
}

/**
 * Shows the relevant conditional options div and hides the others by toggling a class.
 * @param {HTMLElement} formElement - The form element containing the dropdown.
 * @param {string} selectedApiValue - The value of the selected VLM API.
 * @param {string} idPrefix - The prefix for the div IDs (e.g., 'batch-').
 */
function updateConditionalOptions(formElement, selectedApiValue, idPrefix) {
    // Hide all conditional option divs by removing the 'is-visible' class
    formElement.querySelectorAll('.conditional-options').forEach(div => {
        div.classList.remove('is-visible');
    });

    // Normalize the value to ensure it matches the div ID format
    const normalizedApi = selectedApiValue.replace(/_/g, '-');
    const optionsDivId = `${idPrefix}${normalizedApi}-options`;
    const optionsDiv = document.getElementById(optionsDivId);

    if (optionsDiv) {
        // Show the correct div by adding the 'is-visible' class
        optionsDiv.classList.add('is-visible');
    }
}


/**
 * Initializes handlers for file inputs to show previews or file lists.
 */
function initializeFilePreviewHandlers() {
    const fileInput = document.getElementById('input-file');
    const dropZone = document.querySelector('#single-file-pane .file-drop-zone');
    const dropZoneText = dropZone ? dropZone.querySelector('.drop-zone-text') : null;
    const previewArea = document.getElementById('input-preview-area');

    let currentPreviewUrl = null; // For revoking image object URLs

    if (!fileInput || !dropZone || !previewArea) {
        console.error("File preview initialization failed: one or more required elements not found.");
        return;
    }

    // --- RENDER FUNCTIONS (Restored from original script) ---

    /**
     * Renders a preview for standard image types (PNG, JPEG, etc.).
     */
    function renderImagePreview(file) {
        if (currentPreviewUrl) {
            URL.revokeObjectURL(currentPreviewUrl);
        }
        const img = document.createElement('img');
        img.style.cssText = 'max-width:100%; max-height:100%; display:block; margin:auto;';
        currentPreviewUrl = URL.createObjectURL(file);
        img.src = currentPreviewUrl;
        img.onload = () => {
            previewArea.innerHTML = '';
            previewArea.appendChild(img);
        };
        img.onerror = () => {
            previewArea.innerHTML = '<p class="ocr-status-message ocr-status-error">Could not preview image.</p>';
            URL.revokeObjectURL(currentPreviewUrl);
            currentPreviewUrl = null;
        };
    }

    /**
     * Renders a multi-page preview of a PDF file onto canvas elements.
     */
    async function renderPdfPreview(file) {
        if (typeof pdfjsLib === 'undefined') {
            previewArea.innerHTML = '<p class="ocr-status-message ocr-status-error">PDF Viewer library (PDF.js) is not loaded.</p>';
            return;
        }
        // Ensure any old image object URL is cleaned up
        if (currentPreviewUrl) {
            URL.revokeObjectURL(currentPreviewUrl);
            currentPreviewUrl = null;
        }
        const fileReader = new FileReader();
        fileReader.onload = async function() {
            try {
                const typedarray = new Uint8Array(this.result);
                const pdfDoc = await pdfjsLib.getDocument({ data: typedarray }).promise;
                previewArea.innerHTML = ''; // Clear loading message
                for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
                    const page = await pdfDoc.getPage(pageNum);
                    const viewport = page.getViewport({ scale: 1.5 });
                    const canvas = document.createElement('canvas');
                    const context = canvas.getContext('2d');
                    canvas.height = viewport.height;
                    canvas.width = viewport.width;
                    canvas.style.cssText = 'display: block; margin-bottom: 10px; max-width: 100%; border: 1px solid #ccc;';
                    previewArea.appendChild(canvas);
                    await page.render({ canvasContext: context, viewport: viewport }).promise;
                }
            } catch (error) {
                console.error("PDF preview error:", error);
                previewArea.innerHTML = `<p class="ocr-status-message ocr-status-error">Error rendering PDF preview: ${error.message}</p>`;
            }
        };
        fileReader.readAsArrayBuffer(file);
    }

    /**
     * Fetches and renders a preview for a TIFF file by converting it on the server.
     */
    async function renderTiffPreview(file) {
        // Ensure any old image object URL is cleaned up
        if (currentPreviewUrl) {
            URL.revokeObjectURL(currentPreviewUrl);
            currentPreviewUrl = null;
        }
        const formData = new FormData();
        formData.append('tiff_file', file);
        try {
            const response = await fetch('/api/preview_tiff', { method: 'POST', body: formData });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP error ${response.status}` }));
                throw new Error(errorData.error);
            }
            const result = await response.json();
            previewArea.innerHTML = ''; // Clear loading message
            if (result.status === 'success' && result.pages_data) {
                result.pages_data.forEach(base64Data => {
                    const img = document.createElement('img');
                    img.style.cssText = 'display: block; margin-bottom: 10px; max-width: 100%; border: 1px solid #ccc;';
                    img.src = `data:image/png;base64,${base64Data}`;
                    previewArea.appendChild(img);
                });
            } else {
                throw new Error(result.error || 'TIFF conversion failed on server.');
            }
        } catch (error) {
            console.error("TIFF preview error:", error);
            previewArea.innerHTML = `<p class="ocr-status-message ocr-status-error">Error rendering TIFF preview: ${error.message}</p>`;
        }
    }


    /**
     * Orchestrates the display of a file preview based on its type.
     */
    function displayPreview(file) {
        previewArea.innerHTML = '';
        if (!file) {
            previewArea.innerHTML = '<p class="ocr-status-message" style="color:#ccc;">Upload a file to see a preview</p>';
            if (currentPreviewUrl) {
                URL.revokeObjectURL(currentPreviewUrl);
                currentPreviewUrl = null;
            }
            return;
        }
        previewArea.innerHTML = '<p class="ocr-status-message ocr-status-processing">Loading preview...</p>';

        const fileType = file.type;
        const fileName = file.name.toLowerCase();

        // --- THIS IS THE RESTORED LOGIC ---
        if (fileType === 'application/pdf' || fileName.endsWith('.pdf')) {
            renderPdfPreview(file);
        } else if (fileType === 'image/tiff' || fileName.endsWith('.tiff') || fileName.endsWith('.tif')) {
            renderTiffPreview(file);
        } else if (fileType.startsWith('image/')) {
            renderImagePreview(file);
        } else {
            previewArea.innerHTML = `<p class="ocr-status-message">Preview for this file type is not supported.</p>`;
            if (currentPreviewUrl) {
                URL.revokeObjectURL(currentPreviewUrl);
                currentPreviewUrl = null;
            }
        }
    }

    // --- Event Listeners ---
    
    // Drag and Drop Listeners
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, e => {
            e.preventDefault();
            e.stopPropagation();
        }, false);
    });
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'));
    });
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'));
    });

    dropZone.addEventListener('drop', (e) => {
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile) {
            fileInput.files = e.dataTransfer.files; // Assign file to the input
            dropZoneText.textContent = `Selected: ${droppedFile.name}`;
            displayPreview(droppedFile);
        }
    });

    // File Input 'change' Listener
    fileInput.addEventListener('change', () => {
        const selectedFile = fileInput.files[0];
        if (selectedFile) {
            dropZoneText.textContent = `Selected: ${selectedFile.name}`;
            displayPreview(selectedFile);
        } else {
            dropZoneText.textContent = 'Drag & drop file or click to select';
            displayPreview(null);
        }
    });
}