// UI Elements cache
let chatbox = null;
let userInput = null;
let sendButton = null;

let typingInterval = null;

// 记录上一次Nagisa消息内容
let lastBotMessage = '';

export function initializeUI() {
    // Get DOM elements
    chatbox = document.getElementById('chatbox');
    userInput = document.getElementById('userInput');
    sendButton = document.getElementById('sendButton');

    // 文件上传相关元素
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        // 点击加号按钮时触发文件选择
        document.getElementById('addFileBtn')?.addEventListener('click', () => {
            fileInput.click();
        });

        // 渲染缩略图的函数
        function renderFilePreview() {
            const previewArea = document.getElementById('filePreviewArea');
            if (!previewArea) return;
            previewArea.innerHTML = '';
            (window.uploadCache || []).forEach((file, idx) => {
                const fileBox = document.createElement('div');
                fileBox.className = 'file-thumb-box';
                // 让删除按钮和缩略图紧贴在一起（右上角）
                fileBox.style.display = 'inline-block';
                fileBox.style.position = 'relative';
                fileBox.style.width = '68px';
                fileBox.style.height = '68px';
                fileBox.style.margin = '4px';
                // 创建删除按钮
                const delBtn = document.createElement('button');
                delBtn.className = 'file-thumb-del';
                delBtn.textContent = '×';
                delBtn.onclick = () => {
                    window.uploadCache.splice(idx, 1);
                    renderFilePreview();
                    fileInput.value = '';
                };
                // 确保删除按钮绝对定位在缩略图右上角
                delBtn.style.position = 'absolute';
                delBtn.style.top = '4px';
                delBtn.style.right = '4px';
                delBtn.style.zIndex = '10';
                fileBox.appendChild(delBtn);

                if (file.type.startsWith('image/')) {
                    const img = document.createElement('img');
                    img.className = 'file-thumb-img';
                    img.alt = file.name;
                    img.title = file.name;
                    img.style.width = '64px';
                    img.style.height = '64px';
                    img.style.objectFit = 'cover';
                    img.style.borderRadius = '8px';
                    img.style.margin = '4px';
                    const reader = new FileReader();
                    reader.onload = function(ev) {
                        img.src = ev.target.result;
                    };
                    reader.readAsDataURL(file);
                    fileBox.appendChild(img);
                } else {
                    // 非图片文件显示文件名和图标
                    const icon = document.createElement('span');
                    icon.textContent = '📄';
                    icon.style.fontSize = '32px';
                    icon.style.marginRight = '6px';
                    const name = document.createElement('span');
                    name.textContent = file.name;
                    name.style.fontSize = '13px';
                    name.style.verticalAlign = 'middle';
                    fileBox.appendChild(icon);
                    fileBox.appendChild(name);
                }
                previewArea.appendChild(fileBox);
            });
        }
        // 选择文件时，合并到uploadCache并渲染
        fileInput.addEventListener('change', (e) => {
            if (!window.uploadCache) window.uploadCache = [];
            const newFiles = Array.from(e.target.files);
            newFiles.forEach(f => {
                if (!window.uploadCache.some(x => x.name === f.name && x.size === f.size)) {
                    window.uploadCache.push(f);
                }
            });
            renderFilePreview();
            console.log('已选择文件:', window.uploadCache);
        });
        // 初始化时渲染（防止残留）
        renderFilePreview();
        // 挂载到window，便于外部调用清除
        window.renderFilePreview = renderFilePreview;
    }

    if (!chatbox || !userInput || !sendButton) {
        throw new Error('Required UI elements not found!');
    }

    return {
        chatbox,
        userInput,
        sendButton
    };
}

export function displayMessage(message, sender) {
    if (!chatbox) {
        throw new Error('Chatbox not initialized! Call initializeUI first.');
    }

    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message', sender);

    // 创建头像元素
    const avatar = document.createElement('img');
    avatar.classList.add('avatar');
    
    if (sender === 'user') {
        avatar.src = '/public/user-avatar.jpg'; // 默认用户头像
        avatar.alt = 'User';
    } else {
        avatar.src = '/public/Nagisa_avatar.jpg'; // Nagisa的头像
        avatar.alt = 'Nagisa';
    }

    // 头像悬停弹窗介绍
    avatar.addEventListener('mouseenter', (e) => {
        const tooltip = document.createElement('div');
        tooltip.className = 'avatar-tooltip';
        if (sender === 'user') {
            tooltip.textContent = 'User\n昵称：你自己\n简介：这是你在本聊天中的形象，可以自定义头像和昵称哦~';
        } else {
            tooltip.textContent = 'Toyoura Nagisa\n性格：元气、可爱、黏人\n爱好：和你聊天、卖萌撒娇\n简介：Nagisa是你的AI虚拟伙伴，喜欢陪伴你、和你互动！';
        }
        document.body.appendChild(tooltip);
        // 定位到头像左侧或右侧
        const rect = avatar.getBoundingClientRect();
        if (sender === 'user') {
            tooltip.style.left = (rect.left - tooltip.offsetWidth - 10) + 'px';
            tooltip.style.top = (rect.top - 10) + 'px';
        } else {
            tooltip.style.left = (rect.right + 10) + 'px';
            tooltip.style.top = (rect.top - 10) + 'px';
        }
    });
    avatar.addEventListener('mouseleave', () => {
        const tooltip = document.querySelector('.avatar-tooltip');
        if (tooltip) tooltip.remove();
    });

    // 创建消息内容容器
    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');

    // 设置消息文本
    messageContent.textContent = message;

    // 根据发送者调整布局
    if (sender === 'user') {
        messageContainer.appendChild(messageContent);
        messageContainer.appendChild(avatar);
        // 添加已读提示容器
        const readDiv = document.createElement('div');
        readDiv.className = 'read-receipt';
        readDiv.style.display = 'none';
        readDiv.innerHTML = '<span>已读</span>';
        messageContainer.appendChild(readDiv);
        // 0.5秒后显示
        setTimeout(() => {
            readDiv.style.display = 'block';
        }, 500);
    } else {
        messageContainer.appendChild(avatar);
        // 创建一个包裹气泡和时间的容器，使时间戳能紧贴气泡下方左对齐
        const bubbleWrapper = document.createElement('div');
        bubbleWrapper.style.display = 'inline-block';
        bubbleWrapper.style.verticalAlign = 'top';
        bubbleWrapper.style.position = 'relative';
        bubbleWrapper.style.maxWidth = '100%';

        bubbleWrapper.appendChild(messageContent);

        // 添加时间戳（紧贴气泡下方，左侧对齐）
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString();
        timeDiv.style.textAlign = 'left';
        timeDiv.style.margin = '4px 0 0 8px'; // 靠左微缩进，与气泡对齐
        timeDiv.style.width = 'auto';
        timeDiv.style.display = 'block';

        bubbleWrapper.appendChild(timeDiv);

        messageContainer.appendChild(bubbleWrapper);
    }

    chatbox.appendChild(messageContainer);
    
    // Scroll to bottom
    chatbox.scrollTop = chatbox.scrollHeight;
    
    return messageContainer;
}

export function updateLastMessage(message, sender) {
    if (!chatbox) {
        throw new Error('Chatbox not initialized! Call initializeUI first.');
    }

    // 获取最后一条消息元素
    const lastMessage = chatbox.lastElementChild;
    
    if (lastMessage && lastMessage.classList.contains(sender)) {
        // 更新现有消息内容
        const messageContent = lastMessage.querySelector('.message-content');
        if (messageContent) {
            if (sender === 'bot') {
                // 只对Nagisa流式消息做渐显
                // 找到新追加的部分
                let prev = lastBotMessage || '';
                let next = message || '';
                let commonLen = 0;
                while (commonLen < prev.length && prev[commonLen] === next[commonLen]) {
                    commonLen++;
                }
                const unchanged = next.slice(0, commonLen);
                const added = next.slice(commonLen);
                // 先显示未变部分
                messageContent.innerHTML = '';
                if (unchanged) {
                    messageContent.appendChild(document.createTextNode(unchanged));
                }
                // 渐显新内容
                if (added) {
                    // 每个字符单独渐显
                    [...added].forEach((ch, i) => {
                        setTimeout(() => {
                            const span = document.createElement('span');
                            span.className = 'fade-in';
                            span.textContent = ch;
                            messageContent.appendChild(span);
                            // 滚动到底部
                            chatbox.scrollTop = chatbox.scrollHeight;
                        }, i * 40); // 40ms一个字
                    });
                }
                lastBotMessage = next;
            } else {
                // 用户消息直接替换
                messageContent.textContent = message;
            }
        }
    } else {
        // 如果没有最后一条消息或不是对应发送者的消息，创建新消息
        displayMessage(message, sender);
        if (sender === 'bot') lastBotMessage = message;
    }
    // Scroll to bottom
    chatbox.scrollTop = chatbox.scrollHeight;
}

export function clearInput() {
    if (!userInput) {
        throw new Error('UserInput not initialized! Call initializeUI first.');
    }
    userInput.value = '';
}

export function getCurrentMessage() {
    if (!userInput) {
        throw new Error('UserInput not initialized! Call initializeUI first.');
    }
    return userInput.value.trim();
}

// 显示Nagisa思考中的loading动画
export function showLoading() {
    if (!chatbox) return;
    // 防止重复添加
    if (chatbox.querySelector('.loading-spinner')) return;
    const loadingContainer = document.createElement('div');
    loadingContainer.classList.add('message', 'bot', 'loading-message');
    const avatar = document.createElement('img');
    avatar.classList.add('avatar');
    avatar.src = '/public/Nagisa_avatar.jpg';
    avatar.alt = 'Nagisa';
    const spinner = document.createElement('div');
    spinner.classList.add('loading-spinner');
    // 动态"正在输入中..."文本
    const typingText = document.createElement('span');
    typingText.classList.add('typing-text');
    typingText.textContent = '正在输入中.';
    loadingContainer.appendChild(avatar);
    loadingContainer.appendChild(spinner);
    loadingContainer.appendChild(typingText);
    chatbox.appendChild(loadingContainer);
    chatbox.scrollTop = chatbox.scrollHeight;
    // 启动点号动画
    let dotCount = 1;
    typingInterval = setInterval(() => {
        dotCount = dotCount % 3 + 1;
        typingText.textContent = '正在输入中' + '.'.repeat(dotCount);
    }, 500);
}

// 移除Nagisa思考中的loading动画
export function hideLoading() {
    if (!chatbox) return;
    const loading = chatbox.querySelector('.loading-message');
    if (loading) {
        chatbox.removeChild(loading);
    }
    if (typingInterval) {
        clearInterval(typingInterval);
        typingInterval = null;
    }
}