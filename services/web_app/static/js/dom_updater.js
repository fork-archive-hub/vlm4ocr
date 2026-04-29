// =================================================================
// == DOM Manipulation Functions
// =================================================================

let pageContentHosts = {};
let currentPageCounter = 0;

function setButtonState(button, state, originalText) {
    if (state === 'stop') {
        button.disabled = false;
        button.classList.add('btn-stop');
        button.innerHTML = 'Stop';
    } else { // 'idle'
        button.disabled = false;
        button.classList.remove('btn-stop');
        button.innerHTML = originalText;
    }
}

function displayProcessingMessage(outputArea) {
    outputArea.innerHTML = '<p class="ocr-status-message ocr-status-processing">Processing... Please wait.</p>';
    document.getElementById('output-header').style.display = 'none';
    document.getElementById('ocr-toggle-container').style.display = 'none';
    pageContentHosts = {};
    currentPageCounter = 0;
}

function displayOcrError(error, outputArea) {
    console.error('An error occurred:', error);
    outputArea.innerHTML = `<p class="ocr-status-message ocr-status-error">Error: ${error.message}</p>`;
}

function updatePreviewIcon(format) {
    const previewIcon = document.getElementById('preview-icon');
    if (!previewIcon) return;
    let iconClass = 'fa-markdown', title = 'Markdown Preview', lib = 'fab';
    if (format.toLowerCase() === 'html') {
        iconClass = 'fa-code'; title = 'HTML Preview'; lib = 'fas';
    } else if (format.toLowerCase() === 'text') {
        iconClass = 'fa-file-alt'; title = 'Text Preview'; lib = 'fas';
    } else if (format.toLowerCase() === 'json') {
        iconClass = 'fa-brackets-curly'; title = 'JSON Preview'; lib = 'fas';
    }
    previewIcon.className = `${lib} ${iconClass}`;
    previewIcon.title = title;
}

function getOrCreatePageHost(outputArea, outputFormat) {
    if (pageContentHosts[currentPageCounter]) {
        return pageContentHosts[currentPageCounter];
    }
    const pageWrapper = document.createElement('div');
    pageWrapper.id = `page-wrapper-${currentPageCounter}`;
    outputArea.appendChild(pageWrapper);
    let newHost;
    const format = outputFormat.toLowerCase();

    if (format === 'html') {
        const shadowHost = document.createElement('div');
        shadowHost.className = 'ocr-html-shadow-host';
        try {
            const shadowRoot = shadowHost.attachShadow({ mode: 'open' });
            const style = document.createElement('style');
            style.textContent = `:host { display: block; border: 1px dashed #ccc; padding: 10px; margin-bottom: 10px; } body { margin: 0; }`;
            shadowRoot.appendChild(style);
            newHost = shadowRoot;
        } catch (e) { newHost = document.createElement('pre'); }
        pageWrapper.appendChild(shadowHost);
    } else if (format === 'markdown') {
        newHost = document.createElement('div');
        newHost.className = 'ocr-markdown-content';
        pageWrapper.appendChild(newHost);
    } else if (format === 'json') {
        newHost = document.createElement('pre');
        newHost.className = 'ocr-plaintext-content ocr-json-streaming';
        pageWrapper.appendChild(newHost);
    } else {
        newHost = document.createElement('pre');
        newHost.className = 'ocr-plaintext-content';
        pageWrapper.appendChild(newHost);
    }
    pageContentHosts[currentPageCounter] = newHost;
    return newHost;
}

function handleStreamItem(item, outputFormat, outputArea, pageContentsArray) {
    if (item.type === 'ocr_chunk' && typeof item.data === 'string') {
        pageContentsArray[currentPageCounter] = (pageContentsArray[currentPageCounter] || '') + item.data;
        const host = getOrCreatePageHost(outputArea, outputFormat);
        const format = outputFormat.toLowerCase();

        if (host.nodeType === Node.DOCUMENT_FRAGMENT_NODE) { // ShadowRoot for HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = pageContentsArray[currentPageCounter];
            const style = host.querySelector('style');
            host.innerHTML = '';
            if (style) host.appendChild(style);
            while (tempDiv.firstChild) {
                host.appendChild(tempDiv.firstChild);
            }
        } else {
             if (format === 'markdown' && typeof marked !== 'undefined') {
                host.innerHTML = marked.parse(pageContentsArray[currentPageCounter].replace(/```markdown|```/g, ''));
             } else {
                host.textContent = pageContentsArray[currentPageCounter];
             }
        }
        
        const scrollThreshold = 50; // Pixels from bottom to still auto-scroll
        const userScrolledUp = outputArea.scrollHeight - outputArea.scrollTop - outputArea.clientHeight > scrollThreshold;

        if (!userScrolledUp && outputArea.scrollHeight > outputArea.clientHeight) {
            outputArea.scrollTop = outputArea.scrollHeight;
        }

    } else if (item.type === 'page_delimiter') {
        const wrapper = document.getElementById(`page-wrapper-${currentPageCounter}`);
        if (wrapper) {
            const hr = document.createElement('hr');
            hr.className = 'page-delimiter-hr';
            wrapper.insertAdjacentElement('afterend', hr);
        }
        currentPageCounter++;
    } else if (item.type === 'error') {
        displayOcrError(new Error(item.data), outputArea);
    }
}

/**
 * Renders the final output. The Markdown logic now mirrors the streaming logic.
 */
function renderFinalOutput(pageContentsArray, outputFormat, outputArea, toggleElement) {
    outputArea.innerHTML = '';
    const isPreviewMode = toggleElement ? toggleElement.checked : true;
    const rawText = pageContentsArray.join('\n\n---\n\n');

    if (!isPreviewMode) {
        const pre = document.createElement('pre');
        pre.className = 'ocr-rawtext-content';
        pre.textContent = rawText;
        outputArea.appendChild(pre);
        return;
    }

    const format = outputFormat.toLowerCase();

    if (format === 'html') {
        if (pageContentsArray.length > 0) {
            const combinedHtml = pageContentsArray.join(`<hr class='page-delimiter-hr page-delimiter-html-view'>`);
            let wrapper = document.createElement('div');
            wrapper.className = 'ocr-page-content-rendered-wrapper html-wrapper single-html-container';
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'width: 100%; border: none; height: 75vh;';
            const baseStyle = `<style>html,body{margin:0;padding:0;height:100%;overflow:auto;}body{font-family:sans-serif;color:#212529;background-color:#fff;padding:10px;}hr.page-delimiter-html-view{border:0;height:1px;background-color:#ced4da;margin:25px 5px;}</style>`;
            iframe.srcdoc = baseStyle + combinedHtml;
            iframe.onerror = () => {
                wrapper.innerHTML = `<p class='ocr-status-error'>Error loading HTML content into preview.</p><pre>${combinedHtml}</pre>`;
            };
            wrapper.appendChild(iframe);
            outputArea.appendChild(wrapper);
        } else {
            outputArea.innerHTML = '<p class="ocr-status-message">No HTML content to display.</p>';
        }
    } else if (format === 'markdown' && typeof marked !== 'undefined') {
        // --- THIS IS THE KEY FIX ---
        // Iterate and render each page separately, just like the stream handler.
        pageContentsArray.forEach((pageContent, index) => {
            const pageDiv = document.createElement('div');
            pageDiv.className = 'ocr-markdown-content';
            const cleanedContent = pageContent.replace(/```markdown|```/g, '');
            pageDiv.innerHTML = marked.parse(cleanedContent);
            outputArea.appendChild(pageDiv);

            // Add a delimiter between pages, but not after the last one
            if (index < pageContentsArray.length - 1) {
                const hr = document.createElement('hr');
                hr.className = 'page-delimiter-hr';
                outputArea.appendChild(hr);
            }
        });
    } else if (format === 'json') {
        pageContentsArray.forEach((pageContent, index) => {
            const pre = document.createElement('pre');
            const code = document.createElement('code');
            code.className = 'language-json';

            const stripped = pageContent.replace(/```json|```/g, '').trim();
            let displayText = stripped;
            try {
                const parsed = JSON.parse(stripped);
                displayText = JSON.stringify(parsed, null, 2);
            } catch (_) {
                // Not valid JSON yet — show raw text without highlight
                pre.className = 'ocr-plaintext-content';
                pre.textContent = stripped;
                outputArea.appendChild(pre);
                if (index < pageContentsArray.length - 1) {
                    const hr = document.createElement('hr');
                    hr.className = 'page-delimiter-hr';
                    outputArea.appendChild(hr);
                }
                return;
            }

            if (typeof hljs !== 'undefined') {
                code.innerHTML = hljs.highlight(displayText, { language: 'json' }).value;
            } else {
                code.textContent = displayText;
            }
            pre.appendChild(code);
            outputArea.appendChild(pre);

            if (index < pageContentsArray.length - 1) {
                const hr = document.createElement('hr');
                hr.className = 'page-delimiter-hr';
                outputArea.appendChild(hr);
            }
        });
    } else { // text
        const pre = document.createElement('pre');
        pre.className = 'ocr-plaintext-content';
        pre.textContent = rawText;
        outputArea.appendChild(pre);
    }
}