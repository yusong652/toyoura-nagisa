# 图生视频功能实现总结

## 概述

基于 AnimateDiff 的图生视频功能已经成功集成到 aiNagisa 系统中，实现了从静态图片生成动态视频的完整流程。

## 架构设计

### 整体流程
1. **前端触发** → 用户点击图片上的视频生成按钮
2. **API 调用** → 前端调用 `/api/generate-video` 接口
3. **后端处理** → 自动找到最新图片，获取原始 prompt，优化为视频 prompt
4. **视频生成** → 调用 AnimateDiff API 生成视频
5. **结果返回** → 视频保存到本地，添加到聊天历史

### 技术栈
- **后端**: FastAPI + FastMCP + AnimateDiff
- **前端**: React + TypeScript + Material-UI
- **视频生成**: AnimateDiff WebUI API
- **存储**: 本地文件系统 + Base64

## 实现细节

### 后端架构

#### 1. 配置系统
**文件**: `backend/config/image_to_video.py`
- `AnimateDiffConfig`: AnimateDiff WebUI 配置
- `ImageToVideoSettings`: 通用设置和运动预设
- 支持多种运动类型：gentle, dynamic, cinematic, loop

#### 2. MCP 工具实现
**文件**: `backend/infrastructure/mcp/tools/lifestyle/tools/image_to_video/image_to_video.py`

核心功能：
- `get_latest_text_to_image_prompt()`: 从 history 文件获取最新的文生图 prompt
- `optimize_prompt_for_video()`: 将静态图 prompt 优化为视频 prompt
- `call_animatediff_api()`: 调用 AnimateDiff API 生成视频
- `find_recent_image_in_messages()`: 找到最近的 AI 生成图片
- `generate_video_from_context()`: 完整的视频生成流程

#### 3. API 接口
**文件**: `backend/presentation/api/content.py`
- 新增 `/api/generate-video` POST 接口
- 使用 `GenerateVideoRequest` 模型
- 集成到 ContentService 服务层

#### 4. 业务服务层
**文件**: `backend/domain/services/content_service.py`
- `generate_video_for_session()`: 会话级视频生成服务
- 使用 MockContext 桥接 MCP 工具调用
- 集成视频存储功能

#### 5. 存储层
**文件**: `backend/infrastructure/storage/video_storage.py`
- `save_video_from_base64()`: 保存 base64 视频到文件
- `_create_and_save_video_message()`: 创建视频消息并添加到聊天历史
- 支持 mp4, gif, webm 格式

### 前端实现

#### 1. 视频生成组件
**文件**: `frontend/src/components/ImageWithVideoAction.tsx`
- 悬浮在图片上的视频生成按钮
- 调用后端 API 进行视频生成
- 支持进度显示和错误处理

#### 2. 视频播放器
**文件**: `frontend/src/components/VideoPlayer.tsx`
- 全屏视频播放器
- 支持多种视频格式
- 键盘快捷键支持（ESC 关闭）

#### 3. 消息组件集成
**文件**: `frontend/src/components/MessageItem.tsx`
- 在 AI 生成的图片上显示视频生成按钮
- 仅对 bot 消息显示，用户上传的图片不显示

## 核心创新点

### 1. 智能 Prompt 提取
- 从文生图的 few-shot history 文件中自动获取原始 prompt
- 避免了前端传递 prompt 的复杂性
- 确保使用最准确的原始生成提示词

### 2. LLM 驱动的 Prompt 优化
- 自动将静态图描述转换为动态视频描述
- 添加运动关键词和摄像机运动
- 保持原始风格和主题的一致性

### 3. 无缝集成设计
- 复用现有的消息系统和存储架构
- 统一的配置管理系统
- 模块化的 MCP 工具架构

## 配置说明

### AnimateDiff 服务器配置
```python
# backend/config/image_to_video.py
ANIMATEDIFF_WEBUI_URL = "http://127.0.0.1:7860"
```

### 运动类型预设
- **gentle**: 轻柔运动，适合风景和静物
- **dynamic**: 动态运动，适合人物和动作
- **cinematic**: 电影级运动，专业摄像机效果
- **loop**: 循环运动，无缝循环动画

### 生成参数
- 帧数: 16 帧（可配置 8-32）
- 帧率: 8 FPS（可配置 1-30）
- CFG Scale: 7.0-8.0（根据运动类型调整）
- 去噪强度: 0.75（适合图生视频）

## 文件结构

```
aiNagisa/
├── backend/
│   ├── config/
│   │   └── image_to_video.py                    # 配置文件
│   ├── domain/services/
│   │   └── content_service.py                   # 业务服务（新增视频生成）
│   ├── infrastructure/
│   │   ├── mcp/tools/lifestyle/tools/image_to_video/
│   │   │   ├── __init__.py                      # 模块导出
│   │   │   └── image_to_video.py                # MCP 工具实现
│   │   └── storage/
│   │       └── video_storage.py                 # 视频存储模块
│   └── presentation/
│       ├── api/
│       │   └── content.py                       # API 接口（新增视频接口）
│       └── models/
│           └── api_models.py                    # API 模型（新增 GenerateVideoRequest）
└── frontend/src/components/
    ├── ImageWithVideoAction.tsx                 # 视频生成按钮组件
    ├── ImageWithVideoAction.css                 # 样式文件
    ├── VideoPlayer.tsx                          # 视频播放器组件
    ├── VideoPlayer.css                          # 播放器样式
    └── MessageItem.tsx                          # 消息组件（集成视频按钮）
```

## 使用方法

1. **生成图片**: 用户通过文生图功能生成静态图片
2. **触发视频生成**: 鼠标悬浮在图片上，点击视频图标按钮
3. **自动处理**: 系统自动提取原始 prompt，优化为视频 prompt
4. **视频生成**: 调用 AnimateDiff 生成视频
5. **结果展示**: 视频自动添加到聊天历史中

## 扩展性

### 支持更多视频生成模型
- 可轻松扩展支持 Stable Video Diffusion
- 支持 CogVideoX 等其他模型
- 统一的配置和接口设计

### 运动类型扩展
- 可添加更多预设运动类型
- 支持自定义运动参数
- 支持用户自定义运动描述

### 输出格式扩展
- 当前支持 mp4, gif, webm
- 可扩展支持更多视频格式
- 支持不同质量等级

## 技术特点

### 优点
- **自动化程度高**: 用户只需点击按钮，无需输入额外信息
- **智能 Prompt 处理**: 自动从历史中提取并优化 prompt
- **无缝集成**: 完美融入现有聊天系统
- **模块化设计**: 便于维护和扩展
- **错误处理完善**: 完整的错误提示和重试机制

### 技术亮点
- **Clean Architecture**: 严格的分层架构设计
- **MCP 协议**: 标准化的工具协调协议
- **TypeScript**: 类型安全的前端开发
- **配置驱动**: 灵活的配置管理系统

## 总结

图生视频功能的成功实现展示了 aiNagisa 系统的强大扩展性和优秀的架构设计。通过智能的 prompt 提取和优化、无缝的用户体验设计，以及模块化的技术实现，为用户提供了从静态图片到动态视频的完整创作流程。

该功能不仅技术实现优秀，更重要的是体现了以用户体验为中心的设计理念，让复杂的 AI 视频生成技术变得简单易用。