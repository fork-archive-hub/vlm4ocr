(function () {
    function escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // ── JSON line tokenizer ────────────────────────────────────────────────
    function highlightJsonLine(line) {
        let result = '';
        let i = 0;
        while (i < line.length) {
            const ch = line[i];
            if (ch === '"') {
                let j = i + 1;
                while (j < line.length) {
                    if (line[j] === '\\') { j += 2; continue; }
                    if (line[j] === '"') { j++; break; }
                    j++;
                }
                const str = escapeHtml(line.slice(i, j));
                const isKey = /^\s*:/.test(line.slice(j));
                result += isKey
                    ? `<span class="json-key">${str}</span>`
                    : `<span class="json-string">${str}</span>`;
                i = j;
            } else if ('{}[]'.includes(ch)) {
                result += `<span class="json-brace">${ch}</span>`;
                i++;
            } else if (':,'.includes(ch)) {
                result += `<span class="json-punct">${ch}</span>`;
                i++;
            } else if (/\d/.test(ch) || (ch === '-' && /\d/.test(line[i + 1] || ''))) {
                const m = line.slice(i).match(/^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/);
                if (m) {
                    result += `<span class="json-number">${m[0]}</span>`;
                    i += m[0].length;
                } else {
                    result += escapeHtml(ch); i++;
                }
            } else if (/[tfn]/.test(ch)) {
                const m = line.slice(i).match(/^(true|false|null)(?=[^\w]|$)/);
                if (m) {
                    result += `<span class="json-keyword">${m[1]}</span>`;
                    i += m[1].length;
                } else {
                    result += escapeHtml(ch); i++;
                }
            } else {
                result += escapeHtml(ch); i++;
            }
        }
        return result;
    }

    // ── Inline markdown (applied to already-escaped text) ─────────────────
    function applyInline(text) {
        text = text.replace(/\*\*\*(.*?)\*\*\*/g, '<span class="md-bold-italic">***$1***</span>');
        text = text.replace(/\*\*(.*?)\*\*/g,     '<span class="md-bold">**$1**</span>');
        text = text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<span class="md-italic">*$1*</span>');
        text = text.replace(/`([^`]+)`/g,         '<span class="md-code">`$1`</span>');
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span class="md-link">[$1]($2)</span>');
        return text;
    }

    // ── Main highlighter ──────────────────────────────────────────────────
    function highlightMarkdown(text) {
        const lines = text.split('\n');
        let inFence = false;
        let fenceLang = '';

        return lines.map(line => {
            // Fenced code block delimiter: ```lang or ```
            const fenceMatch = line.match(/^(```+)(\w*)$/);
            if (fenceMatch) {
                if (!inFence) {
                    inFence = true;
                    fenceLang = fenceMatch[2].toLowerCase();
                } else {
                    inFence = false;
                    fenceLang = '';
                }
                return `<span class="md-fence">${escapeHtml(line)}</span>`;
            }

            if (inFence) {
                return fenceLang === 'json'
                    ? highlightJsonLine(line)
                    : `<span class="md-code-block">${escapeHtml(line)}</span>`;
            }

            // Normal markdown — escape first, then apply inline highlights
            const esc = escapeHtml(line);

            const headingMatch = esc.match(/^(#{1,6})(\s.*)$/);
            if (headingMatch) {
                return `<span class="md-heading">${headingMatch[1]}${applyInline(headingMatch[2])}</span>`;
            }
            if (esc.startsWith('&gt;')) {
                return `<span class="md-blockquote">${applyInline(esc)}</span>`;
            }
            if (/^(---|___|\*\*\*)$/.test(esc.trim())) {
                return `<span class="md-hr">${esc}</span>`;
            }
            const listMatch = esc.match(/^(\s*[-*+]\s|\s*\d+\.\s)(.*)/);
            if (listMatch) {
                return `<span class="md-list-marker">${listMatch[1]}</span>${applyInline(listMatch[2])}`;
            }
            return applyInline(esc);
        }).join('\n');
    }

    // ── Backdrop sync ─────────────────────────────────────────────────────
    function syncBackdrop(textarea, backdrop) {
        backdrop.innerHTML = highlightMarkdown(textarea.value) + ' ';
        backdrop.scrollTop = textarea.scrollTop;
    }

    function initInlineEditor(textareaId) {
        const textarea = document.getElementById(textareaId);
        const backdrop = document.getElementById(textareaId + '-backdrop');
        if (!textarea || !backdrop) return;
        textarea.addEventListener('input', () => syncBackdrop(textarea, backdrop));
        textarea.addEventListener('scroll', () => { backdrop.scrollTop = textarea.scrollTop; });
        syncBackdrop(textarea, backdrop);
    }

    // ── Modal ─────────────────────────────────────────────────────────────
    let activeTextareaId = null;

    function openModal(textareaId) {
        activeTextareaId = textareaId;
        const src = document.getElementById(textareaId);
        const modalTextarea = document.getElementById('modal-prompt-textarea');
        const modalBackdrop = document.getElementById('modal-prompt-backdrop');
        modalTextarea.value = src ? src.value : '';
        syncBackdrop(modalTextarea, modalBackdrop);
        document.getElementById('prompt-expand-modal').style.display = 'flex';
        setTimeout(() => modalTextarea.focus(), 50);
    }

    function closeModal(apply) {
        if (apply && activeTextareaId) {
            const src = document.getElementById(activeTextareaId);
            const modalTextarea = document.getElementById('modal-prompt-textarea');
            if (src) {
                src.value = modalTextarea.value;
                const srcBackdrop = document.getElementById(activeTextareaId + '-backdrop');
                if (srcBackdrop) syncBackdrop(src, srcBackdrop);
            }
        }
        document.getElementById('prompt-expand-modal').style.display = 'none';
        activeTextareaId = null;
    }

    document.addEventListener('DOMContentLoaded', function () {
        initInlineEditor('ocr-user-prompt');
        initInlineEditor('batch-ocr-user-prompt');

        document.querySelectorAll('.prompt-expand-btn').forEach(btn => {
            btn.addEventListener('click', function () { openModal(this.dataset.target); });
        });

        const modalTextarea = document.getElementById('modal-prompt-textarea');
        const modalBackdrop = document.getElementById('modal-prompt-backdrop');
        if (modalTextarea && modalBackdrop) {
            modalTextarea.addEventListener('input', () => syncBackdrop(modalTextarea, modalBackdrop));
            modalTextarea.addEventListener('scroll', () => { modalBackdrop.scrollTop = modalTextarea.scrollTop; });
        }

        const overlay = document.getElementById('prompt-expand-modal');
        document.getElementById('prompt-modal-apply-btn')?.addEventListener('click', () => closeModal(true));
        document.getElementById('prompt-modal-cancel-btn')?.addEventListener('click', () => closeModal(false));
        document.getElementById('prompt-modal-close-btn')?.addEventListener('click', () => closeModal(false));
        overlay?.addEventListener('click', e => { if (e.target === overlay) closeModal(false); });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && overlay && overlay.style.display !== 'none') closeModal(false);
        });
    });
})();
