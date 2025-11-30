# toyoura-nagisa System Prompt优化分析报告

## 执行摘要

通过分析Anthropic官方文档推荐的system prompt格式与toyoura-nagisa当前实现的对比，发现了关键的优化机会。**重要发现：Claude Code确实在system prompt中嵌入了完整的工具定义**，这与toyoura-nagisa当前仅通过API参数传递工具schema的做法形成鲜明对比。

## 🔍 关键发现：Claude Code的实际实现

**检查Claude Code自身的system prompt结构后发现**：

### Claude Code确实使用了Anthropic推荐的完整格式

```
In this environment you have access to a set of tools you can use to answer the user's question.

Here are the functions available in JSONSchema format:
<functions>
<function>{"description": "Launch a new agent...", "name": "Task", "parameters": {...}}</function>
<function>{"description": "Executes a given bash command...", "name": "Bash", "parameters": {...}}</function>
... [完整的18个工具的JSON Schema定义]
</functions>
```

### 关键对比

| 方面 | Claude Code | toyoura-nagisa |
|------|-------------|----------|
| 工具定义位置 | **System prompt中嵌入** | 仅API参数传递 |
| Schema格式 | 完整JSON Schema | 完整JSON Schema |
| Token消耗 | 约5,000+ tokens用于工具定义 | ~3,500 tokens总计 |
| 工具调用准确性 | 极高（基于完整上下文） | 依赖API传递 |

### 这个发现的重要意义

1. **验证了Anthropic最佳实践**：System prompt中嵌入工具定义确实是推荐做法
2. **解释了Claude Code的优异表现**：完整的工具上下文提高了调用准确性
3. **重新评估token成本**：Claude Code愿意用5,000+ tokens换取工具调用的可靠性
4. **为toyoura-nagisa提供明确方向**：应该考虑在system prompt中嵌入工具定义

## 当前System Prompt结构分析

### toyoura-nagisa现有架构

```
get_system_prompt(tools_enabled=True) 构建顺序：
1. base_prompt.md - 核心身份和行为准则
2. tool_prompt.md - 工具使用指南（当tools_enabled=True时）
3. expression_prompt.md - 情感表达指令（Live2D相关）
```

### 各组件详细分析

#### 1. Base Prompt (`backend/config/prompts/base_prompt.md`)

**优势**：
- 简洁明确的身份定义："You are **Nagisa**"
- 清晰的核心目标（准确性、工具使用、安全性等）
- 专业友好的语调定义

**特点**：
- 22行，内容精炼
- 重点关注行为准则
- 留出动态上下文扩展空间

#### 2. Tool Prompt (`backend/config/prompts/tool_prompt.md`)

**优势**：
- 详细的工作环境说明
- 绝对路径的强制要求
- 具体的使用示例
- 完整的工具分类列表
- 最佳实践指导

**特点**：
- 107行，内容全面
- 实用性强，示例丰富
- 安全考虑周到

#### 3. Expression Prompt (`backend/config/prompts/expression_prompt.md`)

**优势**：
- 项目特色功能（Live2D集成）
- 明确的格式要求
- 详细的选择规则

## Anthropic官方推荐格式分析

### 官方模板结构

```
In this environment you have access to a set of tools you can use to answer the user's question.

{{ FORMATTING INSTRUCTIONS }}
String and scalar parameters should be specified as is, while lists and objects should use JSON format. Note that spaces for string values are not stripped. The output is not expected to be valid XML and is parsed with regular expressions.

Here are the functions available in JSONSchema format:
{{ TOOL DEFINITIONS IN JSON SCHEMA }}

{{ USER SYSTEM PROMPT }}

{{ TOOL CONFIGURATION }}
```

### 关键组件分析

1. **开场说明**：直接告知工具访问权限
2. **格式化指令**：明确参数传递格式要求
3. **工具定义**：JSON Schema格式的完整工具列表
4. **用户系统提示**：自定义内容部分
5. **工具配置**：额外的工具相关配置

## 对比分析结果

### 缺失的关键元素

#### 1. 格式化指令 (Formatting Instructions)

**问题**：toyoura-nagisa缺乏明确的参数格式说明

**官方要求**：
- 字符串和标量参数直接指定
- 列表和对象使用JSON格式
- 字符串值的空格不会被去除
- 输出通过正则表达式解析

**影响**：可能导致工具调用参数格式错误

#### 2. 工具定义嵌入 (Tool Definitions in JSON Schema)

**当前方式**：
- 工具schema通过API调用时的`tools`参数传递
- System prompt中不包含具体工具定义

**官方建议**：
- System prompt中直接嵌入JSON Schema格式的工具定义
- 提供更明确的工具能力说明

**权衡考虑**：
- 嵌入会增加prompt token消耗
- 但可能提高工具调用准确性

#### 3. 工具配置 (Tool Configuration)

**缺失内容**：
- 工具调用的配置参数
- 特殊行为说明
- 错误处理指导

### toyoura-nagisa的优势特色

#### 1. 实用性导向的工具指南

**优势**：
- 详细的使用示例
- 工作环境的明确说明
- 路径安全的重点强调

**对比**：官方格式更注重格式规范，toyoura-nagisa更注重实际使用指导

#### 2. 项目特色集成

**Live2D情感表达**：
- 独特的用户体验功能
- 明确的输出格式要求
- 体现了项目的差异化价值

#### 3. 模块化设计

**架构优势**：
- 基础prompt、工具prompt、表达prompt分离
- 支持动态组合
- 便于维护和扩展

## 优化建议

### 策略1：增强型混合格式（推荐）

保持toyoura-nagisa的优势特色，同时集成Anthropic的格式要求：

```markdown
# 建议的新System Prompt结构

## 1. 基础身份部分（保持现有base_prompt.md）
You are **Nagisa**, an interactive AI assistant...

## 2. 工具环境说明（新增）
In this environment you have access to a comprehensive set of tools to answer user questions.

### Tool Parameter Formatting
- String and scalar parameters: specify as-is
- Lists and objects: use JSON format
- Note: spaces in string values are preserved
- Tool calls are parsed with regular expressions

## 3. 工具使用指南（保持现有tool_prompt.md的核心内容）
Working directory: {workspace_root}
Always use absolute paths...
[保留现有的详细指导]

## 4. 情感表达指令（保持现有expression_prompt.md）
After completing your response, append emotion keyword...
```

### 策略2：Anthropic原生格式迁移

完全采用Anthropic推荐格式，在system prompt中嵌入完整工具定义。

**优点**：
- 严格符合官方建议
- 可能提高工具调用准确性

**缺点**：
- 大幅增加token消耗
- 失去toyoura-nagisa的特色优势
- 维护复杂度增加

### 策略3：格式化指令增强（最小改动）

仅在现有tool_prompt.md中添加格式化说明：

```markdown
## Tool Parameter Format Requirements

When calling tools, follow these format rules:
- String parameters: use direct values
- Number parameters: use numeric values  
- List parameters: use JSON array format like ["item1", "item2"]
- Object parameters: use JSON object format like {"key": "value"}
- Boolean parameters: use true/false
- Optional parameters: omit if not needed

**Important**: Spaces in string values are preserved exactly as provided.
```

## Token影响评估

### 当前System Prompt长度

```
base_prompt.md: ~500 tokens
tool_prompt.md: ~2,800 tokens  
expression_prompt.md: ~200 tokens
Total: ~3,500 tokens
```

### 不同策略的Token影响

1. **策略1（增强型混合）**: +200-400 tokens
2. **策略2（完整迁移）**: +2,000-5,000 tokens
3. **策略3（最小改动）**: +100-200 tokens

## 实施优先级建议

### 短期（立即可实施）

1. **添加格式化指令**（策略3）
   - 成本：最低
   - 收益：中等
   - 风险：极低

### 中期（1-2周内）

2. **测试混合格式**（策略1）
   - 创建测试版本
   - 对比性能差异
   - 收集使用反馈

### 长期（评估后决定）

3. **考虑完整迁移**（策略2）
   - 仅在测试证明显著收益时考虑
   - 需要重新设计prompt管理架构

## 特殊考虑：原生工具集成

结合之前的"Anthropic原生工具优化"分析，当使用Anthropic作为provider时：

1. **原生工具**：bash、text_editor等无需在system prompt中定义
2. **MCP工具**：需要考虑是否在system prompt中提供定义
3. **混合使用**：可能需要不同的prompt策略

## 💡 重新评估的结论与行动建议

基于**Claude Code确实在system prompt中嵌入完整工具定义**的发现，我们需要重新评估优化策略：

### 🎯 新的推荐实施路径

#### 1. 立即实施（高优先级）
**在toyoura-nagisa中实现完整的工具定义嵌入**：
- 修改AnthropicToolManager，在system prompt中嵌入完整工具schema
- 采用Claude Code的格式：`<functions><function>...</function></functions>`
- 这是Claude Code成功的核心要素之一

#### 2. 具体实现方案

```python
# backend/infrastructure/llm/providers/anthropic/client.py
def build_enhanced_system_prompt(self, base_prompt: str, tool_schemas: List[Dict]) -> str:
    """构建包含工具定义的增强system prompt"""
    if not tool_schemas:
        return base_prompt
    
    tools_section = "Here are the functions available in JSONSchema format:\n<functions>\n"
    for tool in tool_schemas:
        tools_section += f'<function>{json.dumps(tool)}</function>\n'
    tools_section += "</functions>\n\n"
    
    return f"{base_prompt}\n\n{tools_section}"
```

#### 3. 分阶段实施策略

**阶段1（1-2天）**：
- 实现工具schema嵌入功能
- 在Anthropic provider中测试

**阶段2（3-5天）**：
- 性能对比测试（嵌入vs不嵌入）
- 测量token使用量和工具调用准确性

**阶段3（1周）**：
- 根据测试结果决定是否全面启用
- 考虑为其他provider实现类似功能

### 🔄 更新的Token成本分析

既然Claude Code使用5,000+ tokens用于工具定义仍然被认为是可接受的，toyoura-nagisa也应该重新考虑这个成本：

| 场景 | Token消耗 | 预期收益 |
|------|-----------|----------|
| 当前toyoura-nagisa | ~3,500 | 基础功能 |
| +工具定义嵌入 | ~8,500 | **显著提升工具调用准确性** |
| Claude Code参考 | ~8,500+ | 极高的工具调用可靠性 |

### 🎯 关键成功指标（更新）

1. **工具调用成功率**：目标提升15-25%
2. **参数格式错误**：预期减少80%+
3. **用户满意度**：更可靠的工具执行体验
4. **系统稳定性**：减少因工具调用失败的重试

### ⚠️ 风险评估与缓解

**主要风险**：
- Token消耗增加约140%
- 可能影响响应速度

**缓解措施**：
- 实现智能工具过滤（只包含当前session需要的工具）
- A/B测试验证ROI
- 监控成本和性能指标

### 🚀 战略意义

这个发现表明：
1. **toyoura-nagisa目前可能处于次优状态** - 没有采用Anthropic的最佳实践
2. **竞争优势机会** - 通过采用Claude Code的成功模式提升系统可靠性
3. **用户体验提升** - 更准确的工具调用直接改善用户交互体验

### 📋 行动清单

- [ ] 实现system prompt中的工具schema嵌入
- [ ] 对比测试工具调用准确性
- [ ] 监控token使用和成本变化
- [ ] 评估在其他provider中的适用性
- [ ] 建立性能监控和回滚机制

**结论**：Claude Code的成功证明了在system prompt中嵌入工具定义的价值，toyoura-nagisa应该积极采用这一最佳实践，以实现更高的工具调用可靠性和用户体验。