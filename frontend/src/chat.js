import { playTextAsSpeech } from './tts.js';
import { displayMessage } from './ui.js';
import { clearInput } from './ui.js';
import { startLipSync, stopLipSync } from './live2d.js';

const CHAT_API_URL = '/api/chat';

export async function sendMessage(messageText) {
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
            body: JSON.stringify({ text: messageText }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse response
        const data = await response.json();

        // Handle response
        if (data.response) {
            displayMessage(data.response, 'bot');
            
            // 播放语音并同步嘴型
            try {
                console.log('准备播放语音和同步嘴型');
                await playTextAsSpeech(data.response, (analyser) => {
                    console.log('收到音频分析器，开始嘴型同步');
                    startLipSync(analyser);
                });
                console.log('语音播放结束，停止嘴型同步');
                stopLipSync();
            } catch (error) {
                console.error('语音播放或嘴型同步失败:', error);
                stopLipSync(); // 确保在出错时也停止嘴型同步
            }
        } else {
            displayMessage('Error: No response field in reply.', 'error');
        }

    } catch (error) {
        console.error('Error sending message:', error);
        displayMessage(`Error: ${error.message}`, 'error');   
        stopLipSync(); // 确保在出错时也停止嘴型同步
    }
} 