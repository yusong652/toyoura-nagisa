# Message Component Architecture

## 目录结构设计

```
Message/
├── README.md                     # 架构文档
├── index.ts                      # 导出入口
├── MessageItem.tsx              # 主容器组件 (重构后)
├── MessageItem.css              # 样式文件
├── types.ts                     # 类型定义
├── hooks/                       # 消息相关 hooks
│   ├── useMessageState.ts       # 消息状态管理
│   ├── useMessageEvents.ts      # 消息事件处理
│   └── useStreamingText.ts      # 流式文本处理
├── renderers/                   # 消息渲染器
│   ├── UserMessageRenderer.tsx  # 用户消息渲染
│   ├── BotMessageRenderer.tsx   # 机器人消息渲染
│   └── StreamingTextRenderer.tsx # 流式文本渲染
├── content/                     # 内容组件
│   ├── MessageText.tsx          # 文本内容
│   ├── MessageFiles.tsx         # 文件列表
│   ├── MessageStatus.tsx        # 消息状态
│   └── MessageTimestamp.tsx     # 时间戳
├── files/                       # 文件处理组件
│   ├── FilePreview.tsx          # 文件预览基础组件
│   ├── ImageFile.tsx            # 图片文件组件
│   ├── VideoFile.tsx            # 视频文件组件
│   └── DocumentFile.tsx         # 文档文件组件
├── avatar/                      # 头像组件
│   ├── MessageAvatar.tsx        # 消息头像
│   └── AvatarTooltip.tsx        # 头像提示信息
└── actions/                     # 操作组件
    ├── MessageActions.tsx       # 消息操作容器
    ├── DeleteButton.tsx         # 删除按钮
    └── SelectButton.tsx         # 选择按钮
```

## 设计原则

1. **单一责任原则**: 每个组件只负责一个特定功能
2. **组件组合**: 通过小组件组合构建复杂功能
3. **状态分离**: 将复杂状态管理拆分到专门的 hooks
4. **类型安全**: 完整的 TypeScript 类型支持
5. **可测试性**: 每个组件都可独立测试
6. **可复用性**: 组件可在其他地方复用

## 核心组件职责

### MessageItem (主容器)
- 消息布局和结构
- 事件委托和状态协调
- 子组件组合

### 渲染器 (Renderers)
- UserMessageRenderer: 用户消息的简单渲染
- BotMessageRenderer: 机器人消息的复杂渲染
- StreamingTextRenderer: 流式文本的专门处理

### 内容组件 (Content)
- MessageText: 纯文本内容渲染
- MessageFiles: 文件列表管理
- MessageStatus: 消息状态显示
- MessageTimestamp: 时间戳格式化

### 文件组件 (Files)
- FilePreview: 文件预览基础逻辑
- ImageFile: 图片文件专门处理
- VideoFile: 视频文件专门处理
- DocumentFile: 文档文件处理

### Hooks
- useMessageState: 消息状态管理 (displayText, streaming, etc.)
- useMessageEvents: 事件处理 (click, delete, select)
- useStreamingText: 流式文本逻辑

## 数据流设计

```
MessageItem (容器)
    ↓ props
UserMessageRenderer / BotMessageRenderer
    ↓ 渲染逻辑
MessageText + MessageFiles + MessageStatus + MessageTimestamp
    ↓ 文件处理
ImageFile / VideoFile / DocumentFile
```

## 类型系统

- 统一的消息类型接口
- 渲染器特定的 props 类型
- 事件处理器类型
- 文件类型枚举