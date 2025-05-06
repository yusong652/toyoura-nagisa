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

    const messageElement = document.createElement('p');
    messageElement.textContent = message;
    messageElement.classList.add('message', `${sender}-message`);
    chatbox.appendChild(messageElement);
    
    // Scroll to bottom
    chatbox.scrollTop = chatbox.scrollHeight;
    
    return messageElement;
}

export function updateLastMessage(message, sender) {
    if (!chatbox) {
        throw new Error('Chatbox not initialized! Call initializeUI first.');
    }

    // 获取最后一条消息元素
    const lastMessage = chatbox.lastElementChild;
    
    if (lastMessage && lastMessage.classList.contains(`${sender}-message`)) {
        // 更新现有消息
        lastMessage.textContent = message;
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