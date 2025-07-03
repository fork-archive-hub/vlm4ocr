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
 * Shows the relevant conditional options div and hides the others based on the API selection.
 * @param {HTMLElement} formElement - The form element containing the dropdown.
 * @param {string} selectedApiValue - The value of the selected VLM API from the <option> tag.
 * @param {string} idPrefix - The prefix for the div IDs (e.g., 'batch-').
 */
function updateConditionalOptions(formElement, selectedApiValue, idPrefix) {
    // Hide all conditional option divs within the specified form
    formElement.querySelectorAll('.conditional-options').forEach(div => {
        div.style.display = 'none';
    });

    // **FIX**: Normalize the value to ensure it matches the div ID format (e.g., 'azure_openai' becomes 'azure-openai')
    const normalizedApi = selectedApiValue.replace(/_/g, '-');

    // Construct the ID for the div to show
    const optionsDivId = `${idPrefix}${normalizedApi}-options`;
    const optionsDiv = document.getElementById(optionsDivId);

    // For debugging: Log what we're looking for and if we found it.
    console.log(`Looking for div with ID: #${optionsDivId}`);
    if (optionsDiv) {
        console.log("Found it! Displaying div.");
        optionsDiv.style.display = 'block';
    } else {
        console.log("Could not find the matching div.");
    }
}


/**
 * Initializes handlers for file inputs to show previews or file lists.
 */
function initializeFilePreviewHandlers() {
    // Handler for the single file input
    const inputFile = document.getElementById('input-file');
    const inputPreviewArea = document.getElementById('input-preview-area');
    const previewPlaceholder = document.getElementById('preview-placeholder');

    if (inputFile) {
        inputFile.addEventListener('change', function (event) {
            const file = event.target.files[0];
            if (!file) return;

            previewPlaceholder.style.display = 'none';
            // Clear previous preview
            while (inputPreviewArea.firstChild && inputPreviewArea.firstChild !== previewPlaceholder) {
                inputPreviewArea.removeChild(inputPreviewArea.firstChild);
            }

            // Preview logic based on file type
            if (file.type.startsWith('image/') && file.type !== 'image/tiff') {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.style.maxWidth = '100%';
                    img.style.maxHeight = '100%';
                    img.style.objectFit = 'contain';
                    inputPreviewArea.appendChild(img);
                };
                reader.readAsDataURL(file);
            } else if (file.type === 'application/pdf') {
                const objectUrl = URL.createObjectURL(file);
                const embed = document.createElement('embed');
                embed.src = objectUrl;
                embed.type = 'application/pdf';
                embed.style.width = '100%';
                embed.style.height = '100%';
                inputPreviewArea.appendChild(embed);
            } else if (file.type === 'image/tiff') {
                const objectUrl = URL.createObjectURL(file);
                const iframe = document.createElement('iframe');
                iframe.src = objectUrl;
                iframe.style.width = '100%';
                iframe.style.height = '100%';
                iframe.style.border = 'none';
                inputPreviewArea.appendChild(iframe);
            } else {
                inputPreviewArea.innerHTML = `<p class="ocr-status-message">Preview for this file type is not available.</p><p>Filename: ${file.name}</p>`;
            }
        });
    }

    // Handler for the batch file input
    const batchInputFile = document.getElementById('batch-input-file');
    const batchFileListArea = document.getElementById('batch-input-file-list-area');
    if (batchInputFile) {
        batchInputFile.addEventListener('change', function () {
            if (this.files.length > 0) {
                let fileListHtml = '<ul>';
                Array.from(this.files).forEach(file => {
                    fileListHtml += `<li>${file.name} (${(file.size / 1024).toFixed(2)} KB)</li>`;
                });
                fileListHtml += '</ul>';
                batchFileListArea.innerHTML = fileListHtml;
            } else {
                batchFileListArea.innerHTML = '<p class="ocr-status-message">Uploaded files will be listed here.</p>';
            }
        });
    }
}