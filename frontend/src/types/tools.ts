export interface ToolState {
  type: 'NAGISA_IS_USING_TOOL' | 'NAGISA_TOOL_USE_CONCLUDED'
  tool_name?: string
  parameters?: Record<string, any>
  action_text?: string
}