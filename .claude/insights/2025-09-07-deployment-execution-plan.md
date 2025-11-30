# Windows部署执行计划：从零开始的正确顺序

## 🎯 正确的执行顺序

### Step 0: 先提交当前工作（5分钟）
```bash
# 在Mac上，确保当前代码已提交
cd /Users/hanyusong/toyoura-nagisa

# 查看状态
git status

# 如果有未提交的更改
git add .
git commit -m "feat: prepare for Windows deployment"
git push origin feature/pfc-mcp-integration
```

### Step 1: Windows基础环境准备（15分钟）

#### 1.1 启用SSH服务器
```powershell
# 以管理员身份运行PowerShell

# 安装OpenSSH Server
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# 启动SSH服务
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'

# 配置防火墙
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' `
    -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22

# 测试SSH服务
Get-Service sshd  # 应该显示 Running
```

#### 1.2 配置SSH密钥认证
```powershell
# 创建.ssh目录（如果不存在）
mkdir C:\Users\$env:USERNAME\.ssh

# 设置正确的权限
icacls C:\Users\$env:USERNAME\.ssh /inheritance:r
icacls C:\Users\$env:USERNAME\.ssh /grant:r "$env:USERNAME:(F)"
```

从Mac复制公钥：
```bash
# 在Mac上执行
cat ~/.ssh/id_rsa.pub | ssh username@windows-ip "cat >> C:/Users/username/.ssh/authorized_keys"

# 测试SSH连接
ssh username@windows-ip
```

### Step 2: 安装必要软件（20分钟）

在Windows PowerShell（管理员）中：
```powershell
# 安装Chocolatey包管理器
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 重启PowerShell后继续

# 安装开发工具
choco install git -y
choco install python -y
choco install nodejs -y
choco install vscode -y

# 验证安装
git --version
python --version
node --version
```

### Step 3: 克隆项目（5分钟）

```powershell
# 创建项目目录
mkdir C:\Projects
cd C:\Projects

# 克隆项目
git clone https://github.com/yusong652/toyoura-nagisa.git
cd toyoura-nagisa

# 切换到正确的分支
git checkout feature/pfc-mcp-integration
git pull
```

### Step 4: 配置Python环境（10分钟）

```powershell
# 安装UV包管理器
pip install uv

# 安装项目依赖
cd C:\Projects\toyoura-nagisa
uv sync

# 验证安装
uv run python -c "print('Environment ready!')"
```

### Step 5: 配置文件设置（5分钟）

#### 方案A：快速开始（开发环境）
```powershell
# 复制示例配置
Copy-Item backend\config_example\* backend\config\ -Recurse

# 创建.env文件
@"
GEMINI_API_KEY=your-gemini-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
ENVIRONMENT=development
"@ | Out-File -FilePath .env -Encoding UTF8
```

#### 方案B：从Mac安全传输配置
```bash
# 在Mac上打包配置
cd /Users/hanyusong/toyoura-nagisa
tar czf config.tar.gz backend/config/*.py .env

# 安全传输到Windows
scp config.tar.gz username@windows-ip:C:/Projects/toyoura-nagisa/

# Windows上解压
# 在PowerShell中
tar -xzf config.tar.gz
Remove-Item config.tar.gz
```

### Step 6: VSCode Remote配置（10分钟）

#### Mac端设置：
1. 安装VSCode Remote-SSH扩展
2. 配置SSH：
```bash
# ~/.ssh/config
Host windows-dev
    HostName YOUR_WINDOWS_IP
    User YOUR_USERNAME
    Port 22
    IdentityFile ~/.ssh/id_rsa
```

3. 连接测试：
```bash
# 命令行测试
ssh windows-dev

# VSCode连接
code --remote ssh-remote+windows-dev /C/Projects/toyoura-nagisa
```

### Step 7: 测试运行（5分钟）

在Windows上测试项目：
```powershell
cd C:\Projects\toyoura-nagisa

# 测试MCP服务器
uv run python backend\infrastructure\mcp\smart_mcp_server.py

# 新开一个终端，测试API服务器
uv run python backend\app.py

# 测试前端（可选）
cd frontend
npm install
npm run dev
```

## 🚀 快速检查清单

```markdown
□ Step 0: Mac上代码已提交推送
□ Step 1: Windows SSH服务器运行中
□ Step 2: Git、Python、Node.js已安装
□ Step 3: 项目已克隆到C:\Projects\toyoura-nagisa
□ Step 4: Python依赖已安装（uv sync成功）
□ Step 5: 配置文件已设置
□ Step 6: VSCode可以远程连接
□ Step 7: 服务可以正常启动
```

## 💡 常见问题快速解决

### SSH连接失败
```powershell
# 检查服务状态
Get-Service sshd

# 检查防火墙
Get-NetFirewallRule -Name sshd

# 查看SSH日志
Get-EventLog -LogName System -Source sshd -Newest 10
```

### Python包安装失败
```powershell
# 使用国内镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 重新安装
uv sync
```

### 权限问题
```powershell
# 以管理员身份运行
Start-Process powershell -Verb RunAs
```

## 🎯 最优路径（30分钟完成）

如果你想最快完成部署：

1. **先在Mac提交代码**（2分钟）
2. **Windows启用SSH**（5分钟）
3. **安装Python和Git**（10分钟）
4. **克隆项目**（3分钟）
5. **安装依赖**（5分钟）
6. **配置VSCode Remote**（5分钟）

完成！现在你可以：
- 在Mac上用VSCode编辑
- 代码在Windows上运行
- 直接访问Windows上的商业软件

## 下一步优化（可选）

完成基础部署后，可以考虑：

1. **Cloudflare Tunnel**：实现外网访问
2. **自动同步脚本**：文件变更自动同步
3. **Docker容器化**：更好的环境隔离
4. **CI/CD pipeline**：自动化部署流程

---

**立即开始**: 从Step 0开始，先提交当前代码！