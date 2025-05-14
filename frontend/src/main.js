import './style.css';
import { initializeLive2D, enableLive2DDrag } from './live2d.js';
import { sendAndGetResponse } from './chat.js';
import { initializeUI, getCurrentMessage, clearInput } from './ui.js';
import { initializeChatHistory } from './chatHistory.js';

async function main() {
    // Initialize UI components
    const { userInput, sendButton } = initializeUI();
    console.log(userInput, sendButton);

    // Initialize chat history sidebar
    initializeChatHistory();

    // 自适应高度
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Set up event listeners
    sendButton.addEventListener('click', async () => {
        const message = getCurrentMessage();
        if (message) {
            await sendAndGetResponse(message);
            clearInput();
            userInput.style.height = 'auto'; // 发送后重置高度
        }
    });

    userInput.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const message = getCurrentMessage();
            if (message) {
                await sendAndGetResponse(message);
                clearInput();
                userInput.style.height = 'auto'; // 发送后重置高度
            }
        }
    });

    // Initialize Live2D model
    await initializeLive2D('live2d-canvas');
    // 启用拖动
    enableLive2DDrag();
}

// Execute main function
main().catch(console.error);
