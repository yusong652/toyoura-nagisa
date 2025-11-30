# 配置文件管理策略：开发到生产的安全实践

## 核心问题
- 配置文件包含敏感信息（API keys、数据库密码等）
- 不能提交到Git仓库
- 需要在Mac和Windows之间同步
- 不同环境需要不同配置

## 解决方案架构

### 方案1：环境变量方案（推荐）⭐⭐⭐

#### 实现步骤

1. **创建环境配置模板**
```python
# backend/config/base.py
import os
from pathlib import Path

class Config:
    """基础配置，从环境变量读取"""
    
    # API Keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # 数据库配置
    CHROMA_DB_PATH = os.getenv('CHROMA_DB_PATH', './memory_db')
    
    # 服务配置
    MCP_SERVER_PORT = int(os.getenv('MCP_SERVER_PORT', '9000'))
    API_SERVER_PORT = int(os.getenv('API_SERVER_PORT', '8000'))
    
    # 环境标识
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    
    @classmethod
    def validate(cls):
        """验证必需的配置项"""
        required = ['GEMINI_API_KEY']
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(f"Missing required config: {missing}")
```

2. **Windows环境变量设置**
```powershell
# 创建环境配置文件
# C:\Projects\toyoura-nagisa\.env.production

# API Keys
$env:GEMINI_API_KEY = "your-gemini-key"
$env:ANTHROPIC_API_KEY = "your-anthropic-key"
$env:OPENAI_API_KEY = "your-openai-key"

# 环境标识
$env:ENVIRONMENT = "production"

# 持久化环境变量（系统级）
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-key", "Machine")
```

3. **使用python-dotenv自动加载**
```python
# backend/config/__init__.py
from dotenv import load_dotenv
import os

# 根据环境加载不同的.env文件
env = os.getenv('ENVIRONMENT', 'development')
env_file = f'.env.{env}'

if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    load_dotenv('.env')  # 默认配置

from .base import Config

# 验证配置
Config.validate()
```

### 方案2：加密配置文件方案 ⭐⭐

#### 使用ansible-vault或git-crypt

1. **安装git-crypt**
```bash
# Mac
brew install git-crypt

# Windows (通过WSL或Git Bash)
# 下载二进制文件
```

2. **初始化加密**
```bash
# 在项目根目录
git-crypt init

# 创建.gitattributes
echo "backend/config/*.py filter=git-crypt diff=git-crypt" >> .gitattributes
echo ".env* filter=git-crypt diff=git-crypt" >> .gitattributes

# 添加授权用户
git-crypt add-gpg-user your-email@example.com
```

3. **工作流程**
```bash
# 解密（在可信设备上）
git-crypt unlock

# 文件自动加密后提交
git add backend/config/
git commit -m "Update config"
git push

# Windows服务器上解密
git-crypt unlock key.file
```

### 方案3：Secret管理服务 ⭐⭐

#### 使用HashiCorp Vault或Azure Key Vault

```python
# backend/config/vault_config.py
import hvac

class VaultConfig:
    def __init__(self):
        self.client = hvac.Client(
            url='https://vault.company.com',
            token=os.getenv('VAULT_TOKEN')
        )
    
    def get_secret(self, key):
        """从Vault获取秘密"""
        response = self.client.secrets.kv.v2.read_secret_version(
            path=f'ainagisa/{key}'
        )
        return response['data']['data']['value']
    
    @property
    def gemini_api_key(self):
        return self.get_secret('gemini_api_key')
```

### 方案4：分离式配置（简单实用）⭐⭐⭐

#### 本地配置 + 远程配置分离

1. **创建配置结构**
```
backend/
  config/
    base.py          # 基础配置（可提交）
    local.py         # 本地开发配置（不提交）
    production.py    # 生产配置（不提交）
    __init__.py      # 配置加载器
```

2. **基础配置（可提交到Git）**
```python
# backend/config/base.py
class BaseConfig:
    """基础配置，不包含敏感信息"""
    
    # 应用配置
    APP_NAME = "toyoura-nagisa"
    VERSION = "1.0.0"
    DEBUG = False
    
    # 服务端口
    MCP_SERVER_PORT = 9000
    API_SERVER_PORT = 8000
    
    # 路径配置
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    MEMORY_DB_PATH = PROJECT_ROOT / "memory_db"
    
    # 功能开关
    ENABLE_TTS = True
    ENABLE_MEMORY = True
```

3. **环境特定配置（不提交）**
```python
# backend/config/production.py
from .base import BaseConfig

class ProductionConfig(BaseConfig):
    """生产环境配置"""
    
    # API Keys（敏感信息）
    GEMINI_API_KEY = "sk-xxxxx"
    ANTHROPIC_API_KEY = "sk-xxxxx"
    
    # 数据库
    DATABASE_URL = "postgresql://user:pass@localhost/db"
    
    # 覆盖基础配置
    DEBUG = False
    ENABLE_MONITORING = True
```

4. **智能配置加载器**
```python
# backend/config/__init__.py
import os
import socket

def get_config():
    """根据环境自动选择配置"""
    
    # 方法1：环境变量
    env = os.getenv('APP_ENV', 'development')
    
    # 方法2：主机名检测
    hostname = socket.gethostname()
    if 'production' in hostname or 'WINDOWS' in hostname:
        env = 'production'
    
    # 方法3：文件标记
    if os.path.exists('.production'):
        env = 'production'
    
    # 动态导入配置
    if env == 'production':
        from .production import ProductionConfig
        return ProductionConfig()
    else:
        from .local import LocalConfig
        return LocalConfig()

config = get_config()
```

## 实用同步方案

### 安全同步脚本

```bash
#!/bin/bash
# sync-config.sh - 安全同步配置到Windows

# 1. 加密传输敏感配置
tar czf - backend/config/production.py | \
  openssl enc -aes-256-cbc -salt -pass pass:$CONFIG_PASSWORD | \
  ssh user@windows-server "cd /C/Projects/toyoura-nagisa && openssl enc -aes-256-cbc -d -pass pass:$CONFIG_PASSWORD | tar xzf -"

# 2. 使用rsync排除敏感文件
rsync -avz \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='backend/config/local.py' \
  --exclude='backend/config/production.py' \
  --exclude='.env*' \
  ./ user@windows-server:/C/Projects/toyoura-nagisa/

# 3. 单独安全传输配置
scp -i ~/.ssh/id_rsa backend/config/production.py \
  user@windows-server:/C/Projects/toyoura-nagisa/backend/config/
```

### Windows PowerShell同步

```powershell
# sync-from-mac.ps1
# 从Mac安全获取配置

# 1. 通过SSH获取加密配置
ssh user@mac "cat ~/ainagisa-config.enc" | `
  ConvertFrom-Base64 | `
  Decrypt-Content -Password $env:CONFIG_PASSWORD | `
  Out-File -FilePath ".\backend\config\production.py"

# 2. 验证配置
python -c "from backend.config import config; config.validate()"
```

## 最佳实践建议

### 1. 开发环境（Mac）
```python
# backend/config/local.py
class LocalConfig(BaseConfig):
    """本地开发配置"""
    GEMINI_API_KEY = "test-key-for-dev"
    DEBUG = True
```

### 2. 生产环境（Windows）
- 使用Windows Credential Manager存储API Keys
- 通过环境变量或专用配置文件加载

```powershell
# 使用Windows凭据管理器
cmdkey /generic:AINAGISA_GEMINI_KEY /user:apikey /pass:your-actual-key

# Python中读取
import keyring
gemini_key = keyring.get_password("AINAGISA", "GEMINI_KEY")
```

### 3. 配置文件模板
```bash
# 创建配置模板供团队使用
cp backend/config/local.py backend/config/local.example.py
# 移除敏感信息，替换为占位符
sed -i 's/sk-[a-zA-Z0-9]*/YOUR_API_KEY_HERE/g' backend/config/local.example.py
```

## 推荐方案总结

### 快速开始（最简单）：
1. 使用`.env`文件 + python-dotenv
2. `.env`文件不提交Git
3. 手动复制到Windows

```bash
# Mac
echo "GEMINI_API_KEY=sk-xxxxx" > .env.production

# 安全传输到Windows
scp .env.production user@windows:/C/Projects/toyoura-nagisa/
```

### 专业方案（推荐）：
1. 环境变量 + 配置类
2. 不同环境不同配置文件
3. 敏感信息永不入Git

### 企业方案：
1. HashiCorp Vault
2. Azure Key Vault
3. AWS Secrets Manager

## 安全检查清单

- [ ] 配置文件已加入.gitignore
- [ ] API Keys未硬编码在代码中
- [ ] 使用环境变量或安全存储
- [ ] 传输过程加密
- [ ] 定期轮换密钥
- [ ] 配置验证机制
- [ ] 备份恢复方案

---

选择适合你的方案，确保配置安全且易于管理！