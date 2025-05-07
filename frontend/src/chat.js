import { displayMessage, updateLastMessage, clearInput, showLoading, hideLoading } from './ui.js';
import { playMotion } from './live2d.js';
import { queueAndPlayAudio, resetAudioState } from './audioSync.js';

const CHAT_API_URL = '/api/chat';
const CHAT_STREAM_API_URL = '/api/chat/stream';

export async function sendAndGetResponse(messageText) {
    if (messageText.trim() === '' && (!window.uploadCache || window.uploadCache.length === 0)) {
        return;
    }

    // 统一构造 messageData
    let messageData;
    const files = window.uploadCache || [];
    if (files.length > 0) {
        const filePromises = files.map(file => {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve({
                    name: file.name,
                    type: file.type,
                    data: reader.result
                });
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        });

        try {
            const fileData = await Promise.all(filePromises);
            messageData = JSON.stringify({
                text: messageText,
                files: fileData
            });
        } catch (e) {
            displayMessage('文件处理失败: ' + e.message, 'error');
            return;
        }
    } else {
        // 没有文件时也要构造 messageData
        messageData = JSON.stringify({
            text: messageText,
            files: []
        });
    }

    // 重置音频状态
    await resetAudioState();

    // Display user message
    displayMessage(messageText, 'user');

    // 清空上传文件缓存和缩略图
    window.uploadCache = [];
    if (window.renderFilePreview) window.renderFilePreview();

    // Clear input immediately after displaying the message
    clearInput();

    try {
        // 显示Nagisa思考中loading
        showLoading();
        // 创建新的 bot 消息容器
        // displayMessage('', 'bot'); // 这一行注释掉，loading替代

        // 使用流式 API
        const response = await fetch(CHAT_STREAM_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messageData,
                session_id: localStorage.getItem('session_id') || undefined,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentText = '';
        let currentKeyword = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.text) {
                            // 移除loading，显示Nagisa消息
                            if (document.querySelector('.loading-message')) {
                                hideLoading();
                                displayMessage('', 'bot');
                            }
                            // 更新文本显示
                            currentText += data.text;
                            updateLastMessage(currentText, 'bot');
                        }
                        
                        if (data.keyword && !currentKeyword) {
                            // 只在第一次收到关键词时触发动作
                            currentKeyword = data.keyword;
                            console.log('调用 playMotion，参数：', currentKeyword);
                            playMotion(currentKeyword);
                        }
                        
                        if (data.audio) {
                            // 将音频添加到队列并播放
                            queueAndPlayAudio(data.audio);
                        }
                    } catch (e) {
                        console.error('Error parsing SSE data:', e);
                    }
                }
            }
        }
        // 回复结束后确保loading被移除
        hideLoading();
    } catch (error) {
        console.error('Error sending message:', error);
        hideLoading();
        displayMessage(`Error: ${error.message}`, 'error');   
    }
} 