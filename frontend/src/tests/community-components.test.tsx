import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi, beforeEach } from 'vitest'

import type { CommunityPost } from '@/types/community'

// Mock Virtuoso for jsdom: renders all items as flat list (no scroll virtualization in tests)
vi.mock('react-virtuoso', () => ({
  Virtuoso: ({ data, totalCount, itemContent, components }: any) => {
    const count = data ? data.length : (totalCount ?? 0)
    const items = []
    for (let i = 0; i < count; i++) {
      items.push(itemContent(i, data ? data[i] : undefined))
    }
    return (
      <div>
        {components?.Header?.()}
        {items}
        {components?.Footer?.()}
      </div>
    )
  },
}))

const communityHookMocks = vi.hoisted(() => ({
  useCommunityChartParams: vi.fn(),
  useCommunityFeed: vi.fn(),
  useCommunityTrending: vi.fn(),
  useCommunityPost: vi.fn(),
}))

vi.mock('@/hooks/useCommunity', () => communityHookMocks)

import { AccountAvatar } from '@/features/community/AccountAvatar'
import { CommunityExperience } from '@/features/community/CommunityExperience'
import { CommunityTimeline } from '@/features/community/CommunityTimeline'
import { FeedToggle } from '@/features/community/FeedToggle'
import { PostCard } from '@/features/community/PostCard'
import { setChineseStyle } from '@/lib/chinese'

// Mock IntersectionObserver for jsdom
class MockIntersectionObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
  constructor(_callback: IntersectionObserverCallback, _options?: IntersectionObserverInit) {}
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  communityHookMocks.useCommunityChartParams.mockReturnValue({})
  communityHookMocks.useCommunityFeed.mockReturnValue({
    posts: [],
    meta: { total: 0, total_all: 0, returned: 0, offset: 0, limit: 50 },
    loading: false,
    loadingMore: false,
    error: null,
    refetch: vi.fn(),
    hasMore: false,
    loadMore: vi.fn(),
  })
  communityHookMocks.useCommunityTrending.mockReturnValue({ trending: null })
  communityHookMocks.useCommunityPost.mockReturnValue({
    detail: null,
    loading: false,
    error: null,
    refetch: vi.fn(),
  })
})

afterEach(() => {
  act(() => setChineseStyle('original'))
})

function makePost(overrides: Partial<CommunityPost> = {}): CommunityPost {
  return {
    id: 'test-post-1',
    account_handle: '@chartdata',
    posted_at: '2024-06-15T12:00:00',
    content: 'Hot 100: #1(new) Test Song, Test Artist.',
    post_type: 'no1_announcement',
    tags: ['weekly', 'no1'],
    significance: 0.85,
    images: [],
    linked_entities: [
      { type: 'track', id: 1, name: 'Test Song' },
      { type: 'artist', name: 'Test Artist' },
    ],
    attached_list: null,
    metrics: { likes: 1234, retweets: 456, replies: 78, views: 9876 },
    ...overrides,
  }
}

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location-path">{location.pathname}</div>
}

it('updates names inside memoized community cards without changing entity links', async () => {
  renderWithRouter(
    <PostCard
      post={makePost({
        content: '永恆的主題，值得再次播放。',
        linked_entities: [{ type: 'track', id: 1, name: '永恆的主題' }],
      })}
    />,
  )

  act(() => setChineseStyle('simplified'))

  await waitFor(() => expect(screen.getByText('永恒的主题')).toBeInTheDocument())
  expect(screen.getByRole('link', { name: '永恒的主题' })).toHaveAttribute('href', '/music/tracks/1')
})


describe('AccountAvatar', () => {
  it('renders image for known account', () => {
    const { container } = renderWithRouter(<AccountAvatar handle="@chartdata" />)
    const img = container.querySelector('img')
    expect(img).toBeInTheDocument()
    expect(img!.getAttribute('src')).toContain('/avatars/chartdata.jpg')
  })

  it('renders fallback initials for account without avatar_url', () => {
    renderWithRouter(<AccountAvatar handle="@collectionvault" />)
    expect(screen.getByText('CV')).toBeInTheDocument()
  })

  it('renders size sm by default', () => {
    const { container } = renderWithRouter(<AccountAvatar handle="@chartdata" />)
    const el = container.firstElementChild as HTMLElement
    expect(el.className).toContain('w-10')
  })

  it('renders size xl', () => {
    const { container } = renderWithRouter(<AccountAvatar handle="@chartdata" size="xl" />)
    const el = container.firstElementChild as HTMLElement
    expect(el.className).toContain('w-24')
  })

  it('renders unknown handle with generated initials', () => {
    renderWithRouter(<AccountAvatar handle="@nonexistent" />)
    // Handles without account config fallback to first 2 chars after @ → "NO"
    expect(screen.getByText('NO')).toBeInTheDocument()
  })
})


describe('FeedToggle', () => {
  it('renders both buttons', () => {
    renderWithRouter(
      <FeedToggle active="highlights" onChange={() => {}} />,
    )
    expect(screen.getByText('精选')).toBeInTheDocument()
    expect(screen.getByText('全部')).toBeInTheDocument()
  })

  it('shows counts when provided', () => {
    renderWithRouter(
      <FeedToggle active="highlights" onChange={() => {}} highlightsCount={42} allCount={100} />,
    )
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('100')).toBeInTheDocument()
  })

  it('calls onChange with "all" when clicking 全部', () => {
    const onChange = vi.fn()
    renderWithRouter(<FeedToggle active="highlights" onChange={onChange} />)
    fireEvent.click(screen.getByText('全部'))
    expect(onChange).toHaveBeenCalledWith('all')
  })

  it('applies active styles to selected button', () => {
    renderWithRouter(<FeedToggle active="highlights" onChange={() => {}} />)
    const highlightBtn = screen.getByText('精选').closest('button')!
    const allBtn = screen.getByText('全部').closest('button')!

    expect(highlightBtn.className).toContain('bg-accent-foreground')
    expect(allBtn.className).not.toContain('bg-accent-foreground')
  })
})


describe('PostCard', () => {
  it('renders post content', () => {
    renderWithRouter(<PostCard post={makePost()} />)
    expect(screen.getByText(/Test Song/)).toBeInTheDocument()
    expect(screen.getByText(/Test Artist/)).toBeInTheDocument()
  })

  it('renders linked entity as clickable link', () => {
    renderWithRouter(<PostCard post={makePost()} />)
    const link = screen.getByText('Test Song')
    expect(link.tagName).toBe('A')
    expect(link.getAttribute('href')).toBe('/music/tracks/1')
  })

  it('shows expand button for long posts', () => {
    const longContent = 'A'.repeat(300)
    renderWithRouter(<PostCard post={makePost({ content: longContent })} />)
    expect(screen.getByText('展开')).toBeInTheDocument()
  })

  it('does not show expand button for short posts', () => {
    renderWithRouter(<PostCard post={makePost({ content: 'Short post' })} />)
    expect(screen.queryByText('展开')).not.toBeInTheDocument()
  })

  it('expands when clicking 展开 and then shows 收起', () => {
    const longContent = 'B'.repeat(300)
    renderWithRouter(<PostCard post={makePost({ content: longContent })} />)
    fireEvent.click(screen.getByText('展开'))
    expect(screen.queryByText('展开')).not.toBeInTheDocument()
    expect(screen.getByText('收起')).toBeInTheDocument()
  })

  it('renders post account handle', () => {
    renderWithRouter(<PostCard post={makePost()} />)
    expect(screen.getByText('@chartdata')).toBeInTheDocument()
  })

  it('renders single image as compact square container', () => {
    const { container } = renderWithRouter(
      <PostCard post={makePost({ images: ['/covers/albums/1.jpg'] })} />,
    )
    const squareContainer = container.querySelector('.w-40.h-40')
    expect(squareContainer).toBeInTheDocument()
    const contentImg = squareContainer?.querySelector('img')
    expect(contentImg).toBeInTheDocument()
    expect(contentImg?.getAttribute('src')).toBe('/covers/albums/1.jpg')
  })

  it('renders multi-image grid', () => {
    const images = ['/img/1.jpg', '/img/2.jpg', '/img/3.jpg']
    const { container } = renderWithRouter(<PostCard post={makePost({ images })} />)
    // Content images are in the grid (plus avatar image)
    const grid = container.querySelector('.grid-cols-2')
    expect(grid).toBeInTheDocument()
    expect(grid!.className).toContain('max-w-[320px]')
    const gridImgs = grid!.querySelectorAll('img')
    expect(gridImgs).toHaveLength(3)
  })

  it('renders metrics', () => {
    renderWithRouter(<PostCard post={makePost()} />)
    // Check that at least one formatted metric value is displayed
    expect(screen.getByText('1.2K')).toBeInTheDocument()
  })

  it('navigates to post detail when clicking the post body', () => {
    render(
      <MemoryRouter initialEntries={['/community']}>
        <PostCard post={makePost()} />
        <LocationProbe />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByText(/Hot 100/))

    expect(screen.getByTestId('location-path')).toHaveTextContent('/community/post/test-post-1')
  })
})


describe('CommunityTimeline', () => {
  it('renders posts', () => {
    const posts = [makePost(), makePost({ id: 'test-post-2', content: 'Second post' })]
    renderWithRouter(
      <CommunityTimeline
        posts={posts}
        loading={false}
        hasMore={false}
        onLoadMore={() => {}}
      />,
    )
    expect(screen.getByText(/Test Song/)).toBeInTheDocument()
    expect(screen.getByText('Second post')).toBeInTheDocument()
  })

  it('shows loading skeletons', () => {
    renderWithRouter(
      <CommunityTimeline
        posts={[]}
        loading={true}
        hasMore={false}
        onLoadMore={() => {}}
      />,
    )
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('shows empty state when no posts and not loading', () => {
    renderWithRouter(
      <CommunityTimeline
        posts={[]}
        loading={false}
        hasMore={false}
        onLoadMore={() => {}}
      />,
    )
    expect(screen.getByText('No posts yet')).toBeInTheDocument()
  })

  it('shows "no more posts" when hasMore is false and posts exist', () => {
    renderWithRouter(
      <CommunityTimeline
        posts={[makePost()]}
        loading={false}
        hasMore={false}
        onLoadMore={() => {}}
      />,
    )
    expect(screen.getByText('No more posts')).toBeInTheDocument()
  })

  it('does not show "no more posts" when hasMore is true', () => {
    renderWithRouter(
      <CommunityTimeline
        posts={[makePost()]}
        loading={false}
        hasMore={true}
        onLoadMore={() => {}}
      />,
    )
    expect(screen.queryByText('No more posts')).not.toBeInTheDocument()
  })
})


describe('CommunityExperience filter propagation', () => {
  it('passes chart settings params to feed and trending hooks', () => {
    const chartParams = {
      min_ms: 45000,
      music_only: true,
      bb_top_n: 77,
      bb_album_top_n: 66,
      bb_artist_top_n: 55,
      bb_week_start_dow: 2,
      bb_week_start_hour: 12,
      include_compilations: true,
      merge_level: 3,
      dynamic_threshold: false,
      max_merge_gap_minutes: 45,
    }
    communityHookMocks.useCommunityChartParams.mockReturnValue(chartParams)

    renderWithRouter(<CommunityExperience />)

    expect(communityHookMocks.useCommunityFeed).toHaveBeenCalledWith(
      expect.objectContaining({
        ...chartParams,
        limit: 50,
        offset: 0,
        highlights_only: true,
      }),
    )
    expect(communityHookMocks.useCommunityTrending).toHaveBeenCalledWith(
      expect.objectContaining(chartParams),
    )
  })
})
