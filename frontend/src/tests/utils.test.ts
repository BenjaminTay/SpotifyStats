import { describe, it, expect } from 'vitest'
import { cn } from '@/lib/utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('filters falsy values', () => {
    expect(cn('foo', false && 'hidden', undefined, 'bar')).toBe('foo bar')
  })

  it('handles conditional classes via object', () => {
    expect(cn('base', { active: true, disabled: false })).toBe('base active')
  })

  it('resolves Tailwind conflicts via twMerge', () => {
    expect(cn('px-4', 'px-2')).toBe('px-2')
  })

  it('returns empty string for no args', () => {
    expect(cn()).toBe('')
  })
})
