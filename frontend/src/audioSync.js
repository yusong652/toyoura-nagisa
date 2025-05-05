import { startLipSync, stopLipSync } from './live2d.js';

let audioContext = null;
function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

export function playAudioWithLipSync(audioBase64) {
    try {
        const audioBuffer = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0)).buffer;
        const context = getAudioContext();
        context.decodeAudioData(audioBuffer, (decodedData) => {
            const source = context.createBufferSource();
            source.buffer = decodedData;
            const analyser = context.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            analyser.connect(context.destination);

            startLipSync(analyser);
            source.start(0);
            source.onended = () => {
                stopLipSync();
                source.disconnect();
                analyser.disconnect();
            };
        }, (err) => {
            throw new Error('音频解码失败: ' + err);
        });
    } catch (error) {
        console.error('音频播放或嘴型同步失败:', error);
        stopLipSync();
    }
} 