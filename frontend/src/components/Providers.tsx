import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/api/query-client'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ThemeProvider } from '@/hooks/useTheme'
import { RuntimeCapabilitiesProvider } from '@/hooks/useRuntimeCapabilities'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <RuntimeCapabilitiesProvider>
        <ThemeProvider>
          <TooltipProvider>{children}</TooltipProvider>
        </ThemeProvider>
      </RuntimeCapabilitiesProvider>
    </QueryClientProvider>
  )
}
