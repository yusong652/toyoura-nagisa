# 🚀 HPC分布式LLM推理 - 快速开始

## 简化架构（无额外依赖）

✅ **移除paramiko依赖**，使用系统SSH命令  
✅ **简化部署流程**，专注核心功能  
✅ **保持优雅API**，一键连接HPC  

## 使用步骤

### 1. 准备HPC环境
```bash
# 在HPC上手动启动vLLM服务器（一次性，运行8小时）
ssh your_username@hpc.university.edu
sbatch deploy_vllm.sh  # 使用生成的部署脚本
```

### 2. 本地连接
```python
from backend.chat.llm_factory import get_client

# 创建分布式客户端
client = get_client(
    name="distributed-vllm",
    hpc_host="hpc.university.edu",
    ssh_user="your_username",
    ssh_key_path="~/.ssh/id_rsa"
)

# 启动连接（创建SSH隧道）
await client.start_service()

# 即时推理
response = await client.generate(messages)
```

## 核心架构

```
本地aiNagisa → SSH隧道 → HPC运行的vLLM → 即时响应
     ↓              ↓              ↓
  工厂模式      系统SSH命令    长期运行服务器
```

## 配置示例

```python
# config.py 中添加
HPC_CONFIG = {
    "hpc_host": "hpc.university.edu",
    "ssh_user": "username", 
    "ssh_key_path": "~/.ssh/id_rsa",
    "model_path": "/shared/models/llama-7b"
}

# 使用
client = get_client("distributed-vllm", **HPC_CONFIG)
```

## 部署脚本生成

```python
from backend.chat.local.hpc_deployment_template import create_deployment_files

# 生成所有部署文件
create_deployment_files(
    output_dir="./hpc_deploy",
    hpc_host="hpc.university.edu",
    ssh_user="username",
    vllm_model_path="/shared/models/llama-7b"
)

# 运行生成的快速启动脚本
# ./hpc_deploy/quickstart.sh
```

## 关键特性

- **零依赖**：只使用Python标准库和系统SSH
- **即时响应**：连接到预运行的HPC服务器
- **自动恢复**：SSH隧道断线自动重连
- **优雅集成**：完全兼容现有LLM工厂

## 故障排除

1. **SSH连接失败**：检查密钥权限 `chmod 600 ~/.ssh/id_rsa`
2. **隧道创建失败**：确认HPC服务器已启动
3. **推理失败**：检查远程端口是否正确

## 扩展功能

```python
# 添加更多隧道（多GPU场景）
await client.add_tunnel(remote_port=8001)

# 获取状态信息
info = client.get_service_info()
print(info["ssh_status"])

# 清理资源
await client.stop_service()
```

现在可以在无额外依赖的情况下实现HPC分布式推理！