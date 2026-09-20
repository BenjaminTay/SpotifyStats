import { act } from '@testing-library/react'
import { vi } from 'vitest'

export function installDeferredObserver(auto = false) {
  const observers: { callback: IntersectionObserverCallback; elements: Set<Element>; options?: IntersectionObserverInit }[] = []
  class Observer {
    entry: typeof observers[number]
    constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
      this.entry = { callback, elements: new Set(), options }; observers.push(this.entry)
    }
    observe = (element: Element) => {
      this.entry.elements.add(element)
      if (auto) this.entry.callback([{ target: element, isIntersecting: true }] as IntersectionObserverEntry[], this as unknown as IntersectionObserver)
    }
    unobserve = (element: Element) => this.entry.elements.delete(element)
    disconnect = () => this.entry.elements.clear()
  }
  vi.stubGlobal('IntersectionObserver', Observer)
  return {
    observers,
    enter: (selector: string) => act(() => {
      for (const observer of observers) for (const target of [...observer.elements]) {
        if (target.matches(selector)) observer.callback([{ target, isIntersecting: true }] as IntersectionObserverEntry[], {} as IntersectionObserver)
      }
    }),
  }
}
