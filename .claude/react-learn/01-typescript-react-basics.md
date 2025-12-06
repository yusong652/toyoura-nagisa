# TypeScript React 基础学习笔记

**日期**: 2025-11-25
**背景**: 通过 toyoura-nagisa CLI 项目学习 TypeScript 和 React 基础

## 学习内容总结

### 1. 类型系统

#### interface vs type

- **interface**: 定义对象结构，编译时验证，运行时消失
- **type**: 类型别名，适合联合类型、基础类型别名
- 两者都是**编译时约束**，帮助在写代码时发现类型错误

```typescript
// interface - 对象结构
interface AppState {
  isQuitting: boolean;
  error: string | null;
}

// type - 联合类型
type ConnectionStatus = 'connected' | 'connecting' | 'disconnected';
```

#### import type

- `import type { X }` 编译后完全删除
- 意图明确，避免循环依赖，打包更小

### 2. React 组件定义

#### 现代写法（推荐）

```typescript
// 不需要 React.FC，让 TypeScript 自动推断
export const App = () => {
  return <div>Hello</div>;
};
```

#### 旧写法（不推荐）

```typescript
// React.FC 已不推荐使用
export const App: React.FC = () => { ... };
```

### 3. Context 系统基础

#### createContext

```typescript
const MyContext = createContext<T>(defaultValue);
// <T> 指定类型，defaultValue 是后备值
```

#### Provider

- Provider 是 Context 对象的属性，用于向下传递数据
- value 属性的类型必须符合 createContext<T> 中的 T

```typescript
<MyContext.Provider value={data}>
  <ChildComponents />  // 所有子组件都能访问 data
</MyContext.Provider>
```

#### 数据流

- **单向数据流**：外层向内层传递
- 同层组件不能直接通信，必须通过共同父组件或 Context

### 4. useState Hook

#### 基本语法

```typescript
const [state, setState] = useState<T>(defaultValue);
//     ↑ 当前值  ↑ 修改函数        ↑ 类型可省略（自动推断）
```

#### 类型推断

- 能推断就不写：`useState(false)` → boolean
- 需要声明：`useState<string | null>(null)` → 默认值不能表达完整类型

#### 数组解构 vs 对象解构

```typescript
// 数组解构 - 按位置，名字自由
const [count, setCount] = useState(0);

// 对象解构 - 按属性名
const { error, isStreaming } = useChatStream();
```

### 5. 自定义 Hook

- `use` 前缀是约定，告诉 React 和开发者这是 Hook
- 自定义 Hook 封装可复用的状态逻辑
- 内部可以使用其他 Hook（useState, useEffect 等）

```typescript
export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  // ... 逻辑
  return { isStreaming, ... };
}
```

### 6. 泛型参数命名约定

| 字母 | 常见含义 |
|------|---------|
| T | Type（通用） |
| S | State |
| K | Key |
| V | Value |
| P | Props |

命名只是约定，功能完全相同。

## Gemini CLI Context 架构参考

Gemini CLI 使用多 Context 按职责分离：

```text
AppContext        - 应用级别
ConfigContext     - 配置
SettingsContext   - 用户设置
UIStateContext    - UI 状态（~90 字段）
UIActionsContext  - UI 操作方法
StreamingContext  - 流式状态
...
```

**设计原则**：

- 状态和操作分离
- 不同功能域分离
- 每个 Context 有明确职责

## 关键理解

1. **TypeScript 是编译时工具** - 类型在运行时不存在
2. **React 组件就是函数** - 返回 JSX 的函数
3. **useState 触发重渲染** - 状态变 → UI 自动变
4. **Context 解决 prop drilling** - 跨层级传递数据
5. **单向数据流** - 自上而下，通过回调向上传递
