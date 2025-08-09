import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

// 注册 PIXI ticker
// @ts-ignore - 忽略类型错误，因为我们知道在运行时这是正确的
Live2DModel.registerTicker(PIXI.Ticker);

let currentModel: any = null;
let lipSyncAnimationFrame: number | null = null;
let isSpeaking = false;

export async function initializeLive2D(canvas: HTMLCanvasElement) {
    if (!canvas) {
        console.error('错误：找不到 Canvas 元素！');
        return;
    }

    const app = new PIXI.Application({
        view: canvas,
        width: 400,
        height: 600,
        transparent: true,
        backgroundAlpha: 0,
        autoDensity: true,
        resolution: window.devicePixelRatio || 2,
        antialias: true,
    } as any); // 使用any类型绕过类型检查

    const modelPath = '/live2d_models/Nagisa/lolisa.model3.json';

    try {
        console.log('开始加载 Live2D 模型...');
        const model = await Live2DModel.from(modelPath);
        console.log('Live2D 模型加载成功！');

        currentModel = model;

        // 打印模型结构
        console.log('模型结构:', {
            hasInternalModel: !!currentModel.internalModel,
            hasParameters: !!currentModel.parameters,
            modelType: currentModel,
            availableMethods: Object.getOwnPropertyNames(Object.getPrototypeOf(currentModel))
        });

        if (currentModel.internalModel) {
            const params = currentModel.internalModel.coreModel.parameters;
            console.log('所有参数:', params);
        }

        app.stage.addChild(model);

        // 调整模型大小和位置
        const screenWidth = app.screen.width;
        const screenHeight = app.screen.height;
        
        let scale = Math.min(
            screenWidth / model.width,
            screenHeight / model.height
        ) * 1.2;
        
        if (!isFinite(scale) || scale <= 0) {
            scale = 0.1;
        }
        
        model.scale.set(scale);
        
        const scaledWidth = model.width;
        const scaledHeight = model.height * 0.7;
        
        model.x = (screenWidth - scaledWidth) / 2;
        model.y = (screenHeight - scaledHeight) / 2 - 100;

        // 设置初始动作
        await playInitialMotion(model);

        return model;
    } catch (error) {
        console.error('加载或处理 Live2D 模型时出错:', error);
        displayModelError(canvas, modelPath, error);
    }
}

export function startLipSync(analyser: AnalyserNode) {
    if (!currentModel) {
        console.error('模型未初始化，无法进行嘴型同步');
        return;
    }

    // 标记正在说话
    isSpeaking = true;

    // 停止之前的动画帧
    if (lipSyncAnimationFrame) {
        cancelAnimationFrame(lipSyncAnimationFrame);
    }

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    
    function updateLipSync() {
        if (!isSpeaking) return;

        try {
            // 获取音频数据
            analyser.getByteFrequencyData(dataArray);
            
            // 计算音量平均值
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            
            // 将音量映射到嘴型参数范围 (0-1)，并增加灵敏度
            const normalizedValue = Math.min(average / 64, 1) * 0.6; // 将最大值限制在0.5，使嘴型开合更自然

            if (currentModel.internalModel && currentModel.internalModel.coreModel) {
                const model = currentModel.internalModel.coreModel;
                
                // 打印当前可用的参数
                if (!currentModel._parametersLogged) {
                    currentModel._parametersLogged = true;
                }

                // 尝试设置嘴型参数
                try {
                    // 设置多个可能的嘴型相关参数
                    const mouthParams = [
                        'PARAM_MOUTH_OPEN_Y',  // 嘴巴开合
                        'ParamMouthOpenY',     // 备用参数名
                        'MouthOpenY'           // 备用参数名
                    ];

                    let paramFound = false;
                    mouthParams.forEach(param => {
                        if (typeof model.setParameterValueById === 'function') {
                            try {
                                model.setParameterValueById(param, normalizedValue);
                                paramFound = true;
                            } catch (e) {
                                // 忽略参数不存在的错误
                            }
                        }
                    });

                    if (!paramFound) {
                        console.warn('未找到有效的嘴型参数，请检查模型参数列表');
                    }

                } catch (e) {
                    console.warn('设置嘴型参数失败:', e);
                }
            }
        } catch (error) {
            console.error('更新嘴型参数失败:', error);
        }

        // 继续下一帧
        lipSyncAnimationFrame = requestAnimationFrame(updateLipSync);
    }

    // 开始动画循环
    updateLipSync();
}

export function stopLipSync() {
    isSpeaking = false;
    if (lipSyncAnimationFrame) {
        cancelAnimationFrame(lipSyncAnimationFrame);
        lipSyncAnimationFrame = null;
    }

    // 重置嘴型参数
    if (currentModel && currentModel.internalModel && currentModel.internalModel.coreModel) {
        const model = currentModel.internalModel.coreModel;
        try {
            ['PARAM_MOUTH_OPEN_Y', 'ParamMouthOpenY', 'MouthOpenY'].forEach(param => {
                if (typeof model.setParameterValueById === 'function') {
                    model.setParameterValueById(param, 0);
                }
            });
        } catch (e) {
            console.warn('重置嘴型参数失败:', e);
        }
    }
}

async function playInitialMotion(model: any) {
    try {
        await model.motion('neutral');
    } catch (error) {
        console.warn('播放初始动作失败:', error);
    }
}

function displayModelError(canvas: HTMLCanvasElement, modelPath: string, error: any) {
    const errorDiv = document.createElement('div');
    errorDiv.innerText = `无法加载模型: ${modelPath}. 请检查路径和模型文件是否完好。\n错误: ${error.message}`;
    errorDiv.style.color = 'red';
    canvas.parentNode?.insertBefore(errorDiv, canvas.nextSibling);
}

export function playMotion(motionName: string) {
    if (!currentModel) {
        console.error('模型未初始化，无法播放动作');
        return;
    }

    try {
        console.log(`尝试播放动作: ${motionName}`);
        currentModel.motion(motionName);
    } catch (error) {
        console.error(`播放动作 ${motionName} 失败:`, error);
    }
}

export function enableLive2DDrag(canvas: HTMLCanvasElement) {
    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    canvas.style.position = 'fixed'; // 保证可拖动
    canvas.style.cursor = 'grab';

    canvas.addEventListener('mousedown', (e) => {
        isDragging = true;
        offsetX = e.clientX - canvas.offsetLeft;
        offsetY = e.clientY - canvas.offsetTop;
        canvas.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            canvas.style.left = (e.clientX - offsetX) + 'px';
            canvas.style.top = (e.clientY - offsetY) + 'px';
        }
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
        canvas.style.cursor = 'grab';
    });
} 