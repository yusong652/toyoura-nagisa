"""
HPC配置示例

展示如何在config.py中配置SSH信息，以及如何使用分布式客户端。
"""

# 配置文件示例 (backend/chat/local/config.py)
EXAMPLE_HPC_CONFIG = """
# 在 get_hpc_config() 函数的 defaults 中修改：

defaults = {
    "enabled": True,  # 🔥 启用HPC分布式推理
    
    # SSH连接配置
    "host": "hpc.university.edu",        # 🔧 您的HPC集群地址
    "username": "your_username",         # 🔧 您的HPC用户名
    "ssh_key_path": "~/.ssh/id_rsa",     # 🔧 SSH私钥路径
    "ssh_port": 22,
    
    # HPC项目配置
    "project_path": "/shared/ainagisa",
    "session_duration_hours": 8,         # 申请8小时资源
    
    # 模型路径配置
    "models": {
        "vllm": "/shared/models/llama-3.2-8b",    # 🔧 HPC上的模型路径
        "ollama": "llama3.2:3b"
    },
    
    # 端口配置
    "tunnel_ports": {
        "vllm": 8000,
        "ollama": 11434,
        "local_base": 8000
    }
}
"""

# 使用示例
USAGE_EXAMPLES = """
# 方式1: 使用配置文件中的设置（推荐）
from backend.chat.llm_factory import get_client

client = get_client("distributed-vllm")  # 自动读取config.py中的配置
await client.start_service()
response = await client.generate(messages)

# 方式2: 临时覆盖配置
client = get_client(
    "distributed-vllm",
    host="another-hpc.edu",     # 临时使用不同的HPC
    username="temp_user"        # 临时使用不同的用户名
)

# 方式3: 环境变量配置
# export HPC_ENABLED=true
# export HPC_HOST=hpc.university.edu
# export HPC_USERNAME=your_username
client = get_client("distributed-vllm")  # 自动读取环境变量
"""

def show_current_config():
    """显示当前HPC配置"""
    from backend.chat.local.config import get_hpc_config
    
    config = get_hpc_config()
    
    print("🔧 当前HPC配置:")
    print("=" * 50)
    print(f"启用状态: {config.get('enabled')}")
    print(f"HPC主机: {config.get('host')}")
    print(f"用户名: {config.get('username')}")
    print(f"SSH密钥: {config.get('ssh_key_path')}")
    print(f"vLLM模型: {config.get('models', {}).get('vllm')}")
    print(f"会话时长: {config.get('session_duration_hours')}小时")
    
    if not config.get('enabled'):
        print("\n⚠️  HPC未启用。请在config.py中设置 enabled=True")
    
    if config.get('host') == 'hpc.university.edu':
        print("\n📝 请更新config.py中的HPC主机地址")

def test_distributed_client():
    """测试分布式客户端创建"""
    try:
        from backend.chat.llm_factory import get_client
        
        print("🧪 测试分布式客户端创建...")
        
        # 尝试创建客户端（不启动服务）
        client = get_client("distributed-vllm")
        
        print("✅ 分布式客户端创建成功")
        print(f"📊 服务信息: {client.get_service_info()}")
        
    except Exception as e:
        print(f"❌ 客户端创建失败: {e}")
        print("\n💡 解决方案:")
        print("1. 检查 backend/chat/local/config.py 中的HPC配置")
        print("2. 确保 enabled=True")
        print("3. 填写正确的 host 和 username")

if __name__ == "__main__":
    print("🚀 HPC分布式LLM配置助手")
    print("=" * 50)
    
    # 显示配置示例
    print("\n📖 配置文件示例:")
    print(EXAMPLE_HPC_CONFIG)
    
    # 显示使用示例
    print("\n📖 使用示例:")
    print(USAGE_EXAMPLES)
    
    # 显示当前配置
    print("\n" + "="*50)
    show_current_config()
    
    # 测试客户端
    print("\n" + "="*50)
    test_distributed_client()