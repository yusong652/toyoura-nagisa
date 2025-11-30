# Windows服务器部署策略：从零到生产环境

## 部署架构选择

### 方案对比

#### 方案A: 直接SSH (简单开发环境) ⭐
```
Mac → SSH → Windows内网服务器
```
- ✅ 最简单，适合内网开发
- ❌ 需要公网IP或端口转发
- 适用：公司内网或家庭局域网

#### 方案B: Cloudflare Tunnel (推荐生产环境) ⭐⭐⭐
```
Mac → Cloudflare → Tunnel → Windows服务器
```
- ✅ 无需公网IP
- ✅ 内置安全防护
- ✅ 免费tier够用
- 适用：任何网络环境

#### 方案C: Tailscale VPN (团队协作) ⭐⭐
```
Mac → Tailscale网络 → Windows服务器
```
- ✅ 零配置VPN
- ✅ 端到端加密
- 适用：团队开发环境

## 完整部署流程

### Step 1: Windows服务器基础设置

```powershell
# 1. 安装必要软件
# 以管理员身份运行PowerShell

# 安装Chocolatey包管理器
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 安装开发工具
choco install git python nodejs vscode -y
choco install openssh.server -y

# 2. 配置Git
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 3. 克隆项目
cd C:\Projects
git clone https://github.com/yusong652/toyoura-nagisa.git
cd toyoura-nagisa

# 4. 安装Python依赖
# 安装UV包管理器
pip install uv
# 安装项目依赖
uv sync

# 5. 配置环境变量
# 复制配置文件
cp backend\config_example\*.py backend\config\
# 编辑配置文件，添加API keys
```

### Step 2: SSH服务器配置

```powershell
# 1. 启用OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 2. 启动并设置自动启动
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'

# 3. 配置防火墙
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' `
  -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22

# 4. 配置SSH密钥认证
# 编辑 C:\ProgramData\ssh\sshd_config
notepad C:\ProgramData\ssh\sshd_config
```

sshd_config 关键配置：
```
PubkeyAuthentication yes
PasswordAuthentication yes  # 初次设置时开启，后续可关闭
PermitRootLogin no
AllowUsers your_username
```

```powershell
# 5. 重启SSH服务
Restart-Service sshd

# 6. 设置SSH密钥
# 创建.ssh目录
mkdir C:\Users\your_username\.ssh

# 从Mac复制公钥到Windows
# 在Mac上执行：
scp ~/.ssh/id_rsa.pub username@windows-ip:C:/Users/username/.ssh/authorized_keys
```

### Step 3: Cloudflare Tunnel设置（推荐）

#### Windows服务器端：

```powershell
# 1. 下载Cloudflare Tunnel
Invoke-WebRequest -Uri https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi -OutFile cloudflared.msi

# 2. 安装
msiexec /i cloudflared.msi

# 3. 登录Cloudflare
cloudflared tunnel login

# 4. 创建tunnel
cloudflared tunnel create ainagisa-dev

# 5. 创建配置文件
# C:\Users\username\.cloudflared\config.yml
```

config.yml内容：
```yaml
tunnel: <tunnel-id>
credentials-file: C:\Users\username\.cloudflared\<tunnel-id>.json

ingress:
  # SSH访问
  - hostname: ssh.ainagisa.dev
    service: ssh://localhost:22
  
  # MCP服务器
  - hostname: mcp.ainagisa.dev
    service: http://localhost:9000
  
  # 开发服务器（可选）
  - hostname: dev.ainagisa.dev
    service: http://localhost:8000
  
  # 404规则
  - service: http_status:404
```

```powershell
# 6. 运行tunnel
cloudflared tunnel run ainagisa-dev

# 7. 安装为Windows服务
cloudflared service install
```

#### Cloudflare Dashboard配置：

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 选择域名 → DNS
3. 添加CNAME记录：
   - ssh.ainagisa.dev → <tunnel-id>.cfargotunnel.com
   - mcp.ainagisa.dev → <tunnel-id>.cfargotunnel.com

#### Mac连接配置：

```bash
# ~/.ssh/config
Host ainagisa-windows
    HostName ssh.ainagisa.dev
    User your_username
    Port 22
    IdentityFile ~/.ssh/id_rsa
    ProxyCommand cloudflared access ssh --hostname %h
```

### Step 4: MCP服务器部署

Windows服务器上创建启动脚本：

```powershell
# C:\Projects\toyoura-nagisa\start_servers.ps1

# 启动MCP服务器
Start-Process python -ArgumentList "backend\infrastructure\mcp\smart_mcp_server.py" -WorkingDirectory "C:\Projects\toyoura-nagisa"

# 启动FastAPI后端
Start-Process python -ArgumentList "backend\app.py" -WorkingDirectory "C:\Projects\toyoura-nagisa"

# 启动前端（如果需要）
Start-Process npm -ArgumentList "run dev" -WorkingDirectory "C:\Projects\toyoura-nagisa\frontend"
```

Windows服务配置（使用NSSM）：
```powershell
# 安装NSSM
choco install nssm -y

# 注册MCP服务
nssm install AiNagisaMCP "C:\Python39\python.exe" "C:\Projects\toyoura-nagisa\backend\infrastructure\mcp\smart_mcp_server.py"
nssm set AiNagisaMCP AppDirectory "C:\Projects\toyoura-nagisa"
nssm set AiNagisaMCP Start SERVICE_AUTO_START

# 启动服务
nssm start AiNagisaMCP
```

### Step 5: VSCode Remote开发配置

#### Windows端准备：

```powershell
# 确保VSCode Server可以运行
# 创建专用目录
mkdir C:\VSCodeServer

# 设置环境变量
[Environment]::SetEnvironmentVariable("VSCODE_SERVER_DATA_DIR", "C:\VSCodeServer", "User")
```

#### Mac端VSCode设置：

1. 安装Remote-SSH扩展
2. 配置SSH（使用上面的配置）
3. 连接到服务器

settings.json:
```json
{
    "remote.SSH.defaultExtensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "github.copilot"
    ],
    "remote.SSH.connectTimeout": 30,
    "remote.SSH.maxReconnectionAttempts": 5
}
```

## 安全最佳实践

### 1. SSH加固
```powershell
# 修改SSH端口（可选）
# 在sshd_config中：
Port 2222

# 限制用户
AllowUsers your_username
DenyUsers Administrator Guest

# 限制IP（如果有固定IP）
AllowUsers your_username@your.ip.address
```

### 2. Windows防火墙规则
```powershell
# 只允许特定端口
New-NetFirewallRule -DisplayName "AI Nagisa MCP" -Direction Inbound -LocalPort 9000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "AI Nagisa API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### 3. Cloudflare Access保护
在Cloudflare Dashboard设置Access策略：
- 要求邮箱验证
- 限制特定邮箱域名
- 添加2FA要求

## 开发工作流

### 日常开发流程：

```bash
# 1. Mac上连接到Windows
ssh ainagisa-windows

# 或使用VSCode
code --remote ssh-remote+ainagisa-windows /C/Projects/toyoura-nagisa

# 2. 在Windows上启动服务
powershell C:\Projects\toyoura-nagisa\start_servers.ps1

# 3. 通过Cloudflare访问服务
# MCP: https://mcp.ainagisa.dev
# API: https://dev.ainagisa.dev

# 4. 本地开发，自动同步
# 使用VSCode的自动保存功能
```

### 持续同步方案：

```bash
# 使用fswatch + rsync自动同步（Mac端）
brew install fswatch

# sync.sh
#!/bin/bash
fswatch -o . | while read f; do
    rsync -avz --exclude='.git' --exclude='node_modules' \
          --exclude='__pycache__' --exclude='.venv' \
          ./ ainagisa-windows:/C/Projects/toyoura-nagisa/
done
```

## 故障排查

### SSH连接问题：
```powershell
# Windows上检查SSH服务
Get-Service sshd
Test-NetConnection -ComputerName localhost -Port 22

# 查看SSH日志
Get-EventLog -LogName System -Source sshd
```

### Cloudflare Tunnel问题：
```powershell
# 检查tunnel状态
cloudflared tunnel info ainagisa-dev

# 查看实时日志
cloudflared tunnel run ainagisa-dev --loglevel debug

# 重启服务
Restart-Service cloudflared
```

### 权限问题：
```powershell
# 修复.ssh目录权限
icacls C:\Users\username\.ssh /inheritance:r
icacls C:\Users\username\.ssh /grant:r "%username%":"(F)"
```

## 推荐部署方案

### 开发环境：
1. **内网**: 直接SSH
2. **远程**: Tailscale VPN

### 生产环境：
1. **首选**: Cloudflare Tunnel（免费、安全、稳定）
2. **备选**: 自建VPN + Nginx反向代理

### 最小化部署（快速开始）：
```powershell
# 30分钟快速部署
1. 启用SSH (5分钟)
2. 克隆代码 (5分钟)
3. 安装依赖 (10分钟)
4. 配置Cloudflare Tunnel (10分钟)
5. 开始开发！
```

## 成本分析

- **Cloudflare Tunnel**: 免费（每月1TB流量）
- **Tailscale**: 免费（最多20设备）
- **Windows服务器**: 
  - 自有硬件：仅电费
  - 云服务器：约$20-50/月

## 下一步

1. 先在内网测试SSH连接
2. 配置Cloudflare Tunnel实现外网访问
3. 设置自动化部署脚本
4. 实施监控和日志系统

---

选择最适合你的方案，30分钟内即可完成基础部署！