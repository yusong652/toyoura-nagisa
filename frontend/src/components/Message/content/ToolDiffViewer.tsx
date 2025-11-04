import React, { useState, useMemo } from 'react'
import './ToolDiffViewer.css'

/**
 * Types for diff line representation.
 */
interface DiffLine {
  type: 'addition' | 'deletion' | 'context'
  lineNumber: number
  content: string
}

/**
 * Props for ToolDiffViewer component.
 */
interface ToolDiffViewerProps {
  toolName: 'edit' | 'write'
  filePath: string
  oldString?: string  // For edit tool - content to be replaced
  newString?: string  // For edit tool - replacement content
  content?: string    // For write tool - entire file content
}

/**
 * Git-style diff viewer for edit and write tools.
 *
 * Displays file changes with syntax highlighting similar to git diff:
 * - Red lines with '−' prefix for deletions (edit tool)
 * - Green lines with '+' prefix for additions (edit/write tool)
 * - Line numbers and file path header
 * - Collapsible with default expanded state for immediate visibility
 *
 * Args:
 *     toolName: Type of tool ('edit' or 'write')
 *     filePath: Path to the file being modified
 *     oldString: Original content being replaced (edit only)
 *     newString: New content replacing old (edit only)
 *     content: Full file content (write only)
 *
 * Returns:
 *     JSX element with git-style diff display
 */
const ToolDiffViewer: React.FC<ToolDiffViewerProps> = ({
  toolName,
  filePath,
  oldString,
  newString,
  content
}) => {
  const [isExpanded, setIsExpanded] = useState(true)

  /**
   * Type guard to ensure value is a string.
   */
  const isString = (value: any): value is string => {
    return typeof value === 'string'
  }

  /**
   * Generate diff lines from tool parameters.
   *
   * For 'write' tool: Shows entire content as additions (green)
   * For 'edit' tool: Shows old content as deletions (red) and new content as additions (green)
   */
  const diffLines = useMemo(() => {
    const lines: DiffLine[] = []

    if (toolName === 'write') {
      // For write tool, show entire content as additions
      if (isString(content)) {
        const contentLines = content.split('\n')
        contentLines.forEach((line, idx) => {
          lines.push({
            type: 'addition',
            lineNumber: idx + 1,
            content: line
          })
        })
      }
    } else if (toolName === 'edit') {
      // For edit tool, show deletions and additions
      // Deletions start from line 1
      if (isString(oldString)) {
        const oldLines = oldString.split('\n')
        oldLines.forEach((line, idx) => {
          lines.push({
            type: 'deletion',
            lineNumber: idx + 1,
            content: line
          })
        })
      }

      // Additions also start from line 1 (new content)
      if (isString(newString)) {
        const newLines = newString.split('\n')
        newLines.forEach((line, idx) => {
          lines.push({
            type: 'addition',
            lineNumber: idx + 1,
            content: line
          })
        })
      }
    }

    return lines
  }, [toolName, oldString, newString, content])

  // Calculate file statistics
  const stats = useMemo(() => {
    const additions = diffLines.filter(l => l.type === 'addition').length
    const deletions = diffLines.filter(l => l.type === 'deletion').length
    return { additions, deletions }
  }, [diffLines])

  // Extract filename from path with null safety
  const fileName = isString(filePath) ? (filePath.split(/[/\\]/).pop() || filePath) : 'Unknown file'
  const safeFilePath = isString(filePath) ? filePath : ''

  // Early return if no valid file path is provided
  if (!isString(filePath)) {
    return (
      <div className="tool-diff-viewer">
        <div className="diff-header">
          <div className="diff-file-info">
            <span className="diff-file-name" style={{ color: '#ef4444' }}>
              Invalid file path data
            </span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="tool-diff-viewer">
      <div className="diff-header">
        <div className="diff-file-info">
          <span className="diff-file-name">{fileName}</span>
          <span className="diff-file-path">{safeFilePath}</span>
        </div>

        <div className="diff-stats">
          {stats.additions > 0 && (
            <span className="stat-additions">+{stats.additions}</span>
          )}
          {stats.deletions > 0 && (
            <span className="stat-deletions">−{stats.deletions}</span>
          )}
          <button
            className="diff-toggle"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse diff' : 'Expand diff'}
          >
            {isExpanded ? '−' : '+'}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="diff-content">
          {diffLines.length === 0 ? (
            <div className="diff-empty">No changes to display</div>
          ) : (
            <div className="diff-lines">
              {diffLines.map((line, idx) => (
                <div
                  key={idx}
                  className={`diff-line diff-line-${line.type}`}
                >
                  <span className="line-number">{line.lineNumber}</span>
                  <span className="line-marker">
                    {line.type === 'addition' ? '+' : line.type === 'deletion' ? '−' : ' '}
                  </span>
                  <code className="line-content">{line.content || ' '}</code>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ToolDiffViewer
