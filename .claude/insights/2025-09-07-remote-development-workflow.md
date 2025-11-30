# Mac开发 + Windows服务器运行：远程开发工作流方案

## 核心需求
- **Mac本地**：写代码、使用Claude Code
- **Windows服务器**：运行商业软件、执行代码
- **实时同步**：代码修改立即在服务器生效

## 解决方案：VSCode Remote-SSH

### 1. VSCode Remote Development 架构

```
Mac (本地)                     Windows Server (远程)
┌─────────────┐               ┌──────────────────┐
│   VSCode    │               │   SSH Server     │
│  + Claude   │   SSH/SFTP    │   + 代码仓库     │
│  + 编辑器    │ ◄──────────► │   + Python环境   │
│  + 终端      │               │   + 商业软件     │
└─────────────┘               └──────────────────┘
```

### 工作原理
1. VSCode通过SSH连接到Windows服务器
2. 代码实际存储在Windows服务器上
3. Mac上的VSCode作为前端编辑界面
4. 所有执行都在Windows服务器上进行

## 具体实施步骤

### Step 1: Windows服务器配置

```powershell
# 1. 启用OpenSSH Server (Windows Server 2019+内置)
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 2. 启动SSH服务
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'

# 3. 配置防火墙
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22

# 4. 配置SSH密钥认证
# 在 C:\ProgramData\ssh\sshd_config 中设置:
PubkeyAuthentication yes
PasswordAuthentication no  # 可选，更安全
```

### Step 2: Mac本地配置

```bash
# 1. 生成SSH密钥对
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 2. 复制公钥到Windows服务器
ssh-copy-id username@windows-server-ip

# 3. 配置SSH config (~/.ssh/config)
Host pfc-windows
    HostName 192.168.1.100  # Windows服务器IP
    User your_username
    Port 22
    IdentityFile ~/.ssh/id_rsa
    ForwardAgent yes
```

### Step 3: VSCode配置

```json
// 1. 安装Remote-SSH扩展
// 扩展ID: ms-vscode-remote.remote-ssh

// 2. 连接到服务器
// Command Palette: Remote-SSH: Connect to Host
// 选择: pfc-windows

// 3. 项目设置 (.vscode/settings.json)
{
    "python.defaultInterpreterPath": "C:\\Python39\\python.exe",
    "terminal.integrated.shell.windows": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    "remote.SSH.remotePlatform": {
        "pfc-windows": "windows"
    }
}
```

## Claude Code 集成方案

### 方案A: 直接SSH执行
Claude Code可以通过SSH直接在Windows服务器上执行命令：

```python
# backend/infrastructure/remote/ssh_executor.py
import paramiko

class RemoteExecutor:
    def __init__(self, host, username, key_file):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(host, username=username, key_filename=key_file)
    
    def execute_command(self, command):
        """在远程Windows服务器执行命令"""
        stdin, stdout, stderr = self.ssh.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()
    
    def execute_python(self, script):
        """在远程执行Python脚本"""
        command = f'C:\\Python39\\python.exe -c "{script}"'
        return self.execute_command(command)
```

### 方案B: 远程文件系统挂载
使用SSHFS或SMB将Windows文件系统挂载到Mac：

```bash
# Mac上安装SSHFS
brew install macfuse
brew install sshfs

# 挂载Windows目录
mkdir ~/windows-dev
sshfs username@windows-server:/C:/Projects ~/windows-dev

# 现在可以直接编辑远程文件
cd ~/windows-dev/toyoura-nagisa
code .  # VSCode打开
```

### 方案C: Git同步方案
使用Git作为同步机制：

```bash
# Windows服务器作为Git远程仓库
# Windows上初始化裸仓库
git init --bare C:\GitRepos\toyoura-nagisa.git

# Mac上添加远程仓库
git remote add windows ssh://username@windows-server/C:/GitRepos/toyoura-nagisa.git

# 自动同步脚本
#!/bin/bash
# auto-sync.sh
while true; do
    git add .
    git commit -m "Auto sync"
    git push windows main
    ssh username@windows-server "cd /C/Projects/toyoura-nagisa && git pull"
    sleep 5
done
```

## 商业软件MCP集成

### Windows服务器上运行MCP Server
```python
# 在Windows服务器上运行
# C:\Projects\toyoura-nagisa\backend\infrastructure\mcp\pfc_mcp_server.py

import asyncio
from fastmcp import FastMCP
import win32com.client  # Windows COM对象

mcp = FastMCP("PFC-MCP-Server")

@mcp.tool()
async def run_pfc_simulation(model_file: str, parameters: dict):
    """直接调用本地PFC软件"""
    pfc = win32com.client.Dispatch("PFC.Application")
    pfc.OpenModel(f"C:\\PFC_Models\\{model_file}")
    pfc.SetParameters(parameters)
    result = pfc.RunSimulation()
    return {"status": "success", "result": result}

# 服务器运行在Windows上
mcp.run(host="0.0.0.0", port=9000)
```

### Mac上的Claude通过SSH隧道访问
```bash
# 建立SSH隧道
ssh -L 9000:localhost:9000 username@windows-server

# 现在Mac上的localhost:9000映射到Windows的MCP服务器
```

## 开发工作流

### 1. 日常开发流程
```bash
# Mac上
1. 打开VSCode
2. Remote-SSH连接到Windows
3. 编辑代码（实际在Windows上）
4. 终端执行（在Windows上运行）
5. Claude Code通过SSH执行命令
```

### 2. 调试流程
```python
# VSCode launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "windows-server",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "C:/Projects/toyoura-nagisa"
                }
            ]
        }
    ]
}
```

### 3. 性能优化
```yaml
# SSH配置优化
Host pfc-windows
    ControlMaster auto
    ControlPath ~/.ssh/control-%h-%p-%r
    ControlPersist 600  # 保持连接10分钟
    Compression yes
    CompressionLevel 9
```

## 实际使用示例

### Claude Code 使用SSH执行
```python
# Claude可以这样执行远程命令
import subprocess

def run_on_windows(command):
    """通过SSH在Windows服务器执行"""
    ssh_command = f"ssh pfc-windows '{command}'"
    result = subprocess.run(ssh_command, shell=True, capture_output=True)
    return result.stdout.decode()

# 运行PFC仿真
output = run_on_windows("python C:/Projects/toyoura-nagisa/run_pfc_simulation.py")
```

### 实时文件监控
```python
# 使用watchdog监控文件变化并自动同步
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class SyncHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # 文件修改后自动同步到Windows
        subprocess.run("rsync -avz . pfc-windows:/C/Projects/toyoura-nagisa/", shell=True)

observer = Observer()
observer.schedule(SyncHandler(), path='.', recursive=True)
observer.start()
```

## 核心优势

### 1. 开发体验
✅ Mac原生开发环境
✅ VSCode完整功能支持
✅ Claude Code正常工作
✅ 实时代码同步

### 2. 执行环境
✅ 代码在Windows原生运行
✅ 直接访问商业软件
✅ 无需虚拟化开销
✅ 完整的Windows API访问

### 3. 简单可靠
✅ 标准SSH协议
✅ 成熟的工具链
✅ 易于配置和维护
✅ 安全加密传输

## 推荐方案

### 最佳实践：VSCode Remote-SSH
1. **简单**：VSCode内置支持，配置简单
2. **透明**：就像本地开发一样
3. **强大**：完整的调试、终端、扩展支持
4. **稳定**：Microsoft官方维护

### 备选方案：SSH + rsync
- 更灵活的控制
- 适合自动化脚本
- 可以集成到CI/CD

## 立即行动

1. **配置Windows SSH Server** (30分钟)
2. **安装VSCode Remote-SSH** (5分钟)
3. **建立连接测试** (10分钟)
4. **迁移项目到Windows** (1小时)
5. **开始远程开发** ✅

---

这样，Claude Code在Mac上编辑，代码实际在Windows服务器上运行，完美解决了商业软件集成问题！