var APP_HOST = '';
var IS_APP_ACTIVE = true;

window._chatInstance = null;

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function windowRepaint() {
    setTimeout(() => document.body.style.height = "99%", 100);
    setTimeout(() => document.body.removeAttribute('style'), 101);
}

function onPluginShow() {
    IS_APP_ACTIVE = true;
}
function onPluginHide() {
    IS_APP_ACTIVE = false;
}

function onFilesDrag(message) {
    const ta = document.getElementById('message-input');
    if (document.activeElement === ta) {
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        ta.value = ta.value.slice(0, start) + message + ta.value.slice(end);
        ta.selectionStart = ta.selectionEnd = start + message.length;
    } else {
        ta.value = ta.value + message;
    }
}

function onFileChosen(path) {
    windowRepaint(); // dont remove!

    if (!path) return;
    if (!window._chatInstance) return;

    const chat = window._chatInstance;

    if (chat.pendingImages.length >= 10) {
        chat.addMessage({ message: 'Maximum 10 images allowed' }, 'error');
        return;
    }

    fetch(APP_HOST + '/file_content?path=' + encodeURIComponent(path))
        .then(response => response.json().then(data => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
            if (!ok || data.error) {
                chat.addMessage({ message: 'Error loading file: ' + (data.error || 'Server error') }, 'error');
                return;
            }
            chat.pendingImages.push(data.data_url);
            chat._renderPreviews();
        })
        .catch(err => {
            chat.addMessage({ message: 'Error loading file: ' + err.message }, 'error');
        });
}

function JIDETransport(request, onSuccessCb, onFailureCb) {
    if (!IS_APP_ACTIVE) {
        return;
    }

    // JS->Java transport
    window.cefQuery({
        request: request,
        onSuccess: (response) => {
            if (onSuccessCb) onSuccessCb(response);
        },
        onFailure: (errorCode, errorMessage) => {
            if (onFailureCb) onFailureCb(errorCode, errorMessage);
        }
    });
}

class SimpleChat {
    constructor() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.controlFlowStopBtn = document.getElementById('control-flow-stop');
        this.messageInput = document.getElementById('message-input');
        this.uploadImageBtn = document.getElementById('upload-image-btn');
        this.eventSource = null;

        this.ON_USER_SCROLL_SEMAPHORE = false;
        this.pendingImages = [];

        this.IS_LAST_MESSAGE_SUCCESS = false;
        this.IS_ON_END_CONVERSATION = false; // mutex for debounce

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connectSSE();
    }

    onStartConversation() {
        document.getElementById('main-wrapper').classList.add('conversation-active');
        this.controlFlowStopBtn.style.display = 'block';
        this.messageInput.style.display = 'none';
        if (this.uploadImageBtn) this.uploadImageBtn.style.display = 'none';
        this.IS_ON_END_CONVERSATION = false;

        const ctxBar = document.getElementById('context-window-bar');
        if (ctxBar) ctxBar.style.display = 'none';
    }

    onEndConversation() {
        if (this.IS_ON_END_CONVERSATION) {
            return;
        }

        if (this.IS_LAST_MESSAGE_SUCCESS) {
            this.messageInput.value = "";
            this.messageInput.style.height = 'auto';
            localStorage.removeItem('promptInputValue_' + SESSION_ID);
            this.messagesContainer.querySelectorAll('div.message.loading').forEach(el => el.remove());
        } else {
            this.messagesContainer.querySelectorAll('div.message').forEach(el => el.classList.remove('loading'));
        }

        this.controlFlowStopBtn.style.display = 'none';
        this.controlFlowStopBtn.classList.remove('loading');
        this.messageInput.style.display = 'block';
        if (this.uploadImageBtn) this.uploadImageBtn.style.display = 'block';
        document.getElementById('main-wrapper').classList.remove('conversation-active');
        if (!this.ON_USER_SCROLL_SEMAPHORE) {
            window.scrollTo(0, document.body.scrollHeight);
        }

        const ctxBar = document.getElementById('context-window-bar');
        if (ctxBar) ctxBar.style.display = 'none';

        this.IS_ON_END_CONVERSATION = true;
    }

    setupEventListeners() {
        // Restore textarea value from localStorage
        const savedValue = localStorage.getItem('promptInputValue_' + SESSION_ID);
        if (savedValue) {
            this.messageInput.value = savedValue;
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = (this.messageInput.scrollHeight + 5) + 'px';
        }

        // Handle Ctrl+Enter to send message
        this.messageInput.addEventListener('keydown', (e) => {
            // Check for Ctrl (Windows/Linux) or Cmd (Mac)
            const isCtrlClick = e.ctrlKey || e.metaKey;
            if (! (isCtrlClick && e.key === 'Enter')) {
                return;
            }

            const message = this.messageInput.value.trim();
            this.sendMessage(message);
        });

        // Stop flow
        this.controlFlowStopBtn.addEventListener('click', () => {
            this.controlFlowStopBtn.classList.add('loading');
            this.sendControl('stop');
        });

        // Auto-resize textarea and save to localStorage
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = (this.messageInput.scrollHeight + 5) + 'px';
            localStorage.setItem('promptInputValue_' + SESSION_ID, this.messageInput.value);
        });

        // Handle image paste from clipboard
        this.messageInput.addEventListener('paste', (e) => {
            const items = e.clipboardData && e.clipboardData.items;
            if (!items) return;

            let hasImage = false;
            for (const item of items) {
                if (item.kind !== 'file' || !item.type.startsWith('image/')) continue;
                hasImage = true;

                if (this.pendingImages.length >= 10) {
                    this.addMessage({ message: 'Maximum 10 images allowed' }, 'error');
                    break;
                }

                const file = item.getAsFile();
                if (!file) continue;

                if (file.size > 5 * 1024 * 1024) {
                    alert(`Pasted image exceeds the 5 MB limit.`);
                    continue;
                }

                const reader = new FileReader();
                reader.onload = (ev) => {
                    this.pendingImages.push(ev.target.result);
                    this._renderPreviews();
                };
                reader.readAsDataURL(file);
            }

            if (hasImage) {
                e.preventDefault();
            }
        });

        // Handle clicks on A tags in chat messages
        this.messagesContainer.addEventListener('click', (e) => {
            const dom_element = e.target;

            if (dom_element.tagName === 'A') {
                e.preventDefault();

                // Check for Ctrl (Windows/Linux) or Cmd (Mac)
                const isCtrlClick = event.ctrlKey || event.metaKey;

                const isCallJava = dom_element.href.indexOf('#call:');
                if (isCallJava == -1) {
                    return false;
                }

                try {
                    var command = dom_element.href.substr(isCallJava + 6).split('//');
                    if (command[0] === 'jide_open_file' && isCtrlClick) {
                        command[0] = 'jide_open_diff_file';
                    }

                    JIDETransport(
                        command.join('//'),
                        null,
                         (errorCode, errorMessage) => {
                            this.addMessage({ message: "Java error:" + errorMessage }, 'error');
                        }
                    );
                } catch (e) {
                    this.addMessage({ message: "JS error:" + e }, 'error');
                }

                return false;
            }
        });

        // Detect user scroll position and control autoscroll semaphore.
        // Uses the 'scroll' event on window so ALL input methods are covered
        // (mouse wheel, keyboard, touch, scrollbar drag, etc.).
        window.addEventListener('scroll', () => {
            if (this.IS_ON_END_CONVERSATION) {
                return;
            }

            const scrollTop = window.scrollY;
            const windowHeight = window.innerHeight;
            const documentHeight = document.documentElement.scrollHeight;
            const maxScrollTop = documentHeight - windowHeight;
            const scrollPercentage = maxScrollTop > 0 ? scrollTop / maxScrollTop : 1;

            // If user is at (or very near) the bottom, re-enable autoscroll.
            // Otherwise suppress it until they scroll back down.
            this.ON_USER_SCROLL_SEMAPHORE = scrollPercentage <= 0.99;
        });

        const uploadBtn = document.getElementById('upload-image-btn');
        const fileInput = document.getElementById('image-upload-input');

        if (uploadBtn) {
            uploadBtn.addEventListener('click', () => {
                JIDETransport(
                    "jide_choose_file",
                    null,
                    (errorCode, errorMessage) => {
                        this.addMessage({ message: "Java error:" + errorMessage }, 'error');
                    }
                );
            });
        }
    }

    connectSSE() {
        try {
            this.eventSource = new EventSource(APP_HOST + '/events?session_id=' + SESSION_ID);

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleServerMessage(data);
                } catch (e) {
                    this.addMessage({ message: "Error:" + e }, 'error');
                }
            };

            this.eventSource.onerror = (error) => {
                this.IS_LAST_MESSAGE_SUCCESS = false;
                this.updateStatus('Connection Error', 'disconnected');
                this.onEndConversation();

                // Attempt to reconnect after 3 seconds
                setTimeout(() => {
                    if (this.eventSource.readyState === EventSource.CLOSED) {
                        this.connectSSE();
                    }
                }, 3000);
            };

        } catch (error) {
            this.IS_LAST_MESSAGE_SUCCESS = false;
            this.updateStatus('Failed to Connect', 'disconnected');
            this.onEndConversation();
        }
    }

    handleServerMessage(data) {
        switch (data.type) {
            case 'nope':
                break;
            case 'status':
                this.updateStatus(data.message, 'connected');
                break;
            case 'end':
                this.onEndConversation();
                break;
            case 'error':
                this.addMessage(data, 'error');
                this.IS_LAST_MESSAGE_SUCCESS = false;
                break;
            case 'warning':
                this.addMessage(data, 'warning');
                this.IS_LAST_MESSAGE_SUCCESS = false;
                break;
            case 'heartbeat':
                break;
            case 'markdown':
                this.addMessage(data, 'markdown');
                this.IS_LAST_MESSAGE_SUCCESS = true;
                break;
            case 'html':
                this.addMessage(data, 'html');
                this.IS_LAST_MESSAGE_SUCCESS = true;
                break;
            case 'tool':
                this.addMessage(data, 'tool');
                this.IS_LAST_MESSAGE_SUCCESS = true;
                break;
            case 'agent':
                this.addMessage(data, 'agent');
                break;
            case 'context':
                this.updateContextBar(data.context_window);
                break;
            default:
                this.addMessage(data, 'bot');
                this.IS_LAST_MESSAGE_SUCCESS = true;
                break;
        }
    }

    async sendControl(command) {
        try {
            const response = await fetch(APP_HOST + '/control', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ command: command, session_id: SESSION_ID })
            });

            const result = await response.json();

            if (result.status !== 'success') {
                this.addMessage({ message: `Error: ${result.message}` }, 'error');
            }
        } catch (error) {
            this.addMessage({ message: 'Error: Failed to send command, [' + error.message + ']' }, 'error');
        }
    }

    async sendMessage(message) {
        if (!message) {
            return;
        }

        // clear response container
        this.messagesContainer.innerHTML = '';

        // Add user message to chat
        this.addMessage({ message: message, images: this.pendingImages.slice() }, 'user');

        try {
            const response = await fetch(APP_HOST + '/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message, session_id: SESSION_ID, images: this.pendingImages.slice() })
            });

            const result = await response.json();

            if (result.status !== 'success') {
                this.addMessage({ message: `Error: ${result.message}` }, 'error');
            }
            else {
                this.clearAllPendingImages();
                this.onStartConversation();
            }
        } catch (error) {
            this.addMessage({ message: 'Error: Failed to send message, [' + error.message + ']' }, 'error');
        }
    }

    addMessage(message, type) {
        if (message.hidden && message.message_id) {
            const el = this.messagesContainer.querySelector(
                `[data-message-id="${message.message_id}"]`
            );
            if (el) el.remove();

            return;
        }
        let messageDivClassName = `message ${type}-message`;
        if (message.is_success === false) messageDivClassName += ' error';

        if (type === 'user') {
            type = 'html';
            const imageHtml = (message.images && message.images.length)
                ? `<div class="user-images-row">${message.images.map(src => `<img src="${src}" class="user-image-preview" alt="attached image">`).join('')}</div>`
                : '';
            message = { ...message, message: `${imageHtml}<pre>${escapeHtml(message.message)}</pre>` };
            messageDivClassName = "message html-message user-message";
        }
        else if (type === 'tool') {
            type = 'html';
        }
        else if (type === 'agent') {
            type = 'html';
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = messageDivClassName;
        messageDiv.dataset.messageId = message.message_id;

        if (message.is_final === false) {
            messageDiv.classList.add('loading');
            const spinnerComponent = document.createElement('div');
            spinnerComponent.className = 'spinner-component';
            messageDiv.appendChild(spinnerComponent);
        }

        const messageContent = document.createElement('div');
        if (type === 'markdown') {
            const markdownText = message.message ?? '';
            messageContent.innerHTML = marked.parse(markdownText);
            this.setupMarkdownCopyButton(messageDiv, markdownText);
        }
        else if (type === 'html') {
            messageContent.innerHTML = message.message;
        }
        else {
            messageContent.textContent = message.message;
        }
        messageDiv.appendChild(messageContent);

        if (message.timestamp) {
            const timestampDiv = document.createElement('div');
            timestampDiv.className = 'timestamp';
            timestampDiv.textContent = new Date(message.timestamp * 1000).toLocaleTimeString();
            messageDiv.appendChild(timestampDiv);
        }

        const existing = message.message_id && this.messagesContainer.querySelector(
            `[data-message-id="${message.message_id}"]`
        );
        if (existing) {
            existing.replaceWith(messageDiv);
        }
        else {
            this.messagesContainer.querySelectorAll('div.loading').forEach(el => el.remove());
            this.messagesContainer.appendChild(messageDiv);
        }

        if (!this.ON_USER_SCROLL_SEMAPHORE) {
            window.scrollTo(0, document.body.scrollHeight);
        }
    }

    setupMarkdownCopyButton(messageDiv, originalMarkdown) {
        const copyButton = document.createElement('button');
        copyButton.className = 'ico-copy';

        copyButton.addEventListener('mouseenter', () => {
            copyButton.style.opacity = '1';
        });

        copyButton.addEventListener('mouseleave', () => {
            copyButton.style.opacity = '0.6';
        });

        copyButton.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(originalMarkdown);
                copyButton.style.opacity = '1';

                setTimeout(() => {
                    copyButton.style.opacity = '0.6';
                }, 2000);
            } catch (err) {
                // @todo
            }
        });

        messageDiv.appendChild(copyButton);
    }

    updateContextBar(contextWindow) {
        if (!contextWindow || !contextWindow.limit) return;

        const used = contextWindow.used;
        const limit = contextWindow.limit;
        const percentage = Math.min(Math.round((used / limit) * 100), 100);

        let bar = document.getElementById('context-window-bar');
        if (!bar) return;

        const fill = bar.querySelector('.context-bar-fill');
        const label = bar.querySelector('.context-bar-label');

        fill.style.width = percentage + '%';
        label.textContent = percentage + '% (' + used.toLocaleString() + ' / ' + limit.toLocaleString() + ')';

        bar.classList.remove('context-level-ok', 'context-level-warn', 'context-level-danger');
        if (percentage < 60) {
            bar.classList.add('context-level-ok');
        } else if (percentage < 85) {
            bar.classList.add('context-level-warn');
        } else {
            bar.classList.add('context-level-danger');
        }

        bar.style.display = 'block';
    }

    handleImageSelected(event) {
        const files = Array.from(event.target.files);
        if (!files.length) return;

        let processed = 0;
        files.forEach(file => {
            if (!file.type.startsWith('image/')) {
                alert(`"${file.name}" is not an image file.`);
                processed++;
                if (processed === files.length) this._renderPreviews();
                return;
            }
            if (file.size > 5 * 1024 * 1024) {
                alert(`"${file.name}" exceeds the 5 MB limit.`);
                processed++;
                if (processed === files.length) this._renderPreviews();
                return;
            }
            const reader = new FileReader();
            reader.onload = (e) => {
                this.pendingImages.push(e.target.result);
                processed++;
                if (processed === files.length) this._renderPreviews();
            };
            reader.readAsDataURL(file);
        });
        event.target.value = '';
    }

    _renderPreviews() {
        const container = document.getElementById('image-preview-container');
        container.innerHTML = '';
        if (this.pendingImages.length === 0) {
            container.style.display = 'none';
            return;
        }
        container.style.display = 'flex';
        this.pendingImages.forEach((url, index) => {
            const wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            wrapper.style.display = 'inline-block';

            const img = document.createElement('img');
            img.src = url;
            img.className = 'image-preview-thumb';
            img.alt = 'attached image';

            const btn = document.createElement('button');
            btn.className = 'clear-image-btn';
            btn.textContent = '✕';
            btn.title = 'Remove image';
            btn.addEventListener('click', () => {
                this.pendingImages.splice(index, 1);
                this._renderPreviews();
            });

            wrapper.appendChild(img);
            wrapper.appendChild(btn);
            container.appendChild(wrapper);
        });
    }

    clearAllPendingImages() {
        this.pendingImages = [];
        this._renderPreviews();
    }

    updateStatus(message, className) {
        try {
            JIDETransport(
                'jide_status//' + message + '//' + className,
                null,
                (errorCode, errorMessage) => {
                    this.addMessage({ message: "Java error:" + errorMessage }, 'error');
                }
            );
        } catch (e) {
            this.addMessage({ message: "[updateStatus] JS error:" + e }, 'error');
        }
    }
}

// Initialize chat when page loads
document.addEventListener('DOMContentLoaded', () => {

    if (!window._chatInstance) {
        window._chatInstance = new SimpleChat();
    }

    const agentCommandExists = typeof AGENT_COMMAND !== 'undefined';
    const agentCommandIsArray = Array.isArray(agentCommandExists ? AGENT_COMMAND : undefined);
    const agentCommandLength = agentCommandIsArray ? AGENT_COMMAND.length : 'n/a';
    const shouldRenderAgentCommandTable = agentCommandExists && agentCommandIsArray && AGENT_COMMAND.length > 0;
    const agentCommandRenderState = shouldRenderAgentCommandTable ? 'entered' : 'skipped';
    const agentCommandSamples = agentCommandIsArray ? AGENT_COMMAND.slice(0, 3) : [];
    const agentCommandSamplesHtml = agentCommandSamples.length > 0
        ? agentCommandSamples.map((item, index) => {
            const firstShellBlock = item && Array.isArray(item.shell_blocks) && item.shell_blocks.length > 0
                ? item.shell_blocks[0]
                : undefined;
            const sample = {
                command: item && item.command,
                shellBlocksLength: item && Array.isArray(item.shell_blocks) ? item.shell_blocks.length : undefined,
                firstShellBlockName: firstShellBlock && firstShellBlock.name,
                firstShellBlockCmd: firstShellBlock && firstShellBlock.cmd,
                firstShellBlockArgs: firstShellBlock && firstShellBlock.args,
                configRole: item && item.config ? item.config.role : undefined
            };
            return `<li><strong>#${index + 1}</strong> <code>command=${escapeHtml(String(sample.command ?? 'undefined'))}</code>, <code>shell_blocks.length=${escapeHtml(String(sample.shellBlocksLength ?? 'undefined'))}</code>, <code>firstShellBlock.name=${escapeHtml(String(sample.firstShellBlockName ?? 'undefined'))}</code>, <code>firstShellBlock.cmd=${escapeHtml(String(sample.firstShellBlockCmd ?? 'undefined'))}</code>, <code>firstShellBlock.args=${escapeHtml(String(sample.firstShellBlockArgs ?? 'undefined'))}</code>, <code>config.role=${escapeHtml(String(sample.configRole ?? 'undefined'))}</code></li>`;
        }).join('')
        : '<li><em>No sample items available</em></li>';

    if (shouldRenderAgentCommandTable) {
        const rows = AGENT_COMMAND.flatMap(c => {
            const role = c.config && c.config.role;
            const normalizedRoles = role == null
                ? []
                : String(role)
                    .split(',')
                    .map(item => item.trim());
            const availableTo = normalizedRoles.length > 0
                ? escapeHtml(normalizedRoles.join(', '))
                : '<i>all</i>';
            const shellBlocks = Array.isArray(c && c.shell_blocks) ? c.shell_blocks : [];

            return shellBlocks.map(shellBlock => {
                const commandName = escapeHtml(String(c && c.command ? c.command : ''));
                const shellBlockName = escapeHtml(String(shellBlock && shellBlock.name ? shellBlock.name : ''));
                const commandLabel = shellBlockName
                    ? `${commandName}_${shellBlockName}`
                    : commandName;
                const shellCmd = escapeHtml(String(shellBlock && shellBlock.cmd ? shellBlock.cmd : ''));

                return `<tr><td><strong>${commandLabel}</strong></td><td><code>${shellCmd}</code></td><td>${availableTo}</td></tr>`;
            });
        }).join('');
        const tableHtml = `<p><strong>Available shell commands:</strong></p><table><thead><tr><th>Command</th><th>Shell</th><th>Available&nbsp;to</th></tr></thead><tbody>${rows}</tbody></table>`;

        window._chatInstance.addMessage({message: tableHtml, type: 'html', is_final: true}, 'html');
    }

    if (typeof MCP_COMMAND !== 'undefined' && Array.isArray(MCP_COMMAND) && MCP_COMMAND.length > 0) {
        const rows = MCP_COMMAND.map(c => {
            const transport = (c.config && c.config.type) ? c.config.type : 'cli';
            const url = (c.config && c.config.url) ? ` <small>(${escapeHtml(c.config.url)})</small>` : '';
            return `<tr><td><strong>${escapeHtml(c.command)}</strong></td><td><code>${escapeHtml(c.cmd)}</code></td><td>${escapeHtml(transport)}${url}</td></tr>`;
        }).join('');
        const tableHtml = `<p><strong>Available MCP:</strong></p><table><thead><tr><th>Server</th><th>Command</th><th>Transport</th></tr></thead><tbody>${rows}</tbody></table>`;
        window._chatInstance.addMessage({message: tableHtml, type: 'html', is_final: true}, 'html');
    }
});