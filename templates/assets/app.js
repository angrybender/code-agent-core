var APP_HOST = '';
var IS_APP_ACTIVE = true;

function onPluginShow() {
    IS_APP_ACTIVE = true;
}
function onPluginHide() {
    IS_APP_ACTIVE = false;
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
        this.userMessage = document.getElementById('user-request');
        this.messageInput = document.getElementById('message-input');
        this.eventSource = null;

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.connectSSE();
    }

    setupEventListeners() {
        // Handle Ctrl+Enter to send message
        this.messageInput.addEventListener('keydown', (e) => {
            // Check for Ctrl (Windows/Linux) or Cmd (Mac)
            const isCtrlClick = e.ctrlKey || e.metaKey;

            if (isCtrlClick && e.key === 'Enter') {
                const message = this.messageInput.value.trim();
                e.preventDefault();

                if (message === '!!') {
                    this.sendControl('stop');
                }
                else {
                    this.sendMessage(message);
                }
            }
        });

        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = (this.messageInput.scrollHeight + 5) + 'px';
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
                            this.addMessage("Java error:" + errorMessage, 'error');
                        }
                    );
                } catch (e) {
                    this.addMessage("JS error:" + e, 'error');
                }

                return false;
            }
        });
    }

    connectSSE() {
        try {
            this.eventSource = new EventSource(APP_HOST + '/events?session_id=' + SESSION_ID);

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleServerMessage(data);
                } catch (e) {
                    this.addMessage("Error:" + e);
                }
            };

            this.eventSource.onerror = (error) => {
                this.updateStatus('Connection Error', 'disconnected');

                // Attempt to reconnect after 3 seconds
                setTimeout(() => {
                    if (this.eventSource.readyState === EventSource.CLOSED) {
                        this.connectSSE();
                    }
                }, 3000);
            };

        } catch (error) {
            this.updateStatus('Failed to Connect', 'disconnected');
        }
    }

    handleServerMessage(data) {
        switch (data.type) {
            case 'status':
                this.updateStatus(data.message, 'connected');
                break;
            case 'end':
                this.addMessage(data.message, 'finished', data.timestamp);
                break;
            case 'error':
                this.addMessage(data.message, 'error', data.timestamp);
                break;
            case 'warning':
                this.addMessage(data.message, 'warning', data.timestamp);
                break;
            case 'heartbeat':
                break;
            case 'markdown':
                this.addMessage(data.message, 'markdown', data.timestamp);
                break;
            case 'html':
                this.addMessage(data.message, 'html', data.timestamp);
                break;
            default:
                this.addMessage(data.message, 'bot', data.timestamp);
                break;
        }
    }

    async sendControl(command) {
        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

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
                this.addMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            this.addMessage('Error: Failed to send command, [' + error.message + ']', 'error');
        }
    }

    async sendMessage(message) {
        if (!message) {
            return;
        }

        // Add user message to chat
        this.addMessage(message, 'user');

        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';

        // clear response container
        this.messagesContainer.innerHTML = '';

        try {
            const response = await fetch(APP_HOST + '/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message, session_id: SESSION_ID })
            });

            const result = await response.json();

            if (result.status !== 'success') {
                this.addMessage(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            this.addMessage('Error: Failed to send message, [' + error.message + ']', 'error');
        }
    }

    addMessage(message, type, timestamp) {
        if (type === 'user') {
            this.userMessage.innerHTML = message;
            return;
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        const messageContent = document.createElement('div');
        if (type === 'markdown') {
            messageContent.innerHTML = marked.parse(message);
        }
        else if (type === 'html') {
            messageContent.innerHTML = message;
        }
        else {
            messageContent.textContent = message;
        }
        messageDiv.appendChild(messageContent);

        if (timestamp) {
            const timestampDiv = document.createElement('div');
            timestampDiv.className = 'timestamp';
            timestampDiv.textContent = new Date(timestamp * 1000).toLocaleTimeString();
            messageDiv.appendChild(timestampDiv);
        }

        this.messagesContainer.appendChild(messageDiv);
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    updateStatus(message, className) {
        try {
            JIDETransport(
                'jide_status//' + message + '//' + className,
                null,
                (errorCode, errorMessage) => {
                    this.addMessage("Java error:" + errorMessage, 'error');
                }
            );
        } catch (e) {
            this.addMessage("[updateStatus] JS error:" + e, 'error');
        }
    }
}

// Initialize chat when page loads
document.addEventListener('DOMContentLoaded', () => {
    new SimpleChat();
});