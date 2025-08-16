# aiNagisa 记忆系统架构设计

## 📋 项目概述

**目标**: 将aiNagisa从"工具调用器"升级为"认知Agent"，记忆系统从可选工具升级为认知基础设施

**核心理念**:
> "记忆不应该是可选的工具，而应该是Agent的认知基础设施。就像人类不会'选择'是否使用记忆，Agent的记忆应该始终在线、自动激活。"

## 🏗️ 总体架构设计

### 现状分析

**当前实现 (Tool-Based Memory):**

```
用户消息 → LLM推理 → [用户选择调用记忆工具] → 记忆检索 → 响应
```

**目标架构 (Infrastructure Memory):**

```
用户消息 → 记忆自动注入 → 增强上下文 → LLM推理 → 响应 → 记忆更新
```

### 架构分层

```
┌─────────────────────────────────────────────────────────┐
│                   Presentation Layer                   │
│  ┌─────────────────┐  ┌─────────────────────────────────┐ │
│  │  Chat Handler   │  │    Memory Injection Middleware │ │
│  │  (handlers.py)  │  │    (inject_memory_context)     │ │
│  └─────────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                    Domain Layer                         │
│  ┌─────────────────┐  ┌─────────────────────────────────┐ │
│  │ Message Factory │  │      Memory Context Manager    │ │
│  │  (enhanced)     │  │     (智能记忆检索与格式化)       │ │
│  └─────────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                Infrastructure Layer                     │
│  ┌─────────────────┐  ┌─────────────────────────────────┐ │
│  │ Memory Manager  │  │       Storage Backends          │ │
│  │   (enhanced)    │  │  ┌─────────┐  ┌─────────────────┐│ │
│  │                 │  │  │ChromaDB │  │  Future: Mem0/  ││ │
│  │                 │  │  │(Vector) │  │  Zep (Hybrid)   ││ │
│  │                 │  │  └─────────┘  └─────────────────┘│ │
│  └─────────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 🎯 Phase 1: 记忆基础设施核心 (1-2周)

### 核心组件设计

#### 1. Memory Injection Middleware

**文件位置**: `backend/presentation/streaming/handlers.py`

```python
async def inject_memory_context(
    messages: List[Any], 
    session_id: str,
    memory_manager: MemoryManager
) -> List[Any]:
    """
    在LLM推理前自动注入相关记忆上下文。
    
    Args:
        messages: 原始用户消息列表
        session_id: 当前会话ID
        memory_manager: 记忆管理器实例
    
    Returns:
        List[Any]: 包含记忆上下文的增强消息列表
        
    Example:
        原始消息: ["用户: 我想喝点什么"]
        增强后: [
            "系统: [Memory Context] 用户偏好咖啡，不喜欢茶类饮品",
            "用户: 我想喝点什么"
        ]
    """
```

**核心逻辑:**

1. 提取用户最新消息的语义向量
2. 检索相关记忆（TOP-5，排除最近对话）
3. 格式化记忆为系统消息
4. 插入到消息列表开头

#### 2. Enhanced Memory Manager

**文件位置**: `backend/infrastructure/memory/memory_manager.py`

**新增方法:**

```python
async def get_relevant_memories_for_context(
    self, 
    query_text: str, 
    session_id: str,
    top_k: int = 5,
    exclude_recent_minutes: int = 10
) -> List[RelevantMemory]:
    """
    为上下文注入检索相关记忆。
    
    Features:
    - 语义相似度检索
    - 时间过滤（避免重复最近对话）
    - 相关性评分
    - 记忆类型分类
    """
```

**记忆数据结构增强:**

```python
@dataclass
class EnhancedMemory:
    content: str
    embedding: List[float]
    timestamp: datetime
    session_id: str
    memory_type: Literal["fact", "preference", "context", "event"]
    confidence: float = 0.8
    expires_at: Optional[datetime] = None
    source: str = "conversation"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### 3. Handle LLM Response 流程修改

**修改位置**: `backend/presentation/streaming/handlers.py`

**当前流程:**

```python
async def handle_llm_response(messages, session_id, ...):
    # 直接调用LLM
    response = await llm_client.get_response(messages, ...)
```

**增强流程:**

```python
async def handle_llm_response(messages, session_id, ...):
    # 1. 记忆注入
    enhanced_messages = await inject_memory_context(
        messages, session_id, memory_manager
    )
    
    # 2. LLM推理
    response = await llm_client.get_response(enhanced_messages, ...)
    
    # 3. 记忆更新（可选，在响应完成后）
    await update_memory_from_conversation(messages, response, session_id)
```

### API接口设计

#### Memory Context API

```python
# 记忆注入接口
POST /api/memory/inject
{
    "messages": [...],
    "session_id": "uuid",
    "options": {
        "top_k": 5,
        "exclude_recent_minutes": 10,
        "memory_types": ["preference", "fact"]
    }
}

# 响应
{
    "enhanced_messages": [...],
    "injected_memories": [
        {
            "content": "用户偏好咖啡",
            "relevance_score": 0.89,
            "timestamp": "2024-08-06T10:30:00Z",
            "memory_type": "preference"
        }
    ],
    "processing_time_ms": 45
}
```

## 🕐 Phase 2: 时间感知增强 (2-3周)

### 记忆分层系统

```python
class MemoryTier:
    """记忆分层管理"""
    
    LONG_TERM = "long_term"      # 用户偏好、重要事实 (30+ 天)
    MEDIUM_TERM = "medium_term"  # 会话上下文 (7-30 天)
    SHORT_TERM = "short_term"    # 工作记忆 (1-7 天)
    WORKING = "working"          # 当前对话 (会话内)

class MemoryDecayPolicy:
    """记忆衰减策略"""
    
    @staticmethod
    def calculate_relevance_weight(
        base_score: float,
        age_days: int,
        memory_type: str
    ) -> float:
        """根据时间和类型计算记忆权重"""
        decay_rates = {
            "preference": 0.01,  # 偏好记忆衰减慢
            "fact": 0.02,       # 事实记忆中等衰减
            "context": 0.05,    # 上下文记忆衰减快
            "event": 0.03       # 事件记忆中等衰减
        }
        
        decay_rate = decay_rates.get(memory_type, 0.03)
        time_weight = math.exp(-decay_rate * age_days)
        return base_score * time_weight
```

### 记忆冲突解决

```python
class MemoryConflictResolver:
    """处理记忆冲突和更新"""
    
    async def resolve_conflicting_memories(
        self,
        new_memory: Memory,
        existing_memories: List[Memory]
    ) -> List[MemoryAction]:
        """
        解决记忆冲突:
        - 标记过时记忆为invalid
        - 保留历史版本用于追溯
        - 更新相关记忆的置信度
        """
```

## 🚀 Phase 3: 混合架构评估 (3-4周)

### 技术方案对比

| 指标 | 现有ChromaDB增强 | Mem0集成 | Zep/Graphiti |
|------|------------------|----------|--------------|
| **开发成本** | 低 (2周) | 中 (3-4周) | 高 (6-8周) |
| **维护复杂度** | 低 | 中 | 高 |
| **功能完整性** | 75% | 90% | 95% |
| **时间感知** | 基础 | 完整 | 高级 |
| **关系推理** | 无 | 基础 | 高级 |
| **迁移成本** | 无 | 中等 | 高 |

### 渐进式迁移策略

```python
class HybridMemoryManager:
    """混合记忆管理器 - 支持平滑迁移"""
    
    def __init__(self):
        self.primary_backend = ChromaDBManager()    # 现有系统
        self.secondary_backend = None               # 未来系统
        self.migration_mode = False
    
    async def search_memories(self, query: str) -> List[Memory]:
        if not self.migration_mode:
            return await self.primary_backend.search(query)
        
        # 双写双读模式
        primary_results = await self.primary_backend.search(query)
        secondary_results = await self.secondary_backend.search(query)
        
        # 结果合并和验证
        return self.merge_and_validate(primary_results, secondary_results)
```

## 📊 预期收益

### 用户体验提升

- **减少重复解释**: 记忆自动激活，用户无需重复说明偏好
- **上下文连续性**: Agent展现明显的"记忆连续性"
- **个性化响应**: 基于历史偏好提供个性化建议

### 系统性能优化

- **记忆命中率**: 目标 >80% 相关记忆成功检索
- **响应延迟**: 记忆注入增加 <200ms
- **Token效率**: 相比全量上下文减少60-80% token消耗

### 技术指标

```python
class MemorySystemMetrics:
    """记忆系统监控指标"""
    
    memory_hit_rate: float          # 记忆命中率
    average_injection_latency: int  # 注入延迟(ms)
    memory_relevance_score: float   # 记忆相关性评分
    context_compression_ratio: float # 上下文压缩比
    user_satisfaction_score: float  # 用户满意度
```

## 🛡️ 风险控制

### 向后兼容策略

1. **保留现有工具**: search_memory工具保持可用
2. **渐进式启用**: 通过配置开关控制记忆自动注入
3. **降级机制**: 记忆服务异常时自动降级到无记忆模式

### 性能保障

```python
# 性能保护机制
class MemoryPerformanceGuard:
    MAX_INJECTION_TIME_MS = 200
    MAX_MEMORY_CONTEXT_TOKENS = 1000
    FALLBACK_ON_TIMEOUT = True
    
    async def safe_inject_memory(self, messages, session_id):
        try:
            with timeout(self.MAX_INJECTION_TIME_MS / 1000):
                return await self.inject_memory_context(messages, session_id)
        except TimeoutError:
            if self.FALLBACK_ON_TIMEOUT:
                return messages  # 降级到原始消息
            raise
```

## 📝 实施路线图

### Week 1: 核心基础设施

- [x] 架构设计文档
- [ ] inject_memory_context 函数实现
- [ ] memory_manager 增强
- [ ] handle_llm_response 流程修改

### Week 2: 集成测试

- [ ] 记忆注入功能测试
- [ ] 性能基准测试
- [ ] 用户体验验证

### Week 3-4: 时间感知

- [ ] 记忆分层系统
- [ ] 时间衰减机制
- [ ] 冲突解决策略

### Week 5-6: 架构评估

- [ ] Mem0/Zep 技术预研
- [ ] 性能对比测试
- [ ] 迁移方案设计

## 🔗 相关文件结构

```
backend/
├── presentation/
│   └── streaming/
│       └── handlers.py              # inject_memory_context
├── domain/
│   └── models/
│       ├── message_factory.py       # 增强消息工厂
│       └── memory_context.py        # 新增记忆上下文模型
└── infrastructure/
    └── memory/
        ├── memory_manager.py         # 增强记忆管理器
        ├── memory_types.py           # 记忆类型定义
        ├── memory_injection.py       # 记忆注入逻辑
        └── hybrid_manager.py         # 混合架构支持
```

---

**设计原则**:

1. **渐进式演进** - 避免大爆炸式重写
2. **向后兼容** - 保持现有功能稳定
3. **性能优先** - 记忆注入不能显著影响响应速度
4. **可观测性** - 完整的监控和调试能力

*"今天我们要实现的不只是功能改进，而是认知架构的根本性升级。"*
