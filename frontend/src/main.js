import './style.css';
import { initializeLive2D } from './live2d.js';
import { sendMessage } from './chat.js';
import { initializeUI, getCurrentMessage, clearInput } from './ui.js';

async function main() {
    // Initialize UI components
    const { userInput, sendButton } = initializeUI();

    // Set up event listeners
    sendButton.addEventListener('click', async () => {
        const message = getCurrentMessage();
        if (message) {
            await sendMessage(message);
            clearInput();
        }
    });

    userInput.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            const message = getCurrentMessage();
            if (message) {
                await sendMessage(message);
                clearInput();
            }
        }
    });

    // Initialize Live2D model
    await initializeLive2D('live2d-canvas');
}

// Execute main function
main().catch(console.error);
