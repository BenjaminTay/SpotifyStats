import { useState } from 'react'
import { ACCOUNT_CONFIG } from './communityData'
import type { AccountInfo } from '@/types/community'

interface AccountAvatarProps {
  handle: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  linkable?: boolean
}

const SIZE_CLASSES = {
  sm: 'w-10 h-10 text-sm',
  md: 'w-12 h-12 text-base',
  lg: 'w-16 h-16 text-lg',
  xl: 'w-24 h-24 text-2xl',
}

export function AccountAvatar({ handle, size = 'sm', linkable = false }: AccountAvatarProps) {
  const account: AccountInfo | undefined = ACCOUNT_CONFIG[handle]
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const dims = SIZE_CLASSES[size]
  const avatar = account?.avatar
  const avatarUrl = account?.avatar_url

  const fallback = (
    <div
      className={`${dims} shrink-0 rounded-full flex items-center justify-center font-bold text-white select-none`}
      style={{ background: avatar?.bg_gradient ?? 'linear-gradient(135deg, #666, #333)' }}
      title={account?.display_name ?? handle}
    >
      {avatar?.initials ?? handle.slice(1, 3).toUpperCase()}
    </div>
  )

  if (avatarUrl && avatarUrl !== failedUrl) {
    const img = (
      <img
        loading="lazy"
        decoding="async"
        src={avatarUrl}
        alt={account?.display_name ?? handle}
        className={`${dims} shrink-0 rounded-full object-cover`}
        onError={() => setFailedUrl(avatarUrl)}
      />
    )
    if (linkable) {
      return (
        <div className="relative shrink-0">
          {img}
          <div className={`${dims} absolute inset-0 rounded-full ring-1 ring-inset ring-white/10 pointer-events-none`} />
        </div>
      )
    }
    return img
  }

  return fallback
}
