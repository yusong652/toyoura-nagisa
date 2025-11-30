# Gemini 完整响应获取与上下文组装实验结果

**测试日期**: 2025-10-29
**测试模型**: `gemini-2.5-flash-preview-09-2025` (也兼容 `gemini-2.0-flash-thinking-exp-01-21`)
**测试脚本**: `backend/tests/test_gemini_complete_response.py`

---

## 📌 模型支持说明

以下 Gemini 模型均支持 thinking 模式：

| 模型名称 | 测试状态 | Thinking 支持 | 备注 |
|---------|---------|--------------|------|
| `gemini-2.5-flash-preview-09-2025` | ✅ 已测试 | ✅ 支持 | 推荐使用，最新版本 |
| `gemini-2.0-flash-thinking-exp-01-21` | ✅ 已测试 | ✅ 支持 | 实验性模型 |
| `gemini-2.5-pro` | ⚠️ 未测试 | ❓ 待验证 | - |
| `gemini-2.5-flash` | ⚠️ 未测试 | ❓ 待验证 | - |

**重要提示**:
- 使用 thinking 模式需要在 config 中启用 `thinking_config`
- 不同模型的 thinking chunk 数量和大小可能略有差异
- 所有模型的响应结构和上下文格式保持一致

---

## 🎯 核心发现

### 1. 流式响应的完整内容获取

#### ✅ 推荐方法：手动组装

通过迭代流式 chunks 并手动拼接所有 parts：

```python
# 初始化收集器
thinking_parts = []
text_parts = []

# 迭代流式响应
async for chunk in await stream_generator:
    # 检查是否有 parts（最后的 finish chunk 可能没有）
    if not chunk.candidates[0].content.parts:
        continue

    for part in chunk.candidates[0].content.parts:
        if part.thought:
            thinking_parts.append(part.text)
        else:
            text_parts.append(part.text)

# 组装完整内容
full_thinking = "".join(thinking_parts)
full_text = "".join(text_parts)
```

#### ❌ `await stream` 不可行

测试发现 `await stream_generator` 返回的仍然是一个异步生成器对象，不是完整响应：

```python
complete_response = await stream_generator2
# 结果：
# Response type: <class 'async_generator'>
# Has .text attribute: False
# Has .candidates attribute: False
```

**结论**: Gemini SDK 的流式 API **不支持** 通过 await 获取完整响应。必须手动迭代并组装。

---

### 2. 多轮对话上下文组装

#### 上下文格式

Gemini 要求的对话历史格式：

```python
conversation_history = [
    {
        "role": "user",
        "parts": [{"text": "What is 5 + 3?"}]
    },
    {
        "role": "model",
        "parts": [{"text": "5 + 3 = 8"}]
    },
    {
        "role": "user",
        "parts": [{"text": "Now multiply that result by 2"}]
    }
]
```

#### 关键要点

1. **角色命名**:
   - 用户消息: `"role": "user"`
   - 模型消息: `"role": "model"` (⚠️ 不是 "assistant")

2. **Parts 结构**:
   - 每条消息的 `parts` 是一个列表
   - 每个 part 是一个字典: `{"text": "content"}`

3. **仅包含文本内容**:
   - 上下文中**只包含普通文本内容**（text parts）
   - **不要包含** thinking 内容
   - Thinking 是模型内部推理过程，不应作为对话历史

4. **使用方法**:
```python
# 构建包含历史的请求
contents = conversation_history + [
    {"role": "user", "parts": [{"text": new_user_message}]}
]

stream = client.aio.models.generate_content_stream(
    model='gemini-2.0-flash-thinking-exp-01-21',
    contents=contents,
    config=config
)
```

---

### 3. Chunk 结构细节

#### Final Chunk

最后一个 chunk 可能不包含 parts，只包含 `finish_reason`：

```python
if not chunk.candidates[0].content.parts:
    # 这是 final chunk
    finish_reason = chunk.candidates[0].finish_reason
    continue
```

#### Parts 检查

**必须检查** `parts` 是否存在，避免 `NoneType` 错误：

```python
# ❌ 错误做法
for part in chunk.candidates[0].content.parts:  # 可能 TypeError
    ...

# ✅ 正确做法
if chunk.candidates[0].content.parts:
    for part in chunk.candidates[0].content.parts:
        ...
```

---

## 📊 测试结果示例

### Test 1: 手动组装完整响应

**Prompt**: "Solve this step by step: If a train travels 120 km in 2 hours, what is its average speed?"

#### gemini-2.5-flash-preview-09-2025 结果

**统计数据**:
- 总 chunks: 6 个
- Thinking chunks: 2 个 (685 字符)
- Text chunks: 4 个 (550 字符)

**完整文本内容**:
```
This problem requires calculating the average speed using the distance traveled and the time taken.

### 1. Identify the Formula

The formula for average speed is:
$$\text{Average Speed} = \frac{\text{Distance Traveled}}{\text{Time Taken}}$$

### 2. Identify the Given Values

*   **Distance ($D$)**: 120 km
*   **Time ($T$)**: 2 hours

### 3. Substitute the Values and Calculate

$$\text{Average Speed} = \frac{120 \text{ km}}{2 \text{ hours}}$$

$$\text{Average Speed} = 60 \text{ km/h}$$

### Answer

The average speed of the train is **60 km/h**.
```

#### gemini-2.0-flash-thinking-exp-01-21 结果

**统计数据**:
- 总 chunks: 7 个
- Thinking chunks: 3 个 (1097 字符)
- Text chunks: 4 个 (620 字符)

**完整文本内容**:
```
Let's solve this step by step:

**Step 1: Understand the concept of average speed.**
Average speed is calculated by dividing the total distance traveled by the total time taken.
The formula is:
Average Speed = Total Distance / Total Time

**Step 2: Identify the given values.**
*   Total Distance = 120 km
*   Total Time = 2 hours

**Step 3: Apply the formula.**
Substitute the given values into the formula:
Average Speed = 120 km / 2 hours

**Step 4: Perform the calculation.**
Divide the distance by the time:
Average Speed = 60 km/h

**Step 5: State the final answer.**
The average speed of the train is **60 km/h**.
```

### Test 2: Await Stream 测试

**结果**:
```
✓ 'await stream' succeeded!

Response type: <class 'async_generator'>
Has .text attribute: False
Has .candidates attribute: False
```

**结论**: `await stream` 不返回完整响应对象，仍然是异步生成器。

### Test 3: 多轮对话

**对话序列**:

1. **User**: "What is 5 + 3?"
   **Assistant**: "5 + 3 = 8"

2. **User**: "Now multiply that result by 2"
   **Assistant**: "The previous result was 8.\n\n8 * 2 = 16"

**上下文历史** (4 条消息):
```python
[
    {"role": "user", "parts": [{"text": "What is 5 + 3?"}]},
    {"role": "model", "parts": [{"text": "5 + 3 = 8"}]},
    {"role": "user", "parts": [{"text": "Now multiply that result by 2"}]},
    {"role": "model", "parts": [{"text": "The previous result was 8.\n\n8 * 2 = 16"}]}
]
```

✅ **验证成功**: 模型正确引用了之前的计算结果 (8)。

---

## 🔧 toyoura-nagisa 实现建议

### 1. 完整响应组装函数

```python
async def get_complete_gemini_response(
    client: genai.Client,
    prompt: str,
    conversation_history: List[Dict] = None,
    config: types.GenerateContentConfig = None
) -> Dict[str, Any]:
    """
    获取 Gemini 流式响应的完整内容

    Returns:
        {
            "thinking": str,  # 完整的 thinking 内容
            "text": str,      # 完整的文本内容
            "chunks": List[Dict]  # 所有 chunks 的详细信息
        }
    """
    # 构建请求内容
    if conversation_history:
        contents = conversation_history + [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    else:
        contents = prompt

    # 创建流式生成器
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=contents,
        config=config
    )

    # 收集所有内容
    thinking_parts = []
    text_parts = []
    chunks_info = []

    async for chunk in await stream_generator:
        # 跳过空 parts 的 chunk（通常是 final chunk）
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            chunk_info = {
                "is_thinking": bool(part.thought),
                "text": part.text,
                "length": len(part.text)
            }
            chunks_info.append(chunk_info)

            if part.thought:
                thinking_parts.append(part.text)
            else:
                text_parts.append(part.text)

    return {
        "thinking": "".join(thinking_parts),
        "text": "".join(text_parts),
        "chunks": chunks_info
    }
```

### 2. 上下文管理类

```python
class ConversationContext:
    """管理 Gemini 多轮对话上下文"""

    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def add_user_message(self, text: str):
        """添加用户消息"""
        self.history.append({
            "role": "user",
            "parts": [{"text": text}]
        })

    def add_assistant_message(self, text: str):
        """添加助手消息（仅文本，不含 thinking）"""
        self.history.append({
            "role": "model",
            "parts": [{"text": text}]
        })

    def get_history(self) -> List[Dict[str, Any]]:
        """获取完整对话历史"""
        return self.history.copy()

    def clear(self):
        """清空历史"""
        self.history.clear()
```

### 3. 流式 WebSocket 发送

```python
async def stream_gemini_to_websocket(
    session_id: str,
    prompt: str,
    conversation_history: List[Dict] = None
):
    """
    实时流式发送 Gemini 响应到 WebSocket
    同时组装完整内容用于上下文
    """
    # 初始化客户端和配置
    client = get_gemini_client()
    config = get_gemini_thinking_config()

    # 构建请求
    if conversation_history:
        contents = conversation_history + [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    else:
        contents = prompt

    # 创建流
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=contents,
        config=config
    )

    # 收集完整内容（用于保存到上下文）
    full_text_parts = []

    # 实时发送 chunks
    chunk_index = 0
    async for chunk in await stream_generator:
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.thought:
                # 发送 thinking chunk
                await send_websocket_message(
                    session_id=session_id,
                    message_type="THINKING_CHUNK",
                    data={
                        "index": chunk_index,
                        "text": part.text
                    }
                )
            else:
                # 发送 text chunk
                await send_websocket_message(
                    session_id=session_id,
                    message_type="TEXT_CHUNK",
                    data={
                        "index": chunk_index,
                        "text": part.text
                    }
                )
                # 收集用于上下文
                full_text_parts.append(part.text)

            chunk_index += 1

    # 组装完整文本（用于保存到对话历史）
    full_text = "".join(full_text_parts)

    # 发送完成信号
    await send_websocket_message(
        session_id=session_id,
        message_type="STREAM_COMPLETE",
        data={"full_text": full_text}
    )

    return full_text
```

---

## ⚠️ 关键注意事项

1. **必须手动组装**: Gemini SDK 不支持 `await stream` 获取完整响应
2. **检查 parts**: 总是检查 `chunk.candidates[0].content.parts` 是否存在
3. **角色名称**: 使用 `"model"` 而不是 `"assistant"`
4. **仅保存文本**: 上下文中只保存 text parts，不保存 thinking
5. **Parts 格式**: 使用 `[{"text": "content"}]` 格式

---

## 🔄 与其他 Provider 的对比

| Provider | 获取完整响应方式 | 上下文格式 |
|----------|-----------------|-----------|
| **Gemini** | 手动迭代 + 拼接 | `{"role": "model", "parts": [{"text": "..."}]}` |
| **Anthropic** | ❓ 待测试 | ❓ 待测试 |
| **OpenAI** | ❓ 待测试 | ❓ 待测试 |

---

## 📝 下一步

1. ✅ Gemini 完整响应获取 - **完成**
2. ✅ Gemini 多轮对话上下文 - **完成**
3. ⏳ 测试 Anthropic Claude 的响应结构
4. ⏳ 测试 OpenAI 的响应结构
5. ⏳ 设计统一的流式处理和上下文管理接口

---

**文档版本**: v2.0
**最后更新**: 2025-10-29 (新增完整响应获取与上下文组装测试)
**测试脚本**: `backend/tests/test_gemini_complete_response.py`
**状态**: Gemini 分析完成，包含上下文组装
