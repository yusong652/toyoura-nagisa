# TypeScript Development Guide

**For frontend development in the toyoura-nagisa project**

When creating or refactoring TypeScript code in the frontend, provide comprehensive explanations to help the user systematically learn TypeScript principles through hands-on project work.

## Core Learning Objectives

**IMPORTANT**: Every TypeScript file creation/modification should be a learning opportunity. Always provide detailed explanations covering:

1. **Type System Mastery**: Deep understanding of TypeScript's type system
2. **React Integration**: Mastery of React-TypeScript patterns
3. **Component Architecture**: Advanced component design principles
4. **Hook Patterns**: Custom hooks with proper typing
5. **Error Prevention**: Type safety best practices

## Detailed Explanation Requirements

### 1. Type System Concepts
When implementing any type construct, explain in detail:

#### Interfaces vs Types
```typescript
// Interface (extensible, declaration merging)
interface UserProps {
  name: string
  age: number
}

// Type alias (more flexible, union types)
type Status = 'loading' | 'success' | 'error'
```
**Explain**: "Interface is preferred for object shapes that might be extended, while type aliases work better for unions and computed types."

#### Generic Types
```typescript
function useApi<T>(endpoint: string): ApiResponse<T>
```
**Explain**: "Generic `<T>` allows this hook to work with any data type while preserving type safety. The actual type is determined at call-site."

#### Union and Intersection Types
```typescript
type MessageSender = 'user' | 'bot'  // Union
type EnhancedMessage = Message & { metadata: any }  // Intersection
```
**Explain**: "Union types represent 'OR' relationships, intersection types represent 'AND' relationships."

#### Conditional Types
```typescript
type ApiResponse<T> = T extends string ? { text: T } : { data: T }
```
**Explain**: "Conditional types enable type logic - different return types based on input type conditions."

### 2. React-TypeScript Patterns
For every React component, explain:

#### Component Typing
```typescript
// Functional Component with Props
const MessageItem: React.FC<MessageItemProps> = ({ message, onSelect }) => {
  // React.FC provides: children?, displayName, defaultProps
  // Automatically infers return type as JSX.Element | null
}

// Alternative (more explicit)
const MessageItem = ({ message, onSelect }: MessageItemProps): JSX.Element => {
  // More explicit about return type, no automatic children prop
}
```
**Explain**: "React.FC is convenient but adds implicit children prop. Explicit typing gives more control."

#### Props Interface Design
```typescript
interface MessageItemProps {
  message: Message                          // Required object
  onSelect: (id: string | null) => void     // Function signature
  selectedId?: string | null               // Optional prop
  children?: React.ReactNode               // Explicit children when needed
}
```
**Explain**: "Props interface defines the contract. Optional props use `?`, functions include full signature for type safety."

#### Event Handler Typing
```typescript
const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
  // e has all button-specific mouse event properties
  e.preventDefault()  // TypeScript knows this method exists
}

const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const value = e.target.value  // TypeScript knows target is HTMLInputElement
}
```
**Explain**: "Generic event types provide element-specific properties and methods."

### 3. Hook Patterns and Custom Hooks
For every hook implementation, explain:

#### Custom Hook Typing
```typescript
// Return type interface for clarity
interface UseMessageStateReturn {
  displayText: string
  isLoading: boolean
  error: string | null
}

const useMessageState = (messageId: string): UseMessageStateReturn => {
  const [displayText, setDisplayText] = useState<string>('')
  // useState<string> is explicit - TypeScript could infer from initial value

  return {
    displayText,
    isLoading,
    error
  }
}
```
**Explain**: "Custom hooks should have clear return type interfaces. State typing can be explicit or inferred."

#### Hook Dependencies and Callbacks
```typescript
const useMessageEvents = (
  message: Message,
  onSelect: (id: string | null) => void
): MessageEventHandlers => {

  // useCallback with dependency typing
  const handleClick = useCallback((e: React.MouseEvent) => {
    onSelect(message.id)
  }, [message.id, onSelect])  // Dependencies must match types used inside

  return { handleClick }
}
```
**Explain**: "useCallback dependencies array must include all values used inside the callback. TypeScript helps catch missing dependencies."

### 4. Component Architecture Patterns
For component design, explain:

#### Composition Patterns
```typescript
// Base props that can be extended
interface BaseComponentProps {
  className?: string
  children?: React.ReactNode
}

// Extended props using intersection
interface MessageTextProps extends BaseComponentProps {
  content: string
  variant?: 'default' | 'streaming'
}
```
**Explain**: "Extending interfaces creates component hierarchies. Base props provide common functionality."

#### Render Props Pattern
```typescript
interface RenderProps<T> {
  data: T
  loading: boolean
  error: string | null
}

interface DataProviderProps<T> {
  render: (props: RenderProps<T>) => JSX.Element
  endpoint: string
}
```
**Explain**: "Render props pattern uses generics to provide type-safe data passing to render functions."

#### Discriminated Unions for Variants
```typescript
type MessageVariant =
  | { type: 'text'; content: string }
  | { type: 'file'; files: File[] }
  | { type: 'tool'; toolState: ToolState }

const MessageRenderer = ({ variant }: { variant: MessageVariant }) => {
  switch (variant.type) {
    case 'text':
      return <TextMessage content={variant.content} />  // TypeScript knows content exists
    case 'file':
      return <FileMessage files={variant.files} />      // TypeScript knows files exists
    case 'tool':
      return <ToolMessage toolState={variant.toolState} /> // TypeScript knows toolState exists
  }
}
```
**Explain**: "Discriminated unions enable type-safe variant handling. TypeScript narrows types in each case."

### 5. Advanced Type Techniques
Explain advanced patterns when encountered:

#### Mapped Types
```typescript
// Make all properties optional
type Partial<T> = {
  [P in keyof T]?: T[P]
}

// Make all properties required
type Required<T> = {
  [P in keyof T]-?: T[P]
}
```
**Explain**: "Mapped types transform existing types. `keyof T` gets all property names, `T[P]` gets property type."

#### Template Literal Types
```typescript
type EventName = 'click' | 'hover' | 'focus'
type HandlerName = `on${Capitalize<EventName>}`  // 'onClick' | 'onHover' | 'onFocus'
```
**Explain**: "Template literal types enable string manipulation at the type level."

#### Conditional Type Utilities
```typescript
type NonNullable<T> = T extends null | undefined ? never : T
type ReturnType<T> = T extends (...args: any[]) => infer R ? R : any
```
**Explain**: "Utility types use conditional types and `infer` to extract or transform types."

## Practical Learning Examples

When creating files, use these teaching moments:

### Component Example with Full Explanation
```typescript
import React, { useState, useCallback } from 'react'

// Props interface - define the contract
interface MessageTextProps {
  content: string                    // Required: message text content
  className?: string                // Optional: CSS class for styling
  onContentChange?: (text: string) => void  // Optional: callback when content changes
}

/**
 * Message text display component with TypeScript best practices.
 *
 * This component demonstrates:
 * - Interface-based props typing
 * - Optional vs required props
 * - Event handler typing
 * - State management with explicit types
 * - Callback memoization with useCallback
 */
const MessageText: React.FC<MessageTextProps> = ({
  content,
  className = 'message-text',  // Default value for optional prop
  onContentChange
}) => {
  // State with explicit typing (could be inferred from initial value)
  const [isEditing, setIsEditing] = useState<boolean>(false)

  // Callback with proper dependencies for performance
  const handleEdit = useCallback(() => {
    setIsEditing(true)
    onContentChange?.(content)  // Optional chaining for optional callback
  }, [content, onContentChange])  // Dependencies ensure callback updates when props change

  return (
    <div className={className} onClick={handleEdit}>
      {content}
    </div>
  )
}

export default MessageText
```

**Learning Points Explained:**
- Interface design for component contracts
- Optional props with default values
- State typing strategies (explicit vs inferred)
- Callback memoization and dependency management
- Optional chaining for optional props

### Hook Example with Full Explanation
```typescript
import { useState, useEffect, useCallback } from 'react'

// Clear return type interface
interface UseApiReturn<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Generic API hook demonstrating TypeScript patterns.
 *
 * Generic type T allows this hook to work with any data type
 * while maintaining complete type safety throughout.
 */
function useApi<T>(endpoint: string): UseApiReturn<T> {
  // State with explicit generic typing
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Memoized fetch function
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(endpoint)
      const result: T = await response.json()  // Type assertion based on generic
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }, [endpoint])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    data,
    loading,
    error,
    refetch: fetchData
  }
}
```

**Learning Points Explained:**
- Generic functions enable reusable, type-safe code
- State typing with union types (T | null)
- Error handling with type guards (instanceof Error)
- Effect dependencies and callback memoization
- Return type interfaces for clarity

## Error Prevention and Best Practices

Always explain these critical concepts:

1. **Strict Type Checking**: Explain why strict mode helps catch errors
2. **Null Safety**: Show proper null/undefined handling
3. **Type Guards**: Demonstrate runtime type checking
4. **Generic Constraints**: Use bounded generics when appropriate
5. **Import/Export Patterns**: Proper module typing

## Assessment Questions

After explaining concepts, ask learning questions:
- "Why did we choose an interface over a type alias here?"
- "What would happen if we removed this generic constraint?"
- "How does TypeScript help prevent this runtime error?"
- "What are the trade-offs between these two typing approaches?"

---

This approach ensures every TypeScript interaction becomes a structured learning opportunity, building expertise through practical application in the toyoura-nagisa project.
