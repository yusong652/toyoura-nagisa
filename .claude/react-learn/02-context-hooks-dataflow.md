# Context 深入与 Hooks 数据流

**日期**: 2025-12-06
**背景**: 继续通过 CLI 项目学习 React Context 和 Hooks

## 学习内容

### 1. Context 深入理解

#### createContext 语法解析

```typescript
const StreamingContext = createContext<StreamingState | undefined>(undefined);
//                                     ↑ 泛型：值的类型              ↑ 默认值
```

- **泛型参数**：定义 Context 存储的值的类型
- **默认值**：没有 Provider 包裹时返回的值
- `undefined` 作为默认值可以检测是否在 Provider 内使用

#### Context 对象 vs Context 值

```typescript
// StreamingContext 是对象，包含 Provider、Consumer
StreamingContext = { Provider, Consumer, ... }

// useContext 获取 Provider 提供的值
const value = useContext(StreamingContext);  // → StreamingState.Responding
```

**关键区别**：

- 直接访问 `StreamingContext` → 获取 Context 对象（没有 value 属性）
- 使用 `useContext(StreamingContext)` → 获取 Provider 的值 + 订阅变化

#### Provider 嵌套与作用域

```typescript
<StreamingContext.Provider value={StreamingState.Idle}>
  <ComponentA />  {/* 获取 Idle */}

  <StreamingContext.Provider value={StreamingState.Responding}>
    <ComponentB />  {/* 获取 Responding（最近的 Provider） */}
  </StreamingContext.Provider>
</StreamingContext.Provider>
```

- Provider 可以嵌套，内层覆盖外层
- `useContext` 返回**最近的** Provider 的值
- 类似 JavaScript 变量作用域链

#### Context 按引用匹配

```typescript
// 多个文件 import 同一个 Context → 同一个对象（JavaScript 模块只执行一次）
import { StreamingContext } from './StreamingContext';  // 文件A
import { StreamingContext } from './StreamingContext';  // 文件B
// 都指向同一个内存地址

// 不同的 createContext 调用 → 不同对象（即使类型相同）
const ContextA = createContext('light');
const ContextB = createContext('light');
// ContextA !== ContextB
```

#### 自定义 Hook 封装 Context

```typescript
// 目的：保证返回值不是 undefined + 类型收窄
export const useStreamingContext = (): StreamingState => {
  const context = useContext(StreamingContext);

  if (context === undefined) {
    throw new Error('必须在 Provider 内使用！');
  }

  return context;  // 类型收窄为 StreamingState（不含 undefined）
};
```

### 2. useCallback Hook

#### 作用：记忆化函数

```typescript
const clearError = useCallback(() => {
  setError(null);
}, []);  // 依赖数组
```

**问题**：组件每次渲染，函数都会重新创建（新的内存地址）

**解决**：`useCallback` 缓存函数引用

#### 依赖数组

| 依赖 | 行为 |
|------|------|
| `[]` 空数组 | 函数只创建一次，永不重新创建 |
| `[a, b]` | a 或 b 变化时重新创建 |
| 不传 | 每次都重新创建（失去意义） |

#### 为什么需要 useCallback？

```typescript
// useChatStream 返回 clearError
return { clearError, ... };

// AppContainer 使用
const appActions = useMemo(() => ({
  clearError,  // 如果 clearError 每次都是新函数
  ...          // useMemo 依赖变化 → appActions 重建 → 下游组件重渲染
}), [clearError, ...]);
```

稳定的函数引用 → 稳定的依赖 → 避免不必要重渲染

### 3. 组件渲染时机

#### 触发重新渲染的情况

| 触发原因 | 例子 |
|----------|------|
| 本组件 state 变化 | `setState(newValue)` |
| 父组件重新渲染 | 父组件 state 变了 |
| Context 变化 | Provider 的 value 变了 |

#### 重要理解

```text
用户点击 → 执行 onClick → setState() → 状态变化 → 触发渲染
          ↑                            ↑
        不触发渲染                   这才触发渲染！
```

**点击本身不触发渲染，是 `setState` 触发的！**

### 4. TypeScript 解构重命名

```typescript
// 解构 + 重命名语法
const { streamingState: streamingStateEnum } = useChatStream();
//      ↑ 原属性名       ↑ 新变量名

// 等价于
const streamingStateEnum = useChatStream().streamingState;
```

**注意区分**：

- `{ a: b } = obj` → 解构重命名（b 是新变量名）
- `a: Type = value` → 类型注解（Type 是类型）

### 5. 泛型类型推断

```typescript
// 可以省略泛型（TypeScript 从初始值推断）
const [isStreaming, setIsStreaming] = useState(false);  // → boolean

// 需要显式写泛型
const [error, setError] = useState<string | null>(null);  // null 不能推断完整类型
const [items, setItems] = useState<Item[]>([]);           // 空数组推断为 never[]
```

### 6. 完整数据流理解

```text
useChatStream（状态源头）
    ↓ useState 管理 streamingState
AppContainer
    ↓ 组装成 appState 对象
    ↓ useMemo 缓存
AppStateContext.Provider
    ↓ 提供 value={appState}
App.tsx
    ↓ useAppState() 获取
    ↓ 提取 appState.streamingState.state
StreamingContext.Provider
    ↓ 提供 value={枚举值}
子组件
    ↓ useStreamingContext() 获取
    使用枚举值
```

## 关键文件

| 文件 | 作用 |
|------|------|
| `StreamingContext.tsx` | 定义 Context 和 useStreamingContext |
| `AppStateContext.tsx` | 全局状态 Context |
| `AppContainer.tsx` | 组装状态，提供 Provider |
| `App.tsx` | 转发 StreamingContext |
| `useChatStream.ts` | 状态源头，管理流式状态 |

## 待学习

- [ ] useEffect - 副作用处理
- [ ] useMemo - 计算结果缓存
- [ ] useRef - 持久化引用
- [ ] 流式渲染的具体实现
- [ ] 工具消息组件（ToolCallMessage）
