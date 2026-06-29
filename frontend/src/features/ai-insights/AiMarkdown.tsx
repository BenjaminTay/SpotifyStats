import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'

interface AiMarkdownProps {
  children: string
}

const markdownComponents = {
  table: ({ children }: { children?: ReactNode }) => (
    <div className="my-3 max-w-full overflow-x-auto rounded-[8px] border border-border/60">
      <table className="w-full min-w-[520px] border-collapse text-left text-[12px] leading-relaxed">
        {children}
      </table>
    </div>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="border-b border-border/70 bg-muted/40 px-3 py-2 font-semibold text-foreground">
      {children}
    </th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="border-b border-border/40 px-3 py-2 align-top text-muted-foreground">
      {children}
    </td>
  ),
}

export function AiMarkdown({ children }: AiMarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
      components={markdownComponents}
    >
      {children}
    </ReactMarkdown>
  )
}
