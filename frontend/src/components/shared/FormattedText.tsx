import ReactMarkdown from "react-markdown"
import rehypeSanitize from "rehype-sanitize"

interface FormattedTextProps {
  text: string
  className?: string
}

/**
 * Renders LLM-translated text with **bold** and *italic* markdown.
 * Uses react-markdown with rehype-sanitize to prevent XSS — no
 * dangerouslySetInnerHTML. Only allows p/strong/em/br elements.
 */
export function FormattedText({ text, className }: FormattedTextProps) {
  if (!text) return null

  return (
    <ReactMarkdown
      rehypePlugins={[rehypeSanitize]}
      allowedElements={["p", "strong", "em", "br"]}
      unwrapDisallowed={true}
      components={{
        p: ({ children }) => <p className={className}>{children}</p>,
      }}
    >
      {text}
    </ReactMarkdown>
  )
}
