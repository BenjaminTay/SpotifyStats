import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FormattedText } from '@/components/shared/FormattedText'

describe('FormattedText', () => {
  it('renders plain text', () => {
    render(<FormattedText text="Hello world" />)
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders markdown bold', () => {
    render(<FormattedText text="Hello **bold** world" />)
    const bold = screen.getByText('bold')
    expect(bold).toBeInTheDocument()
    expect(bold.tagName).toBe('STRONG')
  })

  it('renders markdown italic', () => {
    render(<FormattedText text="Hello *italic* world" />)
    const italic = screen.getByText('italic')
    expect(italic).toBeInTheDocument()
    expect(italic.tagName).toBe('EM')
  })

  it('strips dangerous HTML via sanitize', () => {
    const { container } = render(
      <FormattedText text='<img src=x onerror="alert(1)">safe' />,
    )
    // The img tag should be stripped, but "safe" text remains
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('safe')
  })

  it('returns null for empty string', () => {
    const { container } = render(<FormattedText text="" />)
    expect(container.innerHTML).toBe('')
  })

  it('applies className to paragraphs', () => {
    render(<FormattedText text="text" className="test-class" />)
    expect(screen.getByText('text').className).toBe('test-class')
  })
})
