# 🚀 分布式HPC LLM推理框架

基于SSH隧道的分布式LLM推理系统，支持vLLM和Ollama在HPC集群上的部署。

## ⚡ 快速开始

### 1. 配置SSH凭据（首次使用）

```bash
# 运行配置向导
cd backend/chat/local
python setup_config.py

# 选择选项 1: Setup new configuration
# 然后编辑 config.py 文件，填入您的HPC信息
```

### 2. 使用分布式客户端

```python
from backend.chat.llm_factory import get_client

# 创建分布式客户端（自动读取配置）
client = get_client("distributed-vllm")

# 启动HPC连接
await client.start_service()

# 进行推理
response = await client.generate(messages)
```

## 🔧 配置说明

### 配置文件位置
- **模板文件**: `config.example.py` (版本控制)
- **实际配置**: `config.py` (gitignore, 包含敏感信息)

### 必需配置项
```python
{
    "enabled": True,
    "host": "您的HPC集群地址.edu",
    "username": "您的HPC用户名", 
    "ssh_key_path": "~/.ssh/id_rsa",
    "models": {
        "vllm": "/shared/models/您的模型路径"
    }
}
```

## 🔒 安全特性

- ✅ 配置文件已加入`.gitignore`
- ✅ 支持SSH密钥认证
- ✅ 模板与实际配置分离
- ✅ 环境变量覆盖支持

## 📁 文件结构

```
backend/chat/local/
├── config.example.py     # 配置模板（安全提交）
├── config.py            # 实际配置（gitignore）
├── setup_config.py      # 配置向导
├── distributed_client.py # 分布式客户端
├── simple_ssh_manager.py # SSH隧道管理
└── README.md            # 文档
```

## 🛠️ 管理命令

```bash
# 配置管理
python setup_config.py

# 测试配置
python config_example.py

# 生成HPC部署脚本
python hpc_deployment_template.py
```

## 🌊 工作流程

1. **配置阶段**: 使用`setup_config.py`创建配置
2. **部署阶段**: HPC上手动启动长期运行的服务器
3. **连接阶段**: 本地创建SSH隧道连接到HPC
4. **推理阶段**: 即时响应，无队列延迟

## 📊 支持的客户端

- `distributed-vllm`: 分布式vLLM推理
- `distributed-ollama`: 分布式Ollama推理
- `vllm`: 本地vLLM服务器
- `ollama`: 本地Ollama服务器

## 🔍 故障排除

### 常见问题

1. **SSH连接失败**
   ```bash
   # 检查SSH密钥权限
   chmod 600 ~/.ssh/id_rsa
   
   # 测试SSH连接
   ssh -i ~/.ssh/id_rsa username@hpc.edu
   ```

2. **配置验证失败**
   ```bash
   python setup_config.py
   # 选择选项 2: Test current configuration
   ```

3. **隧道创建失败**
   - 确认HPC服务器已启动
   - 检查端口是否被占用
   - 验证防火墙设置

## 🚀 高级用法

### 环境变量配置
```bash
export HPC_ENABLED=true
export HPC_HOST=hpc.university.edu
export HPC_USERNAME=your_username
```

### 临时配置覆盖
```python
client = get_client(
    "distributed-vllm",
    host="backup-hpc.edu",
    username="temp_user"
)
```

### 多隧道负载均衡
```python
# 添加额外隧道
await client.add_tunnel(remote_port=8001)

# 查看隧道状态
status = client.get_service_info()
print(status["ssh_status"])
```

## 📝 贡献指南

1. 配置更改请更新`config.example.py`
2. 新功能需要更新文档
3. 确保敏感信息不会提交到版本控制

## 🆘 获取帮助

- 运行`python setup_config.py`获取交互式帮助
- 查看`config_example.py`了解配置测试
- 检查`quick_start_guide.md`获取使用示例