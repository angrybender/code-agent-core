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

const ON_USER_SCROLL_SEMAPHORE_TTL = 30; // seconds

class SimpleChat {
    constructor() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.controlFlowStopBtn = document.getElementById('control-flow-stop');
        this.messageInput = document.getElementById('message-input');
        this.eventSource = null;

        this.ON_USER_SCROLL_SEMAPHORE = false;
        this.ON_USER_SCROLL_SEMAPHORE_TIMER = null;

        this.IS_LAST_MESSAGE_SUCCESS = false;

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
    }

    onEndConversation() {
        if (this.IS_LAST_MESSAGE_SUCCESS) {
            this.messageInput.value = "";
        }

        this.controlFlowStopBtn.style.display = 'none';
        this.controlFlowStopBtn.classList.remove('loading');

        this.messageInput.style.display = 'block';
        document.getElementById('main-wrapper').classList.remove('conversation-active');
        window.scrollTo(0, document.body.scrollHeight);
    }

    setupEventListeners() {
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

        // Handle user's scroll by mouse and turn off/on autoscroll
        document.body.addEventListener('wheel', (event) => {
            if (this.ON_USER_SCROLL_SEMAPHORE_TIMER) {
                clearTimeout(this.ON_USER_SCROLL_SEMAPHORE_TIMER);
            }

            // if User scroll to bottom - turn on autoscroll
            const scrollTop = window.scrollY;
            const windowHeight = window.innerHeight;
            const documentHeight = document.documentElement.scrollHeight;
            const scrollPercentage = (scrollTop + windowHeight) / documentHeight;
            if (scrollPercentage > 0.95) {
                this.ON_USER_SCROLL_SEMAPHORE = false;
                return true;
            }

            this.ON_USER_SCROLL_SEMAPHORE = true;
            this.ON_USER_SCROLL_SEMAPHORE_TIMER = setTimeout(() => {
                this.ON_USER_SCROLL_SEMAPHORE = false;
                this.ON_USER_SCROLL_SEMAPHORE_TIMER = null;
            }, ON_USER_SCROLL_SEMAPHORE_TTL*1000);
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
            case 'status':
                this.updateStatus(data.message, 'connected');
                break;
            case 'end':
                this.onEndConversation();
                break;
            case 'error':
                this.addMessage(data.message, 'error', data.timestamp);
                this.IS_LAST_MESSAGE_SUCCESS = false;
                break;
            case 'warning':
                this.addMessage(data.message, 'warning', data.timestamp);
                this.IS_LAST_MESSAGE_SUCCESS = false;
                break;
            case 'heartbeat':
                break;
            case 'markdown':
                this.addMessage(data.message, 'markdown', data.timestamp);
                this.IS_LAST_MESSAGE_SUCCESS = true;
                break;
            case 'html':
                this.addMessage(data.message, 'html', data.timestamp);
                this.IS_LAST_MESSAGE_SUCCESS = true;
                break;
            default:
                this.addMessage(data.message, 'bot', data.timestamp);
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

        // clear response container
        this.messagesContainer.innerHTML = '';

        // Add user message to chat
        this.addMessage(message, 'user');

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
            else {
                this.onStartConversation();
            }
        } catch (error) {
            this.addMessage('Error: Failed to send message, [' + error.message + ']', 'error');
        }
    }

    addMessage(message, type, timestamp) {
        let messageDivClassName = `message ${type}-message`;

        if (type === 'user') {
            type = 'html';
            message = `<pre>${message}</pre>`;
            messageDivClassName = "message html-message user-message";
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = messageDivClassName;

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

        if (!this.ON_USER_SCROLL_SEMAPHORE) {
            window.scrollTo(0, document.body.scrollHeight);
        }
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