import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RecentPlaysSection } from '@/components/shared/RecentPlaysSection'
import { DEFERRED_ROOT_MARGIN } from '@/hooks/useDeferredInView'
import { installDeferredObserver } from './deferred-observer'
const rows = (name: string, total = 51) => ({ total, limit: 50, offset: 0, rows: [{ ts: '2026-09-19T03:00:00Z', date: '2026-09-19', track_name: name, track_id: 1, artist_name: 'artist', album_name: 'album', plays: 1, hours: 1, ms_played: 3600000 }] })
let observer: ReturnType<typeof installDeferredObserver>
beforeEach(() => { observer = installDeferredObserver() })
afterEach(() => { vi.unstubAllGlobals() })
function setup() {
 const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 300000 } } })
 const fetchPage = vi.fn().mockResolvedValue(rows('current'))
 const fetchPlayDates = vi.fn().mockResolvedValue([{ date: '2026-09-19', count: 1 }])
 const view = (id = '1', period: 'lifetime' | 'year' = 'lifetime', min_ms = 30000, project = 1) => <QueryClientProvider client={client}><MemoryRouter><RecentPlaysSection kind="album" entityId={id} artistName="artist" albumProjectId={project} mergeLevel={2} filters={{ min_ms } as never} apiParams={{ period }} fetchPage={fetchPage} fetchPlayDates={fetchPlayDates} /></MemoryRouter></QueryClientProvider>
 return { client, fetchPage, fetchPlayDates, view }
}
describe('Recent plays deferred queries', () => {
 it('has an explicit common margin and does not eagerly fall back without an observer', () => {
  vi.stubGlobal('IntersectionObserver', undefined); const h=setup(); render(h.view()); expect(h.fetchPage).not.toHaveBeenCalled(); expect(h.fetchPlayDates).not.toHaveBeenCalled(); expect(DEFERRED_ROOT_MARGIN).toBe('0px')
 })
 it('loads only at visibility, paginates, and loads dates only on first calendar open', async () => {
  const h=setup(); render(h.view()); expect(h.fetchPage).not.toHaveBeenCalled(); expect(observer.observers[0].options?.rootMargin).toBe('0px')
  observer.enter('[data-deferred="plays"]'); await screen.findByRole('link', { name: 'current' }); expect(h.fetchPage).toHaveBeenCalledTimes(1); expect(h.fetchPlayDates).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{ name: '下一页' })); await waitFor(() => expect(h.fetchPage).toHaveBeenLastCalledWith(2,50,undefined,undefined))
  fireEvent.click(screen.getByRole('button',{ name: '日历' })); await waitFor(() => expect(h.fetchPlayDates).toHaveBeenCalledTimes(1)); fireEvent.keyDown(document,{key:'Escape'}); fireEvent.click(screen.getByRole('button',{name:'日历'})); expect(h.fetchPlayDates).toHaveBeenCalledTimes(1)
 })
 it('shows errors rather than empty results, and retries explicitly', async () => {
  const h=setup(); h.fetchPage.mockRejectedValueOnce(new Error('fail')); render(h.view()); observer.enter('[data-deferred="plays"]'); expect(await screen.findByRole('alert')).toHaveTextContent('播放记录加载失败'); expect(screen.queryByText('暂无播放记录')).not.toBeInTheDocument(); fireEvent.click(screen.getByRole('button',{name:'重试'})); await screen.findByRole('link',{name:'current'})
 })
 it('isolates late entity, filter, period and project responses', async () => {
  const h=setup(); let resolve!: (value: ReturnType<typeof rows>) => void; h.fetchPage.mockImplementationOnce(() => new Promise(r => { resolve=r })); const v=render(h.view()); observer.enter('[data-deferred="plays"]')
  v.rerender(h.view('2','year',45000,2)); expect(h.fetchPage).toHaveBeenCalledTimes(1); observer.enter('[data-deferred="plays"]'); await screen.findByRole('link',{name:'current'}); await act(async()=>resolve(rows('obsolete'))); expect(screen.queryByText('obsolete')).not.toBeInTheDocument()
  expect(h.client.getQueryCache().getAll().filter(q=>q.queryKey[0]==='recent-plays')).toHaveLength(2)
 })
 it('uses search and selected date in the page key and resets pagination', async () => {
  const h=setup(); render(h.view()); observer.enter('[data-deferred="plays"]'); await screen.findByText('current'); fireEvent.change(screen.getByPlaceholderText(/搜索/),{target:{value:'new'}}); await waitFor(()=>expect(h.fetchPage).toHaveBeenLastCalledWith(1,50,'new',undefined))
  fireEvent.click(screen.getByRole('button',{name:'日历'})); await waitFor(()=>expect(h.fetchPlayDates).toHaveBeenCalledTimes(1));
  // The calendar date buttons carry the real localized date accessible name.
  const today = new Date(); const date = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-19`; const cell=document.querySelector(`[data-day="${date}"]`); expect(cell).not.toBeNull(); fireEvent.click(cell!.querySelector('button') ?? cell!); await waitFor(()=>expect(h.fetchPage).toHaveBeenLastCalledWith(1,50,'new',date))
 })
})
