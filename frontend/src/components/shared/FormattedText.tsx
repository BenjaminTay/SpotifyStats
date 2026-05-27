import { useTheme } from '@/hooks/useTheme'

interface FormattedTextProps {
  text: string
  className?: string
}

/**
 * Renders LLM-translated text with **bold** and *italic* markdown.
 * Safe to use — text comes from our own LLM translation pipeline, not user input.
 */
export function FormattedText({ text, className }: FormattedTextProps) {
  if (!text) return null

  // Convert markdown to HTML
  const html = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Preserve paragraph breaks
    .replace(/\n\n/g, '</p><p class="mt-3">')

  return (
    <p
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
