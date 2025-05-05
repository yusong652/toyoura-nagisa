import { displayMessage } from './ui.js';
import { clearInput } from './ui.js';
import { playMotion } from './live2d.js';
import { playAudioWithLipSync } from './audioSync.js';

const CHAT_API_URL = '/api/chat';

// 创建 AudioContext 单例
let audioContext = null;
function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

export async function sendAndGetResponse(messageText) {
    if (messageText.trim() === '') {
        return;
    }

    // Display user message
    displayMessage(messageText, 'user');

    // Clear input immediately after displaying the message
    clearInput();

    try {
        // Send message to backend API
        const response = await fetch(CHAT_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messageText,
                session_id: localStorage.getItem('session_id') || undefined,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse response
        const data = await response.json();
        console.log('Received data object from backend:', data);

        if (data.detail) {
            throw new Error(data.detail);
        }
        if (!data.response || !data.keyword || !data.audio_data) {
            throw new Error('Invalid response format from server');
        }

        // Display bot response
        displayMessage(data.response, 'bot');

        // Handle motion keyword
        console.log('调用 playMotion，参数：', data.keyword);
        playMotion(data.keyword);

        // 播放音频并同步嘴型
        playAudioWithLipSync(data.audio_data);

    } catch (error) {
        console.error('Error sending message:', error);
        displayMessage(`Error: ${error.message}`, 'error');   
    }
} 