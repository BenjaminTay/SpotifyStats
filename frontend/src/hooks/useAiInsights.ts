import { useCallback, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import { CancelError, NetworkError, TimeoutError } from '@/api/errors'
import type { AnalysisStatsResponse } from '@/types/analysis'
import type {
  AskResponse,
  ChatMessage,
  MonthlyPersonalityResponse,
  WeeklyDigestResponse,
  YearlyStoryResponse,
} from '@/types/ai-insights'

function errMsg(error: unknown): string | null {
  if (!error) return null
  if (error instanceof CancelError) return null
  if (error instanceof TimeoutError) return '请求超时，请检查网络后重试'
  if (error instanceof NetworkError) return '网络连接失败，请检查网络'
  if (error instanceof Error) {
    const msg = error.message
    if (msg.includes('503') || msg.includes('LLM 未配置')) return 'AI 功能未配置，请在设置中配置 LLM'
    if (msg.includes('502')) return 'AI 服务调用失败，请稍后重试'
    if (msg.includes('500')) return '数据查询失败，请稍后重试'
    return msg
  }
  return String(error)
}

export function useWeeklyDigest(weekStart: string, weekEnd: string, enabled = true) {
  const queryClient = useQueryClient()
  const signalRef = useRef<AbortController | null>(null)
  const [forceRefresh, setForceRefresh] = useState(0)
  const force = forceRefresh > 0

  const query = useQuery({
    queryKey: [...queryKeys.aiInsights.weeklyDigest(weekStart, weekEnd), forceRefresh] as const,
    queryFn: ({ signal }) => {
      signalRef.current = new AbortController()
      signal.addEventListener('abort', () => signalRef.current?.abort(), { once: true })
      return api.get<WeeklyDigestResponse>(
        '/ai-insights/weekly-digest',
        { week_start: weekStart, week_end: weekEnd, ...(force ? { force: true } : {}) },
        120_000,
        signalRef.current.signal,
      )
    },
    enabled: enabled && !!weekStart && !!weekEnd && weekStart <= weekEnd,
    staleTime: 1000 * 60 * 60 * 6,
  })

  const refetch = useCallback(() => {
    setForceRefresh((f) => f + 1)
  }, [])

  const cancel = useCallback(() => {
    signalRef.current?.abort()
    queryClient.cancelQueries({ queryKey: queryKeys.aiInsights.weeklyDigest(weekStart, weekEnd) })
  }, [queryClient, weekStart, weekEnd])

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    fetching: query.isFetching,
    error: errMsg(query.error),
    refetch,
    cancel,
    cachedAt: query.data?.cached_at ?? null,
    entities: query.data?.entities ?? null,
  }
}

export function useMonthlyPersonality(month: string, year: number, enabled = true) {
  const queryClient = useQueryClient()
  const signalRef = useRef<AbortController | null>(null)
  const [forceRefresh, setForceRefresh] = useState(0)
  const force = forceRefresh > 0

  const query = useQuery({
    queryKey: [...queryKeys.aiInsights.monthlyPersonality(month, year), forceRefresh] as const,
    queryFn: ({ signal }) => {
      signalRef.current = new AbortController()
      signal.addEventListener('abort', () => signalRef.current?.abort(), { once: true })
      return api.get<MonthlyPersonalityResponse>(
        '/ai-insights/monthly-personality',
        { month, year, ...(force ? { force: true } : {}) },
        120_000,
        signalRef.current.signal,
      )
    },
    enabled: enabled && !!month && year > 0,
    staleTime: 1000 * 60 * 60 * 12,
  })

  const refetch = useCallback(() => {
    setForceRefresh((f) => f + 1)
  }, [])

  const cancel = useCallback(() => {
    signalRef.current?.abort()
    queryClient.cancelQueries({ queryKey: queryKeys.aiInsights.monthlyPersonality(month, year) })
  }, [queryClient, month, year])

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    fetching: query.isFetching,
    error: errMsg(query.error),
    refetch,
    cancel,
    cachedAt: query.data?.cached_at ?? null,
    entities: query.data?.entities ?? null,
  }
}

export function useYearlyStory(year: number, enabled = true) {
  const queryClient = useQueryClient()
  const signalRef = useRef<AbortController | null>(null)
  const [forceRefresh, setForceRefresh] = useState(0)
  const force = forceRefresh > 0

  const query = useQuery({
    queryKey: [...queryKeys.aiInsights.yearlyStory(year), forceRefresh] as const,
    queryFn: ({ signal }) => {
      signalRef.current = new AbortController()
      signal.addEventListener('abort', () => signalRef.current?.abort(), { once: true })
      return api.get<YearlyStoryResponse>(
        '/ai-insights/yearly-story',
        { year, ...(force ? { force: true } : {}) },
        120_000,
        signalRef.current.signal,
      )
    },
    enabled: enabled && year > 0,
    staleTime: 1000 * 60 * 60 * 24 * 3,
  })

  const refetch = useCallback(() => {
    setForceRefresh((f) => f + 1)
  }, [])

  const cancel = useCallback(() => {
    signalRef.current?.abort()
    queryClient.cancelQueries({ queryKey: queryKeys.aiInsights.yearlyStory(year) })
  }, [queryClient, year])

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    fetching: query.isFetching,
    error: errMsg(query.error),
    refetch,
    cancel,
    cachedAt: query.data?.cached_at ?? null,
    entities: query.data?.entities ?? null,
  }
}

export function useAskQuestion() {
  const signalRef = useRef<AbortController | null>(null)

  const mutation = useMutation({
    mutationFn: (payload: {
      question: string
      conversation_history?: ChatMessage[]
    }) => {
      signalRef.current = new AbortController()
      return api.post<AskResponse>(
        '/ai-insights/ask',
        payload,
        60_000,
        signalRef.current.signal,
      )
    },
  })

  const cancel = useCallback(() => {
    signalRef.current?.abort()
  }, [])

  return {
    ask: mutation.mutateAsync,
    answer: mutation.data?.answer ?? null,
    response: mutation.data ?? null,
    asking: mutation.isPending,
    error: errMsg(mutation.error),
    cancel,
  }
}

export function useLatestListeningRange() {
  const query = useQuery({
    queryKey: [...queryKeys.aiInsights.all, 'latest-listening-range'] as const,
    queryFn: () => api.get<AnalysisStatsResponse>('/analysis/stats', { period: 'lifetime' }),
    staleTime: 30 * 60 * 1000,
  })

  return {
    latestDate: query.data?.period.end_date ?? null,
    earliestDate: query.data?.period.start_date ?? null,
    loading: query.isLoading,
  }
}

export function useSuggestedQuestions(context?: string) {
  const query = useQuery({
    queryKey: queryKeys.aiInsights.suggestedQuestions(context),
    queryFn: () =>
      api.get<{ questions: string[] }>('/ai-insights/suggested-questions', context ? { context } : undefined),
    staleTime: Infinity,
  })

  return {
    questions: query.data?.questions ?? [],
    isLoading: query.isLoading,
  }
}
