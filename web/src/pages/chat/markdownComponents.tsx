import { type Components } from 'react-markdown'
import styles from '../../components/chat.module.css'
import { CodeBlockCard } from './CodeBlockCard'

/** Customiza elementos Markdown que precisam de comportamento visual ou seguro. */
export const markdownComponents: Components = {
  a({ href, children, ...props }) {
    return (
      <a href={href} target="_blank" rel="noreferrer noopener" {...props}>
        {children}
      </a>
    )
  },
  table({ children, ...props }) {
    return (
      <div className={styles.markdownTableScroller}>
        <table {...props}>{children}</table>
      </div>
    )
  },
  pre({ children }) {
    return <>{children}</>
  },
  code({ className, children, ...props }) {
    const rawCode = String(children ?? '').replace(/\n$/, '')
    const match = /language-(\w+)/.exec(className ?? '')
    const language = match?.[1]
    const hasBlockBreak = rawCode.includes('\n')

    if (!hasBlockBreak && !language) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      )
    }

    return (
      <CodeBlockCard
        code={rawCode}
        language={language ?? 'text'}
      />
    )
  },
}
