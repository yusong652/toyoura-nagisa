import React, { useState, useEffect, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { createHighlighter, Highlighter } from 'shiki'
import 'katex/dist/katex.min.css'
import '../../../styles/markdown.css'

interface CodeBlockProps {
  inline?: boolean
  className?: string
  children: React.ReactNode
}

// Singleton highlighter instance
let sharedHighlighter: Highlighter | null = null

const CodeBlock: React.FC<CodeBlockProps> = ({ inline, className, children }) => {
  const [highlightedHtml, setHighlightedHtml] = useState<string | null>(null)
  const [isCopied, setIsCopied] = useState(false)
  const language = className?.replace(/language-/, '') || 'text'
  const content = String(children).replace(/\n$/, '')

  useEffect(() => {
    if (inline) return

    const highlight = async () => {
      if (!sharedHighlighter) {
        sharedHighlighter = await createHighlighter({
          themes: ['min-dark', 'min-light'],
          langs: ['typescript', 'javascript', 'python', 'bash', 'json', 'markdown', 'html', 'css', 'cpp']
        })
      }

      try {
        // Ensure language is loaded
        if (!sharedHighlighter.getLoadedLanguages().includes(language)) {
          await sharedHighlighter.loadLanguage(language as any).catch(() => {
             // Fallback to text if language not found
          })
        }

        const html = sharedHighlighter.codeToHtml(content, {
          lang: sharedHighlighter.getLoadedLanguages().includes(language) ? language : 'text',
          theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'min-dark' : 'min-light'
        })
        setHighlightedHtml(html)
      } catch (err) {
        console.error('Shiki highlighting error:', err)
      }
    }

    highlight()
  }, [content, language, inline])

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setIsCopied(true)
    setTimeout(() => setIsCopied(false), 2000)
  }

  if (inline) {
    return <code className={className}>{children}</code>
  }

  return (
    <div className="code-block-wrapper" style={{ position: 'relative', marginBottom: '16px' }}>
      <div className="code-block-header" style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '4px 12px',
        backgroundColor: '#2d2d2d',
        borderTopLeftRadius: '8px',
        borderTopRightRadius: '8px',
        fontSize: '11px',
        color: '#aaa',
        fontFamily: 'monospace'
      }}>
        <span>{language}</span>
        <button 
          onClick={handleCopy}
          className="copy-button"
          style={{
            padding: '2px 8px',
            borderRadius: '4px',
            backgroundColor: 'transparent',
            color: '#aaa',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
        >
          {isCopied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      {highlightedHtml ? (
        <div dangerouslySetInnerHTML={{ __html: highlightedHtml }} />
      ) : (
        <pre><code className={className}>{children}</code></pre>
      )}
      <style>{`
        .code-block-header .copy-button:hover { 
          color: #fff; 
          background-color: rgba(255, 255, 255, 0.1); 
        }
        .code-block-wrapper .shiki { 
          padding: 16px; 
          border-bottom-left-radius: 8px; 
          border-bottom-right-radius: 8px; 
          margin: 0; 
          font-size: 13px;
          line-height: 1.5;
        }
      `}</style>
    </div>
  )
}

interface MarkdownContentProps {
  content: string
  className?: string
}

const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, className = '' }) => {
  const components = useMemo(() => ({
    code: (props: any) => <CodeBlock {...props} />,
    a: ({ node, ...props }: any) => {
      const isExternal = props.href?.startsWith('http');
      return (
        <a 
          {...props} 
          target={isExternal ? "_blank" : undefined} 
          rel={isExternal ? "noopener noreferrer" : undefined}
        />
      );
    }
  }), [])

  return (
    <div className={`markdown-body ${className}`} data-component="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components as any}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default MarkdownContent
