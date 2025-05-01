const TTS_API_URL = '/api/tts';

// 创建 AudioContext 单例
let audioContext = null;

function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

async function createAudioSource(audioBuffer) {
    const context = getAudioContext();
    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    return source;
}

async function setupAudioAnalyser() {
    const context = getAudioContext();
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    return analyser;
}

export async function playAudioAndGetAnalyser(audioBuffer) {
    try {
        const source = await createAudioSource(audioBuffer);
        const analyser = await setupAudioAnalyser();
        
        // 连接节点: source -> analyser -> destination
        source.connect(analyser);
        analyser.connect(getAudioContext().destination);

        // 开始播放
        source.start(0);

        // 返回分析器节点供外部使用
        return {
            analyser,
            source,
            // 添加播放结束的 Promise
            finished: new Promise(resolve => {
                source.onended = () => {
                    resolve();
                    // 断开连接
                    source.disconnect();
                    analyser.disconnect();
                };
            })
        };
    } catch (error) {
        console.error('设置音频播放和分析失败:', error);
        throw error;
    }
}

export async function playTextAsSpeech(textToSpeech, onAnalyserReady = null) {
    console.log(`[TTS] Requesting speech for: "${textToSpeech.substring(0, 50)}..."`);

    try {
        // 获取音频数据
        const ttsResponse = await fetch(TTS_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: textToSpeech })
        });

        if (!ttsResponse.ok) {
            let errorMsg = `TTS request failed with status ${ttsResponse.status}`;
            try {
                const errorBody = await ttsResponse.text();
                errorMsg += `: ${errorBody}`;
            } catch (e) {
                console.warn("Could not read error body from failed TTS response", e);
            }
            throw new Error(errorMsg);
        }

        // 获取音频数据
        const audioData = await ttsResponse.arrayBuffer();
        
        // 解码音频数据
        const audioBuffer = await getAudioContext().decodeAudioData(audioData);
        
        // 设置音频播放和分析器
        const { analyser, finished } = await playAudioAndGetAnalyser(audioBuffer);

        // 如果提供了回调函数，则传递分析器
        if (onAnalyserReady) {
            onAnalyserReady(analyser);
        }

        // 等待播放完成
        await finished;
        
        console.log("[TTS] Audio playback finished");

    } catch (error) {
        console.error("Error during text-to-speech playback:", error);
        throw error;
    }
} 