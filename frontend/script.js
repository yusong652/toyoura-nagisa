// 获取 DOM 元素
const chatbox = document.getElementById('chatbox');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');

// 后端 API 地址
const CHAT_API_URL = '/api/chat'; // 确保端口号与后端运行端口一致
const TTS_API_URL = '/api/tts'; // 确保端口号与后端运行端口一致
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
        const response = await fetch(CHAT_API_URL, {
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
             await playTextAsSpeech(data.response);
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

async function playTextAsSpeech(textToSpeech) {
    console.log(`[TTS] Requesting speech for: "${textToSpeech.substring(0, 50)}..."`);

    // 使用 try...catch 包裹，处理可能发生的错误
    try {
        // --- Step 1: Fetch audio from /api/tts ---
        const ttsResponse = await fetch(TTS_API_URL, {
            method: 'POST', // 指定请求方法为 POST
            headers: {
                'Content-Type': 'application/json', // 告诉服务器我们发送的是 JSON
            },
            body: JSON.stringify({ text: textToSpeech }) // 将要合成的文本打包成 JSON 字符串
        });
        // --- Step 2: Check if the response status is OK (200-299) ---
        if (!ttsResponse.ok) {
            // 如果状态码不是 2xx，说明请求失败了
            let errorMsg = `TTS request failed with status ${ttsResponse.status}`;
            try {
                // 尝试从响应体读取更详细的错误信息 (我们后端出错时会返回文本)
                const errorBody = await ttsResponse.text();
                errorMsg += `: ${errorBody}`;
            } catch (e) {
                // 读取响应体也可能失败，忽略它
                console.warn("Could not read error body from failed TTS response", e);
            }
            // 抛出一个错误，让外面的 catch 块来处理
            throw new Error(errorMsg);
        }

        // 如果代码能执行到这里，说明 ttsResponse.ok 是 true，请求成功！
        console.log("[TTS] Received successful response from /api/tts (status: " + ttsResponse.status + ")");
        // --- Step 3: Get audio Blob ---
        const audioBlob = await ttsResponse.blob();
        // 打印一下获取到的 Blob 信息，方便调试
        console.log(`[TTS] Received audio blob, type: ${audioBlob.type}, size: ${audioBlob.size}`);

        // --- Step 4: Create Object URL ---
        const audioUrl = URL.createObjectURL(audioBlob);
        // 打印出来看看，这个 URL 看起来会像 'blob:http://...'
        console.log(`[TTS] Created Object URL: ${audioUrl}`);

        // --- Step 5: Create Audio object and play ---
        const audio = new Audio(audioUrl); // 用这个 URL 创建 Audio 对象
        console.log("[TTS] Audio object created, attempting to play...");
        audio.play(); // 命令浏览器播放这个音频！

        // --- Step 6: Setup cleanup (onended, onerror) ---
        // 监听播放结束事件
        audio.onended = () => {
            URL.revokeObjectURL(audioUrl); // 释放内存
            console.log("[TTS] Audio playback finished, Object URL revoked.");
        };

        // 监听播放错误事件
        audio.onerror = (e) => {
            console.error("[TTS] Error playing audio:", e);
            URL.revokeObjectURL(audioUrl); // 出错也要释放！
            // 这里可以考虑给用户一个“播放失败”的提示
        };

    } catch (error) {
        // 如果过程中出现任何错误，在这里捕获并打印到控制台
        console.error("Error during text-to-speech playback:", error);
        // 未来可以考虑在界面上给用户一个失败提示
    }
}

// 为发送按钮添加点击事件监听器
sendButton.addEventListener('click', sendMessage);

// (可选) 为输入框添加回车键监听器
userInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
