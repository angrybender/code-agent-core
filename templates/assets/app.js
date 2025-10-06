var APP_HOST = '';

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
            if (e.ctrlKey && e.key === 'Enter') {
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
    }

    connectSSE() {
        try {
            this.eventSource = new EventSource(APP_HOST + '/events?session_id=' + SESSION_ID);

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleServerMessage(data);
                } catch (e) {
                    console.error('Error parsing SSE message:', e);
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
            console.error('Failed to connect SSE:', error);
            this.updateStatus('Failed to Connect', 'disconnected');
        }
    }

    handleServerMessage(data) {
        this.updateStatus('Connected', 'connected');

        switch (data.type) {
            case 'status':
                this.updateProjectStatus(data.message);
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
            console.error('Error sending command:', error);
            this.addMessage('Error: Failed to send command', 'error');
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
            console.error('Error sending message:', error);
            this.addMessage('Error: Failed to send message', 'error');
            this.updateStatus('Send Error', 'disconnected');
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
        document.querySelector('#connection-status').className = `status ${className}`;
        document.querySelector('#connection-status .connection').textContent = message;
    }

    updateProjectStatus(message) {
        document.querySelector('#connection-status .project').textContent = message;
    }
}

// Initialize chat when page loads
document.addEventListener('DOMContentLoaded', () => {
    new SimpleChat();
});