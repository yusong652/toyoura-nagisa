import { startLipSync, stopLipSync } from './live2d.js';

let audioContext = null;
let currentSource = null;
let currentAnalyser = null;

// 音频队列管理
let audioQueue = [];
let isPlaying = false;
let currentAudioPromise = null;

function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

// 停止当前正在播放的音频
export async function stopCurrentAudio() {
    if (currentSource) {
        try {
            currentSource.stop();
            currentSource.disconnect();
            currentAnalyser.disconnect();
            stopLipSync();
        } catch (e) {
            console.log('Audio already stopped');
        } finally {
            currentSource = null;
            currentAnalyser = null;
        }
    }
}

// 重置音频状态
export async function resetAudioState() {
    audioQueue = [];
    await stopCurrentAudio();
    isPlaying = false;
    currentAudioPromise = null;
}

// 添加音频到队列并开始播放
export function queueAndPlayAudio(audioData) {
    audioQueue.push(audioData);
    if (!isPlaying) {
        playNextAudio();
    }
}

// 播放队列中的下一个音频
async function playNextAudio() {
    if (isPlaying || audioQueue.length === 0) return;
    
    isPlaying = true;
    const audioData = audioQueue.shift();
    
    try {
        // 确保停止当前正在播放的音频
        await stopCurrentAudio();
        
        // 创建新的音频播放 Promise
        currentAudioPromise = playAudioWithLipSync(audioData);
        await currentAudioPromise;
    } catch (error) {
        console.error('Error playing audio:', error);
    } finally {
        isPlaying = false;
        currentAudioPromise = null;
        // 检查队列中是否还有音频需要播放
        if (audioQueue.length > 0) {
            playNextAudio();
        }
    }
}

export function playAudioWithLipSync(audioBase64) {
    return new Promise((resolve, reject) => {
        try {
            // 先停止当前正在播放的音频
            stopCurrentAudio();

            const audioBuffer = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0)).buffer;
            const context = getAudioContext();
            
            context.decodeAudioData(audioBuffer, (decodedData) => {
                try {
                    currentSource = context.createBufferSource();
                    currentSource.buffer = decodedData;
                    
                    currentAnalyser = context.createAnalyser();
                    currentAnalyser.fftSize = 256;
                    
                    currentSource.connect(currentAnalyser);
                    currentAnalyser.connect(context.destination);

                    startLipSync(currentAnalyser);
                    
                    currentSource.onended = () => {
                        stopLipSync();
                        currentSource.disconnect();
                        currentAnalyser.disconnect();
                        currentSource = null;
                        currentAnalyser = null;
                        resolve();
                    };

                    currentSource.onerror = (error) => {
                        stopLipSync();
                        currentSource.disconnect();
                        currentAnalyser.disconnect();
                        currentSource = null;
                        currentAnalyser = null;
                        reject(error);
                    };

                    currentSource.start(0);
                } catch (error) {
                    stopLipSync();
                    reject(error);
                }
            }, (err) => {
                stopLipSync();
                reject(new Error('音频解码失败: ' + err));
            });
        } catch (error) {
            stopLipSync();
            reject(error);
        }
    });
} 