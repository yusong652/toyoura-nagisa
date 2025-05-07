// UI Elements cache
let chatbox = null;
let userInput = null;
let sendButton = null;

export function initializeUI() {
    // Get DOM elements
    chatbox = document.getElementById('chatbox');
    userInput = document.getElementById('userInput');
    sendButton = document.getElementById('sendButton');

    if (!chatbox || !userInput || !sendButton) {
        throw new Error('Required UI elements not found!');
    }

    return {
        chatbox,
        userInput,
        sendButton
    };
}

export function displayMessage(message, sender) {
    if (!chatbox) {
        throw new Error('Chatbox not initialized! Call initializeUI first.');
    }

    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message', sender);

    // 创建头像元素
    const avatar = document.createElement('img');
    avatar.classList.add('avatar');
    
    if (sender === 'user') {
        avatar.src = '/public/user-avatar.jpg'; // 默认用户头像
        avatar.alt = 'User';
    } else {
        avatar.src = '/public/Nagisa_avatar.jpg'; // Nagisa的头像
        avatar.alt = 'Nagisa';
    }

    // 创建消息内容容器
    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');
    messageContent.textContent = message;

    // 根据发送者调整布局
    if (sender === 'user') {
        messageContainer.appendChild(messageContent);
        messageContainer.appendChild(avatar);
    } else {
        messageContainer.appendChild(avatar);
        messageContainer.appendChild(messageContent);
    }

    chatbox.appendChild(messageContainer);
    
    // Scroll to bottom
    chatbox.scrollTop = chatbox.scrollHeight;
    
    return messageContainer;
}

export function updateLastMessage(message, sender) {
    if (!chatbox) {
        throw new Error('Chatbox not initialized! Call initializeUI first.');
    }

    // 获取最后一条消息元素
    const lastMessage = chatbox.lastElementChild;
    
    if (lastMessage && lastMessage.classList.contains(sender)) {
        // 更新现有消息内容
        const messageContent = lastMessage.querySelector('.message-content');
        if (messageContent) {
            messageContent.textContent = message;
        }
    } else {
        // 如果没有最后一条消息或不是对应发送者的消息，创建新消息
        displayMessage(message, sender);
    }
    
    // Scroll to bottom
    chatbox.scrollTop = chatbox.scrollHeight;
}

export function clearInput() {
    if (!userInput) {
        throw new Error('UserInput not initialized! Call initializeUI first.');
    }
    userInput.value = '';
}

export function getCurrentMessage() {
    if (!userInput) {
        throw new Error('UserInput not initialized! Call initializeUI first.');
    }
    return userInput.value.trim();
} 