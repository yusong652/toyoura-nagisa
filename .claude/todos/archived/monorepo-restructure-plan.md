# toyoura-nagisa Monorepo 目录结构重构计划

**日期**: 2025-11-23
**状态**: 规划阶段
**目标**: 统一项目目录结构，符合 Monorepo 最佳实践

---

## 1. 目标架构

### 1.1 新目录结构

```
toyoura-nagisa/
├── packages/                    # 所有可复用包
│   ├── backend/                # Python FastAPI 后端
│   │   ├── pyproject.toml
│   │   ├── app.py
│   │   ├── presentation/
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── config/
│   │   └── shared/
│   ├── core/                   # TypeScript 共享核心（新建）
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── connection/     # WebSocket 管理
│   │       ├── messaging/      # 消息处理
│   │       ├── session/        # 会话管理
│   │       ├── services/       # API 服务
│   │       ├── types/          # 类型定义
│   │       └── utils/          # 工具函数
│   ├── web/                    # React Web 前端（frontend 重命名）
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.js
│   │   ├── index.html
│   │   ├── public/
│   │   └── src/
│   │       ├── components/
│   │       ├── contexts/
│   │       ├── hooks/
│   │       └── App.tsx
│   └── cli/                    # CLI 前端（保持）
│       ├── package.json
│       ├── tsconfig.json
│       └── src/
│           ├── index.tsx
│           ├── managers/
│           ├── ui/
│           └── commands/
├── services/                   # 独立运行的服务
│   └── pfc-server/            # PFC WebSocket 服务器
│       ├── pyproject.toml
│       ├── start_server.py
│       ├── server/
│       ├── examples/
│       └── README.md
├── workspace/                  # UV 工作区（保持现状）
│   └── default/
├── scripts/                    # 构建和部署脚本
│   ├── setup.sh               # 初始化环境
│   ├── dev.sh                 # 启动开发环境
│   ├── migrate-structure.sh   # 迁移脚本
│   └── deploy.sh              # 部署脚本
├── .claude/                    # Claude Code 配置（保持）
│   ├── commands/
│   ├── guides/
│   └── todos/
├── docs/                       # 项目文档（保持）
│   └── architecture/
├── examples/                   # 示例代码（保持）
├── tests/                      # 测试（保持）
├── data/                       # 数据文件（保持）
├── memory_db/                  # ChromaDB 存储（保持）
├── package.json               # 根 package.json（npm workspaces）
├── pyproject.toml             # 根 pyproject.toml（uv workspace）
├── tsconfig.json              # 根 TypeScript 配置
├── uv.lock
├── package-lock.json
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## 2. 当前问题分析

### 2.1 目录结构不一致

| 包名 | 当前位置 | 问题 |
|------|---------|------|
| frontend | `/frontend/` | ❌ 不在 `packages/` 下 |
| cli | `/packages/cli/` | ✅ 正确位置 |
| core | 不存在 | ❌ 计划创建但位置未定 |
| backend | `/backend/` | ❌ 不在 `packages/` 下 |
| pfc-server | `/pfc-server/` | ⚠️  独立服务，应移至 `services/` |

### 2.2 配置文件分散

- `frontend/package.json` - 独立配置
- `packages/cli/package.json` - workspace 成员
- 根 `package.json` - workspace 根（但不包含 frontend）
- 根 `pyproject.toml` - Python workspace 根

### 2.3 依赖管理混乱

**Node.js 依赖**:
- 根 `node_modules/` - 包含 concurrently 等工具
- `frontend/node_modules/` - Web 前端依赖
- `packages/cli/node_modules/` - CLI 依赖

**Python 依赖**:
- `.venv/` - 后端 Python 依赖
- PFC 环境 - pfc-server 依赖（独立）

---

## 3. 迁移计划

### Phase 1: 备份和准备（30分钟）

#### 1.1 创建备份

```bash
# 备份当前状态
git checkout -b backup/pre-restructure
git add .
git commit -m "backup: pre-restructure snapshot"
git tag backup-2025-11-23

# 创建迁移分支
git checkout -b refactor/monorepo-restructure
```

#### 1.2 清理 node_modules

```bash
# 删除所有 node_modules（稍后重新安装）
rm -rf node_modules
rm -rf frontend/node_modules
rm -rf packages/cli/node_modules

# 保留 lock 文件
# package-lock.json 保留
```

---

### Phase 2: 创建新目录结构（1小时）

#### 2.1 创建 packages/ 目录结构

```bash
# 创建 packages/core
mkdir -p packages/core/src/{connection,messaging,session,services,types,utils}

# 移动 backend 到 packages/
mv backend packages/backend

# 移动 frontend 到 packages/web
mv frontend packages/web

# packages/cli 已经在正确位置，无需移动
```

#### 2.2 创建 services/ 目录

```bash
# 创建 services/
mkdir -p services

# 移动 pfc-server 到 services/
mv pfc-server services/pfc-server
```

#### 2.3 创建 scripts/ 目录

```bash
mkdir -p scripts
```

---

### Phase 3: 更新配置文件（2小时）

#### 3.1 更新根 `package.json`

**位置**: `/package.json`

```json
{
  "name": "ainagisa-monorepo",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "workspaces": [
    "packages/core",
    "packages/web",
    "packages/cli"
  ],
  "scripts": {
    "dev:backend": "uv run python packages/backend/app.py",
    "dev:web": "npm -w @toyoura-nagisa/web run dev",
    "dev:cli": "npm -w @toyoura-nagisa/cli run dev",
    "dev:all": "concurrently \"npm run dev:backend\" \"npm run dev:web\"",
    "build:core": "npm -w @toyoura-nagisa/core run build",
    "build:web": "npm -w @toyoura-nagisa/web run build",
    "build:cli": "npm -w @toyoura-nagisa/cli run build",
    "build:all": "npm run build:core && npm run build:web && npm run build:cli",
    "clean": "rm -rf packages/*/dist packages/*/node_modules node_modules",
    "install:all": "npm install",
    "test:backend": "uv run pytest",
    "test:web": "npm -w @toyoura-nagisa/web run test",
    "lint:web": "npm -w @toyoura-nagisa/web run lint"
  },
  "devDependencies": {
    "concurrently": "^9.2.1",
    "typescript": "^5.3.3"
  },
  "engines": {
    "node": ">=18.0.0",
    "npm": ">=9.0.0"
  }
}
```

#### 3.2 更新根 `pyproject.toml`

**位置**: `/pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ainagisa"
version = "0.1.0"
description = "AI Nagisa - Production-grade AI agent platform"
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
authors = [
    { name = "yusong", email = "yusong.han.652@gmail.com" }
]
dependencies = [
    # ... (keep all existing dependencies)
]

[project.urls]
Homepage = "https://github.com/yusong652/toyoura-nagisa"
"Bug Tracker" = "https://github.com/yusong652/toyoura-nagisa/issues"

[tool.hatch.build.targets.wheel]
packages = ["packages/backend"]

[tool.uv]
dev-dependencies = [
    "pytest",
    "pytest-cov",
    "tiktoken>=0.9.0",
]

[tool.uv.workspace]
members = [
    "packages/backend",
    "workspace/default/toyoura-nagisa_uv_workspace/toyoura-nagisa-uv-plot"
]
# Note: services/pfc-server NOT included
# It runs in PFC's embedded Python environment

[project.optional-dependencies]
dev = [
    "github-cli",
]
```

#### 3.3 创建 `packages/core/package.json`

**位置**: `/packages/core/package.json`

```json
{
  "name": "@toyoura-nagisa/core",
  "version": "0.1.0",
  "description": "Shared core logic for toyoura-nagisa web and CLI",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    },
    "./connection": {
      "types": "./dist/connection/index.d.ts",
      "import": "./dist/connection/index.js"
    },
    "./messaging": {
      "types": "./dist/messaging/index.d.ts",
      "import": "./dist/messaging/index.js"
    },
    "./session": {
      "types": "./dist/session/index.d.ts",
      "import": "./dist/session/index.js"
    },
    "./services": {
      "types": "./dist/services/index.d.ts",
      "import": "./dist/services/index.js"
    },
    "./types": {
      "types": "./dist/types/index.d.ts",
      "import": "./dist/types/index.js"
    }
  },
  "scripts": {
    "build": "tsc",
    "clean": "rm -rf dist",
    "dev": "tsc --watch",
    "test": "vitest"
  },
  "keywords": ["toyoura-nagisa", "core", "shared"],
  "author": "toyoura-nagisa Team",
  "license": "MIT",
  "dependencies": {
    "eventemitter3": "^5.0.1"
  },
  "devDependencies": {
    "@types/node": "^20.11.5",
    "typescript": "^5.3.3",
    "vitest": "^2.0.0"
  }
}
```

#### 3.4 创建 `packages/core/tsconfig.json`

**位置**: `/packages/core/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "lib": ["ES2022"],
    "moduleResolution": "bundler",
    "outDir": "./dist",
    "rootDir": "./src",
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "**/*.test.ts"]
}
```

#### 3.5 更新 `packages/web/package.json`

**位置**: `/packages/web/package.json`

**变更**:
- 更新 `name` 为 `@toyoura-nagisa/web`
- 添加 `@toyoura-nagisa/core` 依赖

```json
{
  "name": "@toyoura-nagisa/web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "node -e \"console.log('[Frontend] Waiting 5 seconds for backend...'); setTimeout(() => process.exit(0), 5000)\" && vite",
    "dev:nodelay": "vite",
    "build": "vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "@toyoura-nagisa/core": "*",
    "@emotion/react": "^11.11.4",
    "@emotion/styled": "^11.11.0",
    "@mui/icons-material": "^5.18.0",
    "@mui/material": "^5.15.12",
    "@types/dompurify": "^3.0.5",
    "@types/marked": "^5.0.2",
    "@types/uuid": "^10.0.0",
    "dompurify": "^3.2.6",
    "marked": "^15.0.12",
    "pixi-live2d-display": "0.5.0-beta",
    "pixi.js": "7.4.0",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
    "uuid": "^11.1.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.25.0",
    "@types/react": "^19.1.2",
    "@types/react-dom": "^19.1.2",
    "@vitejs/plugin-react": "^4.4.1",
    "concurrently": "^9.2.1",
    "eslint": "^9.25.0",
    "eslint-plugin-react-hooks": "^5.2.0",
    "eslint-plugin-react-refresh": "^0.4.19",
    "globals": "^16.0.0",
    "vite": "^6.3.5"
  }
}
```

#### 3.6 更新 `packages/cli/package.json`

**位置**: `/packages/cli/package.json`

**变更**: 已经正确，无需修改

#### 3.7 更新 `packages/backend/pyproject.toml`

**创建新文件**: `/packages/backend/pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ainagisa-backend"
version = "0.1.0"
description = "toyoura-nagisa FastAPI backend"
requires-python = ">=3.10"

dependencies = [
    # Copy from root pyproject.toml dependencies
]

[tool.hatch.build.targets.wheel]
packages = ["backend"]
```

---

### Phase 4: 更新导入路径（2小时）

#### 4.1 更新 backend 中的路径引用

**需要更新的文件**:
- `packages/backend/app.py`
- 所有 Python 文件中的相对导入

**示例变更**:
```python
# Before
from backend.infrastructure.mcp import mcp_server

# After (保持不变，因为 backend 仍然是包名)
from backend.infrastructure.mcp import mcp_server
```

**Note**: Python 导入路径无需修改，因为 `backend` 仍然是顶层包名

#### 4.2 更新 frontend → web 的引用

**需要更新的文件**:
- `packages/web/vite.config.js`
- `packages/web/index.html`
- README.md
- CLAUDE.md

**示例变更**:
```javascript
// vite.config.js - 无需修改（使用相对路径）
export default defineConfig({
  root: '.',  // 保持不变
  // ...
})
```

#### 4.3 更新文档中的路径引用

**需要更新的文件**:
- `README.md`
- `CLAUDE.md`
- `.claude/guides/*.md`
- `.claude/todos/*.md`

**示例变更**:
```markdown
# Before
frontend/src/components/ChatBox.tsx

# After
packages/web/src/components/ChatBox.tsx
```

---

### Phase 5: 创建辅助脚本（1小时）

#### 5.1 创建 `scripts/setup.sh`

```bash
#!/bin/bash
# 环境初始化脚本

echo "🚀 Setting up toyoura-nagisa development environment..."

# 1. 安装 Python 依赖
echo "📦 Installing Python dependencies..."
uv sync

# 2. 安装 Node.js 依赖
echo "📦 Installing Node.js dependencies..."
npm install

# 3. 构建 core 包
echo "🔨 Building @toyoura-nagisa/core..."
npm run build:core

echo "✅ Setup complete! Run 'npm run dev:all' to start."
```

#### 5.2 创建 `scripts/dev.sh`

```bash
#!/bin/bash
# 启动开发环境

echo "🚀 Starting toyoura-nagisa development environment..."

# 使用 concurrently 同时启动 backend 和 frontend
npm run dev:all
```

#### 5.3 创建 `scripts/migrate-structure.sh`

```bash
#!/bin/bash
# 自动迁移目录结构

set -e  # 遇到错误立即退出

echo "🔄 Migrating toyoura-nagisa directory structure..."

# 备份
echo "📦 Creating backup..."
git checkout -b backup/pre-restructure
git add .
git commit -m "backup: pre-restructure snapshot" || true

# 创建迁移分支
echo "🌿 Creating migration branch..."
git checkout -b refactor/monorepo-restructure

# 创建新目录
echo "📁 Creating new directories..."
mkdir -p packages/core/src/{connection,messaging,session,services,types,utils}
mkdir -p services

# 移动目录
echo "🚚 Moving directories..."
[ -d backend ] && mv backend packages/backend
[ -d frontend ] && mv frontend packages/web
[ -d pfc-server ] && mv pfc-server services/pfc-server

# 清理 node_modules
echo "🧹 Cleaning node_modules..."
rm -rf node_modules packages/*/node_modules

echo "✅ Migration complete! Next steps:"
echo "1. Update configuration files"
echo "2. Run 'npm install'"
echo "3. Run 'npm run build:core'"
echo "4. Test the application"
```

---

### Phase 6: 测试和验证（1小时）

#### 6.1 安装依赖

```bash
# 安装所有依赖
npm install

# 验证 workspace 配置
npm ls --all
```

#### 6.2 构建测试

```bash
# 构建 core
npm run build:core

# 构建 web
npm run build:web

# 构建 cli
npm run build:cli
```

#### 6.3 运行测试

```bash
# 启动后端
npm run dev:backend

# 在另一个终端启动前端
npm run dev:web

# 验证功能正常
# - WebSocket 连接
# - 消息发送
# - 会话管理
```

#### 6.4 验证 CLI

```bash
# 启动 CLI
npm run dev:cli

# 测试基本功能
```

---

### Phase 7: 提交和部署（30分钟）

#### 7.1 提交代码

```bash
git add .
git commit -m "refactor: restructure project to monorepo layout

- Move backend to packages/backend
- Rename frontend to packages/web
- Move pfc-server to services/pfc-server
- Create packages/core for shared logic
- Update all configuration files
- Add migration scripts

https://github.com/yusong652/toyoura-nagisa

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>"
```

#### 7.2 创建 PR

```bash
gh pr create \
  --title "refactor: restructure project to monorepo layout" \
  --body "$(cat <<'EOF'
## Summary

Restructure toyoura-nagisa to follow monorepo best practices:

- ✅ All packages in `packages/` directory
- ✅ Independent services in `services/` directory
- ✅ Unified workspace configuration (npm + uv)
- ✅ Clear separation of concerns

## Changes

### Directory Structure
- `backend/` → `packages/backend/`
- `frontend/` → `packages/web/`
- `pfc-server/` → `services/pfc-server/`
- Create `packages/core/` for shared TypeScript logic

### Configuration
- Updated root `package.json` with workspaces
- Updated root `pyproject.toml` with new paths
- Created `packages/core/package.json`
- Updated `packages/web/package.json`

### Scripts
- Added `scripts/setup.sh` - Environment initialization
- Added `scripts/dev.sh` - Development startup
- Added `scripts/migrate-structure.sh` - Automated migration

## Testing

- [x] Backend starts successfully
- [x] Web frontend builds and runs
- [x] CLI builds and runs
- [x] All imports resolved correctly
- [x] WebSocket connection works
- [x] Message sending works

## Migration Guide

For developers pulling this change:

```bash
# 1. Pull the latest code
git pull origin refactor/monorepo-restructure

# 2. Clean old dependencies
rm -rf node_modules packages/*/node_modules .venv

# 3. Run setup script
bash scripts/setup.sh

# 4. Start development
npm run dev:all
```

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
EOF
)"
```

---

## 4. 变更影响分析

### 4.1 开发者工作流变更

**Before**:
```bash
# 启动前端
cd frontend
npm run dev

# 启动后端
cd ..
uv run python backend/app.py
```

**After**:
```bash
# 启动所有服务（推荐）
npm run dev:all

# 或分别启动
npm run dev:web
npm run dev:backend
npm run dev:cli
```

### 4.2 导入路径变更

**Frontend/Web**:
```typescript
// Before
import { ChatService } from '../services/api/chatService'

// After (使用 @toyoura-nagisa/core)
import { ChatService } from '@toyoura-nagisa/core/services'
```

**Backend**:
```python
# No change - backend imports remain the same
from backend.infrastructure.mcp import mcp_server
```

### 4.3 构建输出路径变更

**Before**:
```
frontend/dist/
backend/
pfc-server/
```

**After**:
```
packages/web/dist/
packages/core/dist/
packages/cli/dist/
packages/backend/
services/pfc-server/
```

---

## 5. 风险评估

| 风险 | 严重性 | 概率 | 缓解措施 |
|------|--------|------|----------|
| **破坏现有功能** | 高 | 中 | 完整测试、Git 备份、逐步迁移 |
| **导入路径错误** | 中 | 高 | IDE 自动重构、测试覆盖 |
| **配置文件冲突** | 中 | 中 | 仔细审查、备份原配置 |
| **依赖安装失败** | 低 | 低 | 使用 lock 文件、清理缓存 |

---

## 6. 回滚计划

如果迁移失败，可以快速回滚：

```bash
# 方案 A: 回到备份分支
git checkout backup/pre-restructure

# 方案 B: 使用 Git tag
git checkout backup-2025-11-23

# 方案 C: 重置到迁移前的提交
git reset --hard <commit-hash>
```

---

## 7. 成功标准

迁移成功的标志：

- ✅ 所有 npm workspaces 成员可以正确安装依赖
- ✅ `npm run build:all` 成功构建所有包
- ✅ `npm run dev:all` 可以同时启动后端和前端
- ✅ Web 前端正常连接后端 WebSocket
- ✅ CLI 正常运行
- ✅ 所有测试通过
- ✅ 文档路径引用正确更新

---

## 8. 后续优化

迁移完成后可以进一步优化：

### 8.1 添加 Turbo/Nx 加速构建

```bash
npm install -D turbo

# turbo.json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    }
  }
}
```

### 8.2 统一 TypeScript 配置

创建根 `tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

各包继承根配置:
```json
{
  "extends": "../../tsconfig.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  }
}
```

### 8.3 添加统一的代码规范

```bash
npm install -D eslint prettier

# .eslintrc.js
module.exports = {
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  // ...
}
```

---

## 9. 时间估算

| 阶段 | 估算时间 | 关键任务 |
|------|---------|---------|
| Phase 1: 备份准备 | 30分钟 | Git 备份、创建分支 |
| Phase 2: 创建目录 | 1小时 | 移动文件、创建结构 |
| Phase 3: 更新配置 | 2小时 | 修改所有配置文件 |
| Phase 4: 更新路径 | 2小时 | 修正导入路径、文档 |
| Phase 5: 创建脚本 | 1小时 | 编写辅助脚本 |
| Phase 6: 测试验证 | 1小时 | 功能测试 |
| Phase 7: 提交部署 | 30分钟 | Git 提交、PR |
| **总计** | **8小时** | **完整迁移** |

---

## 10. 执行清单

迁移时逐项检查：

### 准备阶段
- [ ] 阅读完整迁移计划
- [ ] 确认当前代码已提交
- [ ] 创建备份分支
- [ ] 创建迁移分支

### 执行阶段
- [ ] 创建 `packages/core` 目录结构
- [ ] 移动 `backend` → `packages/backend`
- [ ] 移动 `frontend` → `packages/web`
- [ ] 移动 `pfc-server` → `services/pfc-server`
- [ ] 更新根 `package.json`
- [ ] 更新根 `pyproject.toml`
- [ ] 创建 `packages/core/package.json`
- [ ] 创建 `packages/core/tsconfig.json`
- [ ] 更新 `packages/web/package.json`
- [ ] 更新 `packages/backend/pyproject.toml`
- [ ] 更新文档路径引用
- [ ] 创建 `scripts/` 辅助脚本

### 验证阶段
- [ ] 清理 node_modules
- [ ] `npm install` 成功
- [ ] `npm run build:core` 成功
- [ ] `npm run build:web` 成功
- [ ] `npm run dev:backend` 成功
- [ ] `npm run dev:web` 成功
- [ ] WebSocket 连接正常
- [ ] 消息发送正常
- [ ] `npm run dev:cli` 成功

### 完成阶段
- [ ] Git 提交代码
- [ ] 创建 PR
- [ ] 更新 README.md
- [ ] 通知团队成员

---

## 11. 参考资料

- [npm workspaces 官方文档](https://docs.npmjs.com/cli/v10/using-npm/workspaces)
- [uv workspace 文档](https://docs.astral.sh/uv/concepts/workspaces/)
- [Monorepo 最佳实践](https://monorepo.tools/)
- [Turborepo 文档](https://turbo.build/repo/docs)

---

**状态**: ✅ 准备执行
**审核**: 待审核
**预计完成**: 2025-11-24
