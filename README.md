
<p align="center">
  <img src="https://raw.githubusercontent.com/yusong652/aiNagisa/main/frontend-react/public/Nagisa.png" alt="aiNagisa Logo" width="200"/>
</p>

<h1 align="center">aiNagisa</h1>

<p align="center">
  <strong>An extensible, voice-enabled AI assistant with long-term memory and a dynamic tool-use framework.</strong>
</p>

<p align="center">
  <a href="https://github.com/yusong652/aiNagisa/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  </a>
  <a href="https://github.com/yusong652/aiNagisa/pulls">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
  </a>
</p>

---

## 🚀 Core Philosophy

aiNagisa is not just another chatbot. It's an exploration into creating a truly helpful and adaptive AI companion. Our goal is to build a system that can learn, reason, and act in the world through a rich set of tools. We believe that the future of AI lies in its ability to seamlessly integrate with our digital lives, and aiNagisa is our step in that direction.

## ✨ Key Innovations

aiNagisa is built on a foundation of several key technical innovations that set it apart:

### 🧠 **Autonomous Tool Orchestration with `FastMCP`**

At the heart of aiNagisa is the **Master Control Program (MCP)**, a powerful tool orchestration engine. Unlike traditional chatbots with hardcoded tool integrations, aiNagisa features a dynamic, semantic tool discovery and invocation system.

- **Semantic Tool Search**: We use a `ToolVectorizer` to embed the descriptions and capabilities of all available tools into a vector space. When a user makes a request, the LLM can query this vector space to find the most relevant tools for the task at hand. This allows for a much more flexible and extensible tool system.
- **Dynamic Tool Loading**: Tools are categorized and can be loaded on-demand, making the system lightweight and scalable. The LLM can request tool categories based on the task, and the MCP will provide the necessary tools.
- **Chain of Thought (CoT) and Tool Use**: The system supports complex, multi-step tasks by allowing the LLM to chain together multiple tool calls. The LLM can reason about the results of one tool and use them as input for another, enabling sophisticated workflows.

### 📚 **Persistent, Vectorized Long-Term Memory**

aiNagisa has a sophisticated long-term memory system that allows it to learn from past conversations and build a persistent model of the user and their preferences.

- **ChromaDB Integration**: We use `ChromaDB` to store and retrieve memories based on semantic similarity. This means that Nagisa can recall relevant information from past conversations even if the user's wording is different.
- **Context-Aware Memory**: The memory system is integrated with the chat flow, allowing Nagisa to inject relevant memories into the conversation at the right time, creating a more personalized and contextually rich experience.

### 🗣️ **Multi-Provider LLM and TTS Support**

aiNagisa is designed to be flexible and adaptable. It supports a variety of LLM and TTS providers through a factory pattern.

- **LLM Agnostic**: Easily switch between models from OpenAI, Google, Anthropic, and more. This allows you to leverage the best model for your needs and budget.
- **Pluggable TTS**: The Text-to-Speech system is also pluggable, with support for both local and remote TTS engines.

### 🎨 **Engaging Frontend with Live2D**

The user experience is a top priority. We've built a modern, responsive frontend with a unique twist.

- **React and Material-UI**: A clean, modern, and responsive UI built with industry-standard technologies.
- **Live2D Integration**: Nagisa is brought to life with a `Live2D` model that reacts to the conversation, creating a more engaging and personal interaction.

## 🛠️ Technical Deep Dive

### System Architecture

```
+------------------------------------------------+
|                 Frontend (React)               |
| (Live2D, Chat UI, Geolocation, Voice Input)    |
+----------------------+-------------------------+
                       | (WebSocket / HTTP)
+----------------------v-------------------------+
|                 Backend (FastAPI)              |
| +------------------+  +----------------------+ |
| |   LLM Factory    |  |     TTS Factory      | |
| | (GPT, Gemini,...) |  | (Local, Remote,...) | |
| +------------------+  +----------------------+ |
|                      |                         |
| +--------------------v-----------------------+ |
| |      Model Context Protocol (FastMCP)      | |
| | +----------------+  +--------------------+ | |
| | | Tool Vectorizer|  |   Tool Registry    | | |
| | |  (ChromaDB)    |  | (Active Tools)     | | |
| | +----------------+  +--------------------+ | |
| +------------------------------------------+ |
|                      |                         |
| +--------------------v-----------------------+ |
| |      Long-Term Memory (ChromaDB)           | |
| +------------------------------------------+ |
+------------------------------------------------+
```

### Project Structure

```
aiNagisa/
├── backend/
│   ├── app.py              # FastAPI application entrypoint
│   ├── chat/               # LLM clients and conversation management
│   ├── memory/             # Long-term memory system (ChromaDB)
│   ├── nagisa_mcp/         # Master Control Program and tool definitions
│   └── tts/                # Text-to-Speech clients
├── frontend-react/
│   ├── src/
│   │   ├── App.tsx         # Main React application component
│   │   ├── components/     # UI components (ChatBox, Live2DCanvas, etc.)
│   │   └── contexts/       # React contexts for state management
│   └── public/
│       └── live2d_models/  # Live2D model files
└── ...
```

## 🚀 Getting Started

... (The getting started guide from the previous version is good, I will keep it here)

## 🤝 Contributing

We are actively looking for contributors to help us push the boundaries of what's possible with AI assistants. Whether you're a frontend developer, a backend engineer, or an AI researcher, there are many ways to get involved. Please check out our contributing guidelines to get started.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
