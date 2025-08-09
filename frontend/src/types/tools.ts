export interface ToolState {
  type: 'NAGISA_IS_USING_TOOL' | 'NAGISA_TOOL_USE_CONCLUDED'
  tool_name?: string
  parameters?: Record<string, any>
  action_text?: string
}

export interface ToolsContextType {
  // 工具状态
  toolState: ToolState | null
  toolsEnabled: boolean
  ttsEnabled: boolean

  // 工具操作
  updateToolsEnabled: (enabled: boolean) => Promise<void>
  updateTtsEnabled: (enabled: boolean) => Promise<void>
  setToolState: (state: ToolState | null) => void
}