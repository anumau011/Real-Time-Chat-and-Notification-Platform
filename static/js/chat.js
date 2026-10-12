class ChatManager {
    constructor() {
        console.log('Initializing ChatManager');
        this.currentRoomId = null;
        this.websocket = null;
        this.userEmail = document.querySelector('meta[name="user-email"]').content;
        console.log('User email:', this.userEmail);
        this.typingTimeout = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 5000;
        this.heartbeatInterval = null;
        this.initEventListeners();
        this.initEmojiPicker();
    }

    initEventListeners() {
        console.log('Setting up event listeners');
        document.querySelectorAll('.chatroom-item').forEach(item => {
            console.log('Adding click listener to chatroom item:', item.dataset.roomId);
            item.addEventListener('click', () => {
                console.log('Chatroom item clicked:', item.dataset.roomId);
                document.querySelectorAll('.chatroom-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                this.loadRoom(item.dataset.roomId);
            });
        });

        const messageForm = document.getElementById('message-form');
        if (messageForm) {
            console.log('Adding submit listener to message-form');
            messageForm.addEventListener('submit', (e) => {
                e.preventDefault();
                console.log('Message form submitted');
                this.sendMessage();
            });
        } else {
            console.error('message-form not found');
        }

        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            console.log('Adding input listener to message-input');
            messageInput.addEventListener('input', () => {
                console.log('Message input changed, value:', messageInput.value);
                if (this.websocket && messageInput.value.trim()) {
                    console.log('Sending typing event');
                    this.websocket.send(JSON.stringify({ typing: true }));
                    if (this.typingTimeout) clearTimeout(this.typingTimeout);
                    this.typingTimeout = setTimeout(() => {
                        if (this.websocket) {
                            console.log('Sending typing false event');
                            this.websocket.send(JSON.stringify({ typing: false }));
                        }
                    }, 2000);
                }
            });
        } else {
            console.error('message-input not found');
        }
    }

    initEmojiPicker() {
        console.log('Initializing emoji picker');
        const button = document.getElementById('emoji-button');
        const input = document.getElementById('message-input');
        if (!button || !input) {
            console.error('Emoji button or input not found:', { button, input });
            return;
        }

        const emojis = ['😀', '😂', '😍', '👍', '❤️', '🔥', '🎉', '🙏', '😊', '🥳', '🤔', '👏'];
        const picker = document.createElement('div');
        picker.className = 'emoji-picker hidden';
        picker.style.display = 'none';
        
        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-6 gap-2';
        
        emojis.forEach(emoji => {
            const span = document.createElement('span');
            span.className = 'text-xl cursor-pointer hover:bg-gray-100 rounded p-1 text-center';
            span.textContent = emoji;
            span.addEventListener('click', () => {
                console.log('Emoji selected:', emoji);
                input.value += emoji;
                input.focus();
                picker.style.display = 'none';
                picker.classList.add('hidden');
            });
            grid.appendChild(span);
        });
        
        picker.appendChild(grid);
        document.body.appendChild(picker);

        button.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log('Emoji button clicked');
            if (picker.style.display === 'none') {
                picker.style.display = 'block';
                picker.classList.remove('hidden');
                const rect = button.getBoundingClientRect();
                picker.style.bottom = `${window.innerHeight - rect.top + 10}px`;
                picker.style.right = `${window.innerWidth - rect.right}px`;
            } else {
                picker.style.display = 'none';
                picker.classList.add('hidden');
            }
        });

        document.addEventListener('click', (e) => {
            if (!picker.contains(e.target) && e.target !== button) {
                console.log('Closing emoji picker');
                picker.style.display = 'none';
                picker.classList.add('hidden');
            }
        });
    }

    async loadRoom(roomId) {
        console.log('Loading room:', roomId);
        if (this.currentRoomId === roomId) {
            console.log('Room already loaded, skipping');
            return;
        }
        this.currentRoomId = roomId;
        localStorage.setItem('selectedRoomId', roomId);
        history.replaceState(null, '', `?room=${roomId}`);

        const roomItem = document.querySelector(`.chatroom-item[data-room-id="${roomId}"]`);
        const chatHeader = document.getElementById('chat-header');
        const chatAvatar = document.getElementById('chat-avatar');
        const chatStatusDot = document.getElementById('chat-status-dot');
        
        if (roomItem) {
            console.log('Updating chat header for room:', roomId);
            chatHeader.textContent = roomItem.querySelector('.font-medium').textContent;
            if (!roomItem.querySelector('.bi-people-fill')) {
                const avatar = roomItem.querySelector('img');
                if (avatar) {
                    console.log('Updating chat avatar:', avatar.src);
                    chatAvatar.src = avatar.src;
                }
            }
        } else {
            console.error('Room item not found:', roomId);
        }

        const container = document.getElementById('messages-container');
        if (container) {
            console.log('Clearing messages container');
            container.innerHTML = '';
        } else {
            console.error('messages-container not found');
        }
        
        try {
            console.log('Fetching messages for room:', roomId);
            const response = await fetch(`/messages/${roomId}/`);
            console.log('Fetch messages response status:', response.status, response.statusText);
            const data = await response.json();
            
            if (data.success) {
                console.log('Messages fetched:', data.messages);
                data.messages.forEach(msg => this.renderMessage(msg));
                container.scrollTop = container.scrollHeight;
                
                if (data.participants && data.participants.length === 2) {
                    const otherUser = data.participants.find(p => p.email !== this.userEmail);
                    if (otherUser) {
                        console.log('Updating status dot for user:', otherUser.email, 'is_online:', otherUser.is_online);
                        chatStatusDot.className = `online-status ${otherUser.is_online ? 'online' : 'offline'}`;
                    }
                }

                // Mark messages as seen and clear unread count
                const unseenMessageIds = data.messages
                    .filter(msg => !msg.seen && msg.sender__email !== this.userEmail)
                    .map(msg => msg.id);
                if (unseenMessageIds.length > 0 && this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    console.log('Sending seen receipts for messages:', unseenMessageIds);
                    unseenMessageIds.forEach(id => {
                        this.websocket.send(JSON.stringify({ seen: true, message_id: id }));
                    });
                    this.updateUnreadCount(roomId, 0);
                }
            } else {
                console.error('Failed to load messages:', data.message);
                toastManager.buildToast()
                    .setMessage('Failed to load messages.')
                    .setType('danger')
                    .setPosition('top-right')
                    .show();
            }
        } catch (error) {
            console.error('Error fetching messages:', error);
            toastManager.buildToast()
                .setMessage('Error loading messages: ' + error.message)
                .setType('danger')
                .setPosition('top-right')
                .show();
        }
        
        console.log('Connecting WebSocket for room:', roomId);
        this.connectWebSocket();
    }

    connectWebSocket() {
        if (!this.currentRoomId) {
            console.error('No room ID set for WebSocket connection');
            return;
        }
        console.log('Attempting WebSocket connection for room:', this.currentRoomId);
        if (this.websocket && this.websocket.readyState !== WebSocket.CLOSED) {
            console.log('Closing existing WebSocket, readyState:', this.websocket.readyState);
            this.websocket.close();
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        this.websocket = new WebSocket(`${protocol}://${window.location.host}/ws/chat/${this.currentRoomId}/`);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected for room:', this.currentRoomId);
            this.reconnectAttempts = 0;
            // Start heartbeat
            this.startHeartbeat();
        };
        
        this.websocket.onmessage = (e) => {
            console.log('WebSocket message received:', e.data);
            const data = JSON.parse(e.data);
            
            if (data.type === 'message') {
                console.log('Rendering new message:', data);
                this.renderMessage({
                    id: data.message_id,
                    content: data.message,
                    sender__email: data.user,
                    created: data.timestamp,
                    seen: false,
                    seen_by: []
                });
                // Update unread count if message is not from current user and room is not open
                if (data.user !== this.userEmail && data.room_id !== this.currentRoomId) {
                    this.incrementUnreadCount(data.room_id);
                }
            } else if (data.type === 'typing') {
                console.log('Typing event received:', data.user, data.typing);
                this.showTypingIndicator(data.user, data.typing);
            } else if (data.type === 'seen') {
                console.log('Seen receipt received for message:', data.message_id, 'by user:', data.user);
                this.updateSeenReceipt(data.message_id, data.user);
            } else if (data.type === 'status') {
                console.log('Status update received:', data.user, data.status);
                const statusDot = document.getElementById('chat-status-dot');
                if (statusDot && data.user !== this.userEmail) {
                    statusDot.className = `online-status ${data.status === 'online' ? 'online' : 'offline'}`;
                }
            }
        };
        
        this.websocket.onclose = (e) => {
            console.log('WebSocket closed for room:', this.currentRoomId, 'code:', e.code, 'reason:', e.reason);
            this.stopHeartbeat();
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                console.log(`Reconnect attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts}`);
                toastManager.buildToast()
                    .setMessage('Connection lost. Reconnecting...')
                    .setType('warning')
                    .setPosition('top-right')
                    .show();
                this.reconnectAttempts++;
                setTimeout(() => this.connectWebSocket(), this.reconnectInterval);
            } else {
                console.error('Max reconnect attempts reached');
                toastManager.buildToast()
                    .setMessage('Failed to reconnect. Please refresh the page.')
                    .setType('danger')
                    .setPosition('top-right')
                    .show();
            }
        };
        
        this.websocket.onerror = (e) => {
            console.error('WebSocket error:', e);
        };
    }

    startHeartbeat() {
        console.log('Starting WebSocket heartbeat');
        this.stopHeartbeat(); // Clear any existing heartbeat
        this.heartbeatInterval = setInterval(() => {
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                console.log('Sending heartbeat ping');
                this.websocket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // Send ping every 30 seconds
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            console.log('Stopping WebSocket heartbeat');
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    renderMessage(message) {
        console.log('Rendering message:', message);
        const container = document.getElementById('messages-container');
        if (!container) {
            console.error('messages-container not found');
            return;
        }
        const isOwnMessage = message.sender__email === this.userEmail;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `flex ${isOwnMessage ? 'justify-end' : 'justify-start'} mb-4`;
        
        const messageDate = message.created ? new Date(message.created) : new Date();
        const timeString = messageDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageDiv.innerHTML = `
            <div class="max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${isOwnMessage ? 'bg-primary text-white' : 'bg-white border border-gray-200'}">
                ${!isOwnMessage ? `<div class="text-xs font-medium text-gray-500 mb-1">${message.sender__email}</div>` : ''}
                <div class="message-content">${message.content}</div>
                <div class="flex items-center justify-end mt-1 gap-1">
                    <div class="text-xs ${isOwnMessage ? 'text-white/80' : 'text-gray-400'}">
                        ${timeString}
                    </div>
                    ${isOwnMessage ? `
                        <div class="message-seen" data-message-id="${message.id}">
                            ${message.seen ? `
                                <svg viewBox="0 0 16 16" fill="#10B981">
                                    <path d="M6.5 11L2 6.5 3.5 5l3 3 5-5 1.5 1.5z"/>
                                </svg>
                                ${message.seen_by.length > 1 ? `
                                    <svg viewBox="0 0 16 16" fill="#10B981">
                                        <path d="M6.5 11L2 6.5 3.5 5l3 3 5-5 1.5 1.5z"/>
                                    </svg>
                                ` : ''}
                            ` : `
                                <svg viewBox="0 0 16 16" fill="#9CA3AF">
                                    <path d="M6.5 11L2 6.5 3.5 5l3 3 5-5 1.5 1.5z"/>
                                </svg>
                            `}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
        console.log('Message appended, scrolling to bottom');
        
        if (!isOwnMessage && this.currentRoomId && this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            console.log('Sending seen receipt for message:', message.id);
            this.websocket.send(JSON.stringify({ seen: true, message_id: message.id }));
        }
    }

    showTypingIndicator(user, isTyping) {
        console.log('Updating typing indicator for user:', user, 'isTyping:', isTyping);
        const indicator = document.getElementById('typing-indicator');
        if (!indicator) {
            console.error('typing-indicator not found');
            return;
        }
        
        if (isTyping) {
            indicator.innerHTML = `
                <div class="flex items-center gap-1">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                    <span>${user} is typing</span>
                </div>
            `;
        } else {
            indicator.innerHTML = '';
        }
    }

    updateSeenReceipt(messageId, user) {
        console.log('Updating seen receipt for message:', messageId, 'by user:', user);
        const seenIndicator = document.querySelector(`.message-seen[data-message-id="${messageId}"]`);
        if (seenIndicator) {
            seenIndicator.innerHTML = `
                <svg viewBox="0 0 16 16" fill="#10B981">
                    <path d="M6.5 11L2 6.5 3.5 5l3 3 5-5 1.5 1.5z"/>
                </svg>
                <svg viewBox="0 0 16 16" fill="#10B981">
                    <path d="M6.5 11L2 6.5 3.5 5l3 3 5-5 1.5 1.5z"/>
                </svg>
            `;
        } else {
            console.error('Seen indicator not found for message:', messageId);
        }
    }

    updateUnreadCount(roomId, count) {
        console.log('Updating unread count for room:', roomId, 'count:', count);
        const roomItem = document.querySelector(`.chatroom-item[data-room-id="${roomId}"]`);
        if (roomItem) {
            const unreadSpan = roomItem.querySelector('.unread-count');
            if (count > 0) {
                if (unreadSpan) {
                    unreadSpan.textContent = count;
                } else {
                    const newSpan = document.createElement('span');
                    newSpan.className = 'unread-count mt-1';
                    newSpan.textContent = count;
                    roomItem.querySelector('.flex-col').appendChild(newSpan);
                }
            } else if (unreadSpan) {
                unreadSpan.remove();
            }
        }
    }

    incrementUnreadCount(roomId) {
        console.log('Incrementing unread count for room:', roomId);
        const roomItem = document.querySelector(`.chatroom-item[data-room-id="${roomId}"]`);
        if (roomItem) {
            const unreadSpan = roomItem.querySelector('.unread-count');
            let count = unreadSpan ? parseInt(unreadSpan.textContent) || 0 : 0;
            count++;
            this.updateUnreadCount(roomId, count);
        }
    }

    sendMessage() {
        const input = document.getElementById('message-input');
        const message = input.value.trim();
        
        console.log('Attempting to send message:', message);
        if (!this.currentRoomId) {
            console.error('No room selected');
            toastManager.buildToast()
                .setMessage('Please select a chat room.')
                .setType('danger')
                .setPosition('top-right')
                .show();
            return;
        }
        if (!message) {
            console.error('Empty message');
            toastManager.buildToast()
                .setMessage('Message cannot be empty.')
                .setType('danger')
                .setPosition('top-right')
                .show();
            return;
        }
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected, readyState:', this.websocket ? this.websocket.readyState : 'null');
            toastManager.buildToast()
                .setMessage('Connection not established. Please try again.')
                .setType('danger')
                .setPosition('top-right')
                .show();
            return;
        }
        console.log('Sending message via WebSocket:', message);
        this.websocket.send(JSON.stringify({ message }));
        input.value = '';
        console.log('Message input cleared');
    }

    static refreshChatrooms() {
        console.log('Refreshing chatrooms');
        fetch('{% url "chat_home" %}', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log('Refreshing chatroom list with data:', data);
            const chatroomList = document.getElementById('chatroom-list');
            chatroomList.innerHTML = '';
            data.chatrooms.forEach(room => {
                const div = document.createElement('div');
                div.className = `chatroom-item p-3 rounded-lg hover:bg-gray-100 cursor-pointer flex items-center gap-3 ${room.id === this.currentRoomId ? 'active' : ''}`;
                div.dataset.roomId = room.id;
                div.innerHTML = `
                    <div class="relative">
                        ${room.is_group ? `
                            <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                                <i class="bi bi-people-fill"></i>
                            </div>
                        ` : `
                            <img src="${room.participants.find(p => p.email !== this.userEmail)?.profile_image || '{% static "img/avatar.png" %}'}" 
                                 class="w-10 h-10 rounded-full object-cover">
                        `}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="font-medium truncate">${room.display_name}</div>
                        <div class="text-xs text-gray-500 truncate">
                            ${room.last_message ? room.last_message.content.substring(0, 30) : 'No messages yet'}
                        </div>
                    </div>
                    <div class="text-xs text-gray-500 flex flex-col items-end">
                        ${room.last_message && room.last_message.created ? new Date(room.last_message.created).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--'}
                        ${room.unread_count > 0 ? `<span class="unread-count mt-1">${room.unread_count}</span>` : ''}
                    </div>
                `;
                div.addEventListener('click', () => {
                    document.querySelectorAll('.chatroom-item').forEach(i => i.classList.remove('active'));
                    div.classList.add('active');
                    this.loadRoom(room.id);
                });
                chatroomList.appendChild(div);
            });
        })
        .catch(error => {
            console.error('Error refreshing chatrooms:', error);
            toastManager.buildToast()
                .setMessage('Error refreshing chatrooms: ' + error.message)
                .setType('danger')
                .setPosition('top-right')
                .show();
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing ChatManager');
    const startChatForm = document.getElementById('start-chat-form');
    if (startChatForm) {
        console.log('Adding form-submitted listener to start-chat-form');
        startChatForm.addEventListener('form-submitted', (e) => {
            console.log('Start chat form-submitted event:', e.detail);
            if (e.detail.success && e.detail.room_id) {
                console.log('Loading new room:', e.detail.room_id);
                window.chatManager.loadRoom(e.detail.room_id);
                bootstrap.Modal.getInstance(document.getElementById('startChatModal')).hide();
                ChatManager.refreshChatrooms();
            }
        });
    } else {
        console.error('start-chat-form not found');
    }
});