import { AccountArchiveDesktopRoute } from '@/features/account-archive/route/AccountArchiveDesktopRoute'
import { AccountArchivePhoneRoute } from '@/features/account-archive/route/AccountArchivePhoneRoute'
import { useViewportMode } from '@/hooks/useViewportMode'

export function AccountCenterPage() {
  const mode = useViewportMode()
  return mode === 'phone' ? <AccountArchivePhoneRoute /> : <AccountArchiveDesktopRoute />
}
