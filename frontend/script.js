// 获取 DOM 元素
const chatbox = document.getElementById('chatbox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// 后端 API 地址
const apiUrl = 'http://127.0.0.1:8000/api/chat'; // 确保端口号与后端运行端口一致

// 发送消息的函数
async function sendMessage() {
    const messageText = userInput.value.trim(); // 获取输入并去除首尾空格

    if (messageText === '') {
        return; // 如果消息为空，则不执行任何操作
    }

    // 1. 在聊天框显示用户发送的消息
    displayMessage(messageText, 'user');

    // 清空输入框
    userInput.value = '';

    try {
        // 2. 发送消息到后端 API
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            // 将消息包装成后端需要的格式
            body: JSON.stringify({ text: messageText }),
        });

        // 检查响应是否成功
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // 解析后端返回的 JSON 数据
        const data = await response.json();

        // 3. 在聊天框显示后端返回的响应
        if (data.response) {
             displayMessage(data.response, 'bot');
        } else {
             displayMessage('Error: No response field in reply.', 'error');
        }

    } catch (error) {
        // 4. 如果发生错误，显示错误信息
        console.error('Error sending message:', error);
        displayMessage(`Error: ${error.message}`, 'error');
    }
}

// 在聊天框显示消息的辅助函数
function displayMessage(message, sender) {
    const messageElement = document.createElement('p');
    messageElement.textContent = message;
    messageElement.classList.add('message', `${sender}-message`); // 添加 CSS 类用于样式化 (可选)
    chatbox.appendChild(messageElement);
    // 滚动到底部
    chatbox.scrollTop = chatbox.scrollHeight;
}

// 为发送按钮添加点击事件监听器
sendButton.addEventListener('click', sendMessage);

// (可选) 为输入框添加回车键监听器
userInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
