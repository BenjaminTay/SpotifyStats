import { useMutation, useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  AskResponse,
  ChatMessage,
  MonthlyPersonalityResponse,
  WeeklyDigestResponse,
  YearlyStoryResponse,
} from '@/types/ai-insights'

function errMsg(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? String(error) : null
}

export function useWeeklyDigest(weekStart: string, weekEnd: string) {
  const query = useQuery({
    queryKey: queryKeys.aiInsights.weeklyDigest(weekStart, weekEnd),
    queryFn: () =>
      api.get<WeeklyDigestResponse>(
        '/ai-insights/weekly-digest',
        { week_start: weekStart, week_end: weekEnd },
        60_000,
      ),
    enabled: !!weekStart && !!weekEnd,
    staleTime: 1000 * 60 * 60 * 6,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errMsg(query.error),
    refetch: () => query.refetch(),
  }
}

export function useMonthlyPersonality(month: string, year: number) {
  const query = useQuery({
    queryKey: queryKeys.aiInsights.monthlyPersonality(month, year),
    queryFn: () =>
      api.get<MonthlyPersonalityResponse>(
        '/ai-insights/monthly-personality',
        { month, year },
        60_000,
      ),
    enabled: !!month && year > 0,
    staleTime: 1000 * 60 * 60 * 12,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errMsg(query.error),
    refetch: () => query.refetch(),
  }
}

export function useYearlyStory(year: number) {
  const query = useQuery({
    queryKey: queryKeys.aiInsights.yearlyStory(year),
    queryFn: () =>
      api.get<YearlyStoryResponse>('/ai-insights/yearly-story', { year }, 60_000),
    enabled: year > 0,
    staleTime: 1000 * 60 * 60 * 24 * 3,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errMsg(query.error),
    refetch: () => query.refetch(),
  }
}

export function useAskQuestion() {
  const mutation = useMutation({
    mutationFn: (payload: {
      question: string
      conversation_history?: ChatMessage[]
    }) =>
      api.post<AskResponse>(
        '/ai-insights/ask',
        payload,
        60_000,
      ),
  })

  return {
    ask: mutation.mutateAsync,
    answer: mutation.data ?? null,
    asking: mutation.isPending,
    error: errMsg(mutation.error),
  }
}

export function useSuggestedQuestions() {
  const query = useQuery({
    queryKey: queryKeys.aiInsights.suggestedQuestions(),
    queryFn: () =>
      api.get<{ questions: string[] }>('/ai-insights/suggested-questions'),
    staleTime: Infinity,
  })

  return {
    questions: query.data?.questions ?? [],
  }
}
