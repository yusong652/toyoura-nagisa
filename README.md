<!--
Language: zh
-->

# aiNagisa

一个具有多轮对话记忆和语音输出功能的 AI 聊天助手应用。

## 项目简介

aiNagisa 是一个智能聊天助手应用，具有以下特点：

- 基于大语言模型（LLM）的智能对话
- 支持多轮对话记忆和上下文管理
- 集成语音合成（TTS）功能
- 简洁直观的用户界面
- 支持会话历史记录存储

## 技术栈

### 后端
- Python 3.10+
- FastAPI - 高性能 Web 框架
- Uvicorn - ASGI 服务器
- uv - Python 包管理工具
- httpx - 异步 HTTP 客户端
- python-dotenv - 环境变量管理
- fish-audio-sdk - 语音合成 SDK

### 前端
- JavaScript (ES6+)
- HTML5
- CSS3

## 项目结构

```
aiNagisa/
├── backend/                # 后端代码
│   ├── app.py             # FastAPI 主应用
│   ├── run.py             # 启动脚本
│   ├── requirements.txt   # Python 依赖
│   ├── .env              # 环境变量配置
│   ├── .venv/            # Python 虚拟环境
│   ├── data/             # 数据存储目录
│   └── tts/              # 语音合成模块
├── frontend/              # 前端代码
│   ├── index.html        # 主页面
│   ├── style.css         # 样式文件
│   └── script.js         # 前端逻辑
├── .gitignore            # Git 忽略文件
└── README.md             # 项目说明
```

## 环境设置

### 1. 克隆仓库
```bash
git clone https://github.com/yusong652/aiNagisa.git
cd aiNagisa
```

### 2. 后端环境配置

#### 创建并激活虚拟环境
```bash
cd backend
# 使用 uv 创建虚拟环境
uv venv
# 或使用 Python 内置 venv
# python -m venv .venv

# 激活虚拟环境
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
```

#### 安装依赖
```bash
uv pip install -r requirements.txt
```

#### 配置环境变量
在 `backend` 目录下创建 `.env` 文件，包含以下必需的环境变量：

```env
# OpenAI API 配置
OPENAI_API_KEY=your_openai_api_key

# Fish Speech TTS 配置
FISH_SPEECH_API_KEY=your_fish_speech_api_key
FISH_SPEECH_MODEL_ID=your_model_id
```

### 3. 运行项目

确保后端虚拟环境已激活，然后在项目根目录运行：

```bash
python run.py
```

这将启动 FastAPI 服务器（默认地址：`http://127.0.0.1:8000`），该服务器同时托管前端文件。

在浏览器中访问 `http://127.0.0.1:8000` 即可使用应用。

## 特性

### 已实现
- [x] 基于 LLM 的智能对话
- [x] 多轮对话记忆
- [x] 语音合成输出
- [x] 会话历史记录存储
- [x] 角色定义（System Prompt）
- [x] 上下文长度限制

### 计划中
- [ ] 用户认证系统
- [ ] 多语言支持
- [ ] 自定义语音模型
- [ ] 移动端适配
- [ ] 离线模式支持

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

<!--
Language: en
-->

# aiNagisa

An AI-powered chat assistant with multi-turn conversation memory and voice output capabilities.

## Project Overview

aiNagisa is an intelligent chat assistant application with the following features:

- LLM-based intelligent conversation
- Multi-turn conversation memory and context management
- Integrated Text-to-Speech (TTS) functionality
- Clean and intuitive user interface
- Conversation history storage

## Tech Stack

### Backend
- Python 3.10+
- FastAPI - High-performance Web Framework
- Uvicorn - ASGI Server
- uv - Python Package Manager
- httpx - Async HTTP Client
- python-dotenv - Environment Variable Management
- fish-audio-sdk - Speech Synthesis SDK

### Frontend
- JavaScript (ES6+)
- HTML5
- CSS3

## Project Structure

```
aiNagisa/
├── backend/                # Backend code
│   ├── app.py             # FastAPI main application
│   ├── run.py             # Startup script
│   ├── requirements.txt   # Python dependencies
│   ├── .env              # Environment configuration
│   ├── .venv/            # Python virtual environment
│   ├── data/             # Data storage directory
│   └── tts/              # Speech synthesis module
├── frontend/              # Frontend code
│   ├── index.html        # Main page
│   ├── style.css         # Stylesheet
│   └── script.js         # Frontend logic
├── .gitignore            # Git ignore file
└── README.md             # Project documentation
```

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/yusong652/aiNagisa.git
cd aiNagisa
```

### 2. Backend Setup

#### Create and Activate Virtual Environment
```bash
cd backend
# Using uv to create virtual environment
uv venv
# Or using Python's built-in venv
# python -m venv .venv

# Activate virtual environment
# macOS/Linux
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
```

#### Install Dependencies
```bash
uv pip install -r requirements.txt
```

#### Configure Environment Variables
Create a `.env` file in the `backend` directory with the following required environment variables:

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key

# Fish Speech TTS Configuration
FISH_SPEECH_API_KEY=your_fish_speech_api_key
FISH_SPEECH_MODEL_ID=your_model_id
```

### 3. Running the Project

Ensure the backend virtual environment is activated, then run from the project root:

```bash
python run.py
```

This will start the FastAPI server (default address: `http://127.0.0.1:8000`), which also serves the frontend files.

Access the application by visiting `http://127.0.0.1:8000` in your browser.

## Features

### Implemented
- [x] LLM-based intelligent conversation
- [x] Multi-turn conversation memory
- [x] Text-to-Speech output
- [x] Conversation history storage
- [x] Character definition (System Prompt)
- [x] Context length limitation

### Planned
- [ ] User authentication system
- [ ] Multi-language support
- [ ] Custom voice models
- [ ] Mobile responsiveness
- [ ] Offline mode support

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
