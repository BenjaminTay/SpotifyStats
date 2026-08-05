import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useSettings } from '@/hooks/useSettings'
import { useChatSessions, useDeleteSession } from '@/hooks/useAiInsights'
import type { ReportType } from '@/types/ai-insights'

import { ChatInterface } from './ChatInterface'
import { ChatSessionDrawer } from './ChatSessionDrawer'
import { ChatSessionList } from './ChatSessionList'
import { AiReportsPanel } from './AiReportsPanel'
import { LlmNotConfiguredState } from './AiInsightsPrimitives'
import { useViewportMode } from '@/hooks/useViewportMode'
import { cn } from '@/lib/utils'

export function AiInsightsExperience() {
  const viewportMode = useViewportMode()
  const isPhone = viewportMode === 'phone'
  const isCompact = viewportMode === 'compact'
  const { settings } = useSettings()
  const llmAvailable = settings?.llm_enabled && settings?.has_llm_key
  const [searchParams, setSearchParams] = useSearchParams()
  const routeTab = searchParams.get('mode') === 'chat' ? 'chat' : 'reports'
  const activeTab: 'reports' | 'chat' = routeTab
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false)
  const [chatResetKey, setChatResetKey] = useState(0)
  const [chatInitialQuestion, setChatInitialQuestion] = useState<string | null>(null)
  const [chatContext, setChatContext] = useState<ReportType | undefined>(undefined)
  const [chatContextLabel, setChatContextLabel] = useState<string | undefined>(undefined)
  const { data: sessions = [], isLoading: sessionsLoading } = useChatSessions()
  const deleteSession = useDeleteSession()

  const changeTab = useCallback((tab: 'reports' | 'chat') => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('mode', tab)
      return next
    }, { replace: true })
  }, [setSearchParams])

  useEffect(() => {
    const openHistory = () => setSessionDrawerOpen(true)
    window.addEventListener('spotify-stats:open-ai-history', openHistory)
    return () => window.removeEventListener('spotify-stats:open-ai-history', openHistory)
  }, [])

  const handleFollowUp = useCallback((question: string, label: string, context: ReportType) => {
    setChatInitialQuestion(question)
    setChatContext(context)
    setChatContextLabel(label)
    changeTab('chat')
  }, [changeTab])

  const handleSessionSelect = useCallback((id: number) => {
    setActiveSessionId(id)
    setChatContext(undefined)
    setChatContextLabel(undefined)
    setChatInitialQuestion(null)
  }, [])

  const handleSessionDelete = useCallback((id: number) => {
    deleteSession.mutate(id)
    if (activeSessionId === id) setActiveSessionId(null)
  }, [activeSessionId, deleteSession])

  const handleSessionNew = useCallback(() => {
    setActiveSessionId(null)
    setChatInitialQuestion(null)
    setChatContext(undefined)
    setChatContextLabel(undefined)
    setChatResetKey((key) => key + 1)
  }, [])

  return (
    <div className={cn('space-y-6', isPhone && 'mobile-ai-experience')} data-mobile-ai={activeTab}>
      <section className="mb-8 hidden md:block">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          AI / Insights
        </p>
        <h1 className="font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          AI 洞察
        </h1>
      </section>

      <nav className={cn('mb-7 flex gap-x-6 border-b border-border', isPhone && 'mobile-ai-mode-switch')} aria-label="AI 洞察模式">
        {(['reports', 'chat'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => changeTab(tab)}
            aria-pressed={activeTab === tab}
            className={`-mb-[1px] border-b-2 pb-2.5 font-sans text-[13px] font-medium transition-colors ${
              activeTab === tab
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab === 'reports' ? '报告' : '问答'}
          </button>
        ))}
        {isCompact && activeTab === 'chat' && (
          <button
            type="button"
            className="ml-auto -mb-px border-b-2 border-transparent pb-2.5 text-[12px] font-semibold text-muted-foreground"
            onClick={() => setSessionDrawerOpen(true)}
          >
            对话历史
          </button>
        )}
      </nav>

      {!llmAvailable ? (
        <LlmNotConfiguredState />
      ) : (
        <>
          <div className={`space-y-6 ${activeTab === 'reports' ? '' : 'hidden'}`}>
            <AiReportsPanel settings={settings} onFollowUp={handleFollowUp} />
          </div>

          <div className={activeTab === 'chat' ? '' : 'hidden'}>
            <div className="flex w-full min-w-0 gap-8">
              <div className="min-w-0 flex-1">
                <ChatInterface
                  key={chatResetKey}
                  initialQuestion={chatInitialQuestion}
                  onQuestionConsumed={() => setChatInitialQuestion(null)}
                  reportContext={chatContext}
                  reportContextLabel={chatContextLabel}
                  onBackToReport={() => changeTab('reports')}
                  sessionId={activeSessionId}
                  onSessionCreated={setActiveSessionId}
                />
              </div>

              <aside className="hidden w-[340px] shrink-0 lg:block">
                <div className="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-thin rounded-[16px] border border-border bg-card/30 backdrop-blur-[12px]">
                  <ChatSessionList
                    sessions={sessions}
                    activeId={activeSessionId}
                    onSelect={handleSessionSelect}
                    onDelete={handleSessionDelete}
                    onNew={handleSessionNew}
                    loading={sessionsLoading}
                  />
                </div>
              </aside>
            </div>

            <ChatSessionDrawer
              open={sessionDrawerOpen}
              onClose={() => setSessionDrawerOpen(false)}
              sessions={sessions}
              activeId={activeSessionId}
              onSelect={handleSessionSelect}
              onDelete={handleSessionDelete}
              onNew={handleSessionNew}
              loading={sessionsLoading}
            />
          </div>
        </>
      )}
    </div>
  )
}
