// Chat History Sidebar Component
export function initializeChatHistory() {
    // Create sidebar structure
    const sidebar = document.createElement('div');
    sidebar.className = 'chat-history-sidebar';
    
    // Create header
    const header = document.createElement('div');
    header.className = 'chat-history-header';
    
    const title = document.createElement('div');
    title.className = 'chat-history-title';
    title.textContent = '聊天记录';
    
    const closeButton = document.createElement('button');
    closeButton.innerHTML = '×';
    closeButton.style.background = 'none';
    closeButton.style.border = 'none';
    closeButton.style.fontSize = '24px';
    closeButton.style.cursor = 'pointer';
    closeButton.style.color = 'var(--text-color)';
    
    header.appendChild(title);
    header.appendChild(closeButton);
    
    // Create chat history list
    const historyList = document.createElement('div');
    historyList.className = 'chat-history-list';
    
    // Add sample chat history items (for UI demonstration)
    const sampleItems = [
        { title: '日常对话', preview: '你好，今天天气真不错！' },
        { title: '学习讨论', preview: '关于Python的异步编程...' },
        { title: '闲聊', preview: '最近有什么好看的电影推荐吗？' }
    ];
    
    sampleItems.forEach(item => {
        const historyItem = document.createElement('div');
        historyItem.className = 'chat-history-item';
        
        const itemTitle = document.createElement('div');
        itemTitle.className = 'chat-history-item-title';
        itemTitle.textContent = item.title;
        
        const itemPreview = document.createElement('div');
        itemPreview.className = 'chat-history-item-preview';
        itemPreview.textContent = item.preview;
        
        historyItem.appendChild(itemTitle);
        historyItem.appendChild(itemPreview);
        historyList.appendChild(historyItem);
    });
    
    sidebar.appendChild(header);
    sidebar.appendChild(historyList);
    document.body.appendChild(sidebar);
    
    // Create toggle button
    const toggleButton = document.createElement('button');
    toggleButton.className = 'chat-history-toggle';
    toggleButton.innerHTML = '☰';
    document.body.appendChild(toggleButton);
    
    // Toggle sidebar
    toggleButton.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        document.body.classList.toggle('sidebar-open');
    });
    
    // Close sidebar
    closeButton.addEventListener('click', () => {
        sidebar.classList.remove('open');
        document.body.classList.remove('sidebar-open');
    });
    
    return {
        sidebar,
        toggleButton,
        closeButton
    };
} 