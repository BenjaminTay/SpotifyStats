import type {
  ProfileData, WrappedHubData, InferencesData, SoundCapsuleData,
} from '@/types/account'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { cn } from '@/lib/utils'

interface IdentityTabProps {
  profile: ProfileData
  wrappedHub: WrappedHubData | null
  inferences: InferencesData | null
  soundCapsule: SoundCapsuleData | null
}

/* ------------------------------------------------------------------ */
/*  辅助函数：从 profile 中提取信息                                      */
/* ------------------------------------------------------------------ */

function getYearsSince(dateStr: string | null): number | null {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  const now = new Date()
  return now.getFullYear() - d.getFullYear()
}

function getStartYear(dateStr: string | null): string | null {
  if (!dateStr) return null
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  return String(d.getFullYear())
}

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

/* ------------------------------------------------------------------ */
/*  DNA 推断                                                           */
/* ------------------------------------------------------------------ */

interface DnaGene {
  emoji: string
  name: string
  tag: string
  description: string
}

function inferDna(profile: ProfileData): DnaGene[] {
  const { country } = profile.profile
  const firstPlayDate = profile.stats.first_play_date
  const followsCount = profile.follows.length
  const totalPlays = profile.stats.total_audio_plays

  // 地理基因
  let geoTag = '本地探索者'
  let geoDesc = '你的收听足迹以本地为主'
  if (country) {
    const c = country.toUpperCase()
    if (['US', 'GB', 'CA', 'AU', 'NZ'].includes(c)) {
      geoTag = '英语世界公民'
      geoDesc = '你的音乐口味深受英语文化圈影响'
    } else if (['JP'].includes(c)) {
      geoTag = '和风旅人'
      geoDesc = '你的音乐版图以日本为中心延展'
    } else if (['KR'].includes(c)) {
      geoTag = '韩流先锋'
      geoDesc = '韩国流行文化在你的听歌版图中占据核心'
    } else if (['CN', 'TW', 'HK'].includes(c)) {
      geoTag = '华语圈守望者'
      geoDesc = '你的音乐根系扎在华语土壤里'
    } else if (['DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'NO', 'DK', 'FI'].includes(c)) {
      geoTag = '欧陆旅人'
      geoDesc = '你的音乐品味横跨欧洲大陆'
    } else if (['BR', 'MX', 'AR', 'CO', 'CL'].includes(c)) {
      geoTag = '拉丁节奏之心'
      geoDesc = '拉丁美洲的律动在你的播放列表里流淌'
    } else {
      geoTag = '环球旅行者'
      geoDesc = '你的音乐足迹遍布世界各地'
    }
  }

  // 时间基因 — 用 first_play_date 的时间部分
  let timeTag = '全天候听众'
  let timeDesc = '音乐是你永不间断的背景音'
  if (firstPlayDate) {
    const d = new Date(firstPlayDate)
    if (!isNaN(d.getTime())) {
      const hour = d.getHours()
      if (hour >= 0 && hour < 6) {
        timeTag = '午夜猫头鹰'
        timeDesc = '深夜才是你的主场，音乐在夜色中最有灵魂'
      } else if (hour >= 6 && hour < 12) {
        timeTag = '晨间收听者'
        timeDesc = '你在一天的起点用音乐唤醒自己'
      } else if (hour >= 12 && hour < 18) {
        timeTag = '午后节奏师'
        timeDesc = '白天的音乐是你工作和生活的节拍器'
      } else {
        timeTag = '黄昏聆听者'
        timeDesc = '傍晚的音乐是你与世界的温柔对话'
      }
    }
  }

  // 忠诚基因 — 根据 follows 数量
  let loyaltyTag = '初识聆听者'
  let loyaltyDesc = '你正在探索自己的音乐边界'
  if (followsCount >= 100) {
    loyaltyTag = '殿堂级粉丝'
    loyaltyDesc = '你对音乐的热爱已经升华成信仰'
  } else if (followsCount >= 50) {
    loyaltyTag = '铁杆追随者'
    loyaltyDesc = '你对自己喜欢的音乐人从不吝啬关注'
  } else if (followsCount >= 20) {
    loyaltyTag = '忠实听众'
    loyaltyDesc = '你有一批心爱的音乐人陪你走过时光'
  } else if (followsCount >= 5) {
    loyaltyTag = '品味收藏家'
    loyaltyDesc = '你精挑细选，每一位关注的都是心头好'
  }

  // 探索基因 — 根据 total_audio_plays
  let exploreTag = '初涉音乐'
  let exploreDesc = '你的音乐旅程刚刚启航'
  if (totalPlays >= 50000) {
    exploreTag = '声音考古学家'
    exploreDesc = '你见过太多音乐，每一次播放都是考古发掘'
  } else if (totalPlays >= 20000) {
    exploreTag = '音乐马拉松跑者'
    exploreDesc = '你已经跑赢 99% 的听众，但探索永无止境'
  } else if (totalPlays >= 5000) {
    exploreTag = '深度探索者'
    exploreDesc = '你的播放列表比大多数人都要深和广'
  } else if (totalPlays >= 1000) {
    exploreTag = '好奇宝宝'
    exploreDesc = '你正在快速拓宽自己的音乐版图'
  }

  // 情绪基因 — 占位
  const emotionTag = '情绪光谱'
  const emotionDesc = '你的情绪基因正等待更多的数据来解码'

  return [
    { emoji: '🌍', name: '地理基因', tag: geoTag, description: geoDesc },
    { emoji: '⏰', name: '时间基因', tag: timeTag, description: timeDesc },
    { emoji: '❤️', name: '忠诚基因', tag: loyaltyTag, description: loyaltyDesc },
    { emoji: '🔭', name: '探索基因', tag: exploreTag, description: exploreDesc },
    { emoji: '🎭', name: '情绪基因', tag: emotionTag, description: emotionDesc },
  ]
}

/* ------------------------------------------------------------------ */
/*  子组件                                                            */
/* ------------------------------------------------------------------ */

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-5 font-serif text-xl font-semibold">
      {children}
    </h2>
  )
}

/* ---------------------- 1. 身份档案 -------------------------------- */

function IdentityArchive({ profile }: { profile: ProfileData }) {
  const p = profile.profile
  const displayName = p.identity_displayName || p.identity_firstName || '未知用户'
  const username = p.attr_username
  const country = p.attr_country
  const birthdate = p.attr_birthdate
  const imageUrl = p.identity_imageUrl
  const listeningAge = getYearsSince(profile.stats.first_play_date)
  const startYear = getStartYear(profile.stats.first_play_date)
  const totalPlays = profile.stats.total_audio_plays

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* 左侧 — 身份卡片 */}
      <GlassCard className="lg:col-span-2 p-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
          {/* 头像 */}
          <div className="flex-shrink-0">
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={displayName}
                className="h-24 w-24 rounded-full object-cover border-2 border-border"
              />
            ) : (
              <div className="h-24 w-24 rounded-full bg-gradient-to-br from-amber-300 via-rose-400 to-indigo-500 flex items-center justify-center">
                <span className="font-serif text-3xl font-bold text-white">
                  {displayName.charAt(0).toUpperCase()}
                </span>
              </div>
            )}
          </div>

          {/* 信息 */}
          <div className="flex flex-col gap-2">
            <h3 className="font-serif text-3xl font-bold">{displayName}</h3>
            {username && (
              <p className="font-sans text-sm text-muted-foreground">
                @{username}
              </p>
            )}
            <div className="flex flex-wrap gap-x-5 gap-y-1 font-sans text-sm text-muted-foreground">
              {country && <span>{country}</span>}
              {birthdate && <span>{birthdate}</span>}
            </div>

            {/* 标签行 */}
            <div className="mt-3 flex flex-wrap gap-2">
              {listeningAge !== null && (
                <span className="inline-flex items-center rounded-full border border-border px-3 py-1 font-sans text-xs font-medium">
                  {listeningAge} 年收听
                </span>
              )}
              <span className="inline-flex items-center rounded-full border border-border px-3 py-1 font-sans text-xs font-medium">
                {formatNumber(totalPlays)} 次播放
              </span>
              {startYear && (
                <span className="inline-flex items-center rounded-full border border-border px-3 py-1 font-sans text-xs font-medium">
                  始于 {startYear}
                </span>
              )}
            </div>
          </div>
        </div>
      </GlassCard>

      {/* 右侧 — 时间线 */}
      <GlassCard className="p-6">
        <h3 className="mb-4 font-serif text-lg font-semibold">时间线</h3>
        <div className="relative pl-6">
          {/* 竖线 */}
          <div className="absolute left-2 top-1 bottom-1 w-px bg-border" />

          {/* 首次播放 */}
          <div className="relative mb-5">
            <div className="absolute -left-[22px] top-1 h-3 w-3 rounded-full border-2 border-foreground bg-background" />
            <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
              首次播放
            </p>
            <p className="font-sans text-sm">
              {profile.stats.first_play_date || '未知'}
            </p>
          </div>

          {/* 注册账号 — 如果有 username */}
          {profile.profile.attr_username && (
            <div className="relative mb-5">
              <div className="absolute -left-[22px] top-1 h-3 w-3 rounded-full border-2 border-muted-foreground bg-background" />
              <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                Spotify 账号
              </p>
              <p className="font-sans text-sm">@{profile.profile.attr_username}</p>
            </div>
          )}

          {/* 出生日期 — 如果有 */}
          {profile.profile.attr_birthdate && (
            <div className="relative mb-5">
              <div className="absolute -left-[22px] top-1 h-3 w-3 rounded-full border-2 border-muted-foreground bg-background" />
              <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                出生日期
              </p>
              <p className="font-sans text-sm">{profile.profile.attr_birthdate}</p>
            </div>
          )}

          {/* 关注总数 */}
          <div className="relative">
            <div className="absolute -left-[22px] top-1 h-3 w-3 rounded-full border-2 border-muted-foreground bg-background" />
            <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
              关注
            </p>
            <p className="font-sans text-sm">
              {profile.follows.length > 0
                ? `${profile.follows.length} 位`
                : '没有关注'}
            </p>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}

/* ---------------------- 2. 官方 Wrapped ---------------------------- */

function WrappedIdentity({ wrappedHub }: { wrappedHub: WrappedHubData | null }) {
  if (!wrappedHub || !wrappedHub.available) {
    return (
      <GlassCard className="p-6">
        <p className="font-sans text-sm text-muted-foreground">
          Wrapped 数据不可用
        </p>
      </GlassCard>
    )
  }

  const { clubs, party_metrics: partyMetrics, archive_reports: reports, listening_age: listeningAge } = wrappedHub

  return (
    <div className="space-y-5">
      {/* 三列并排 */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {/* 列1 — 你的俱乐部 */}
        <GlassCard className="p-5">
          <h3 className="mb-3 font-serif text-lg font-semibold">你的俱乐部</h3>
          {clubs.length === 0 ? (
            <p className="font-sans text-sm text-muted-foreground">暂无俱乐部数据</p>
          ) : (
            <div className="space-y-3">
              {clubs.map((club, i) => (
                <div key={i} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                  <p className="font-sans text-sm font-semibold">{club.club_name}</p>
                  <p className="font-sans text-xs text-muted-foreground">
                    {club.role} &middot; {club.artist_name}
                  </p>
                  <p className="font-sans text-xs font-medium text-muted-foreground mt-0.5">
                    前 {club.percent_in_club}%
                  </p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* 列2 — 派对性格 */}
        <GlassCard className="p-5">
          <h3 className="mb-3 font-serif text-lg font-semibold">派对性格</h3>
          {partyMetrics.length === 0 ? (
            <p className="font-sans text-sm text-muted-foreground">暂无派对数据</p>
          ) : (
            <div className="space-y-3">
              {partyMetrics.map((m, i) => (
                <div key={i} className="flex items-center justify-between border-b border-border pb-3 last:border-b-0 last:pb-0">
                  <span className="font-sans text-sm">{m.metric}</span>
                  <span className="font-serif text-xl font-bold">{m.value}</span>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* 列3 — 档案报告 */}
        <GlassCard className="p-5">
          <h3 className="mb-3 font-serif text-lg font-semibold">档案报告</h3>
          {reports.length === 0 ? (
            <p className="font-sans text-sm text-muted-foreground">暂无档案报告</p>
          ) : (
            <div className="space-y-3">
              {reports.map((r, i) => (
                <div key={i} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                  <p className="font-sans text-sm font-semibold">{r.title}</p>
                  <p className="font-sans text-xs text-muted-foreground mt-0.5 line-clamp-2">
                    {r.description}
                  </p>
                  <p className="font-sans text-xs text-muted-foreground mt-1">
                    {r.minutes_listened} 分钟
                  </p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>

      {/* 底部统计数字行 */}
      {listeningAge && (
        <GlassCard className="p-5">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
            <div>
              <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                收听年龄
              </p>
              <p className="font-serif text-2xl font-bold">{listeningAge.age}</p>
            </div>
            <div>
              <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                起始年份
              </p>
              <p className="font-serif text-2xl font-bold">{listeningAge.window_start_year}</p>
            </div>
            <div>
              <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                时代阶段
              </p>
              <p className="font-serif text-2xl font-bold">{listeningAge.decade_phase}</p>
            </div>
          </div>
        </GlassCard>
      )}
    </div>
  )
}

/* ---------------------- 3. 社交 + 边界 ----------------------------- */

function SocialAndBoundaries({ profile }: { profile: ProfileData }) {
  const { follows, banned_items: bannedItems } = profile

  // 按 type 分组 follows
  const followsByType: Record<string, typeof follows> = {}
  for (const f of follows) {
    const t = f.type || 'other'
    if (!followsByType[t]) followsByType[t] = []
    followsByType[t].push(f)
  }

  // type 名称映射
  const typeLabels: Record<string, string> = {
    user: '位用户',
    artist: '位艺人',
    playlist: '个歌单',
  }

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      {/* 左半边 — 关注 */}
      <GlassCard className="p-6">
        <h3 className="mb-4 font-serif text-lg font-semibold">关注 / 粉丝</h3>

        {follows.length === 0 ? (
          <p className="font-sans text-sm text-muted-foreground">没有关注数据</p>
        ) : (
          <>
            {/* 统计数 */}
            <div className="flex flex-wrap gap-4 mb-4">
              {Object.entries(followsByType).map(([type, items]) => (
                <div key={type}>
                  <span className="font-serif text-3xl font-bold">{items.length}</span>
                  <span className="font-sans text-sm text-muted-foreground ml-1">
                    {typeLabels[type] || `${type}`}
                  </span>
                </div>
              ))}
            </div>

            {/* 名称标签云 */}
            <div className="flex flex-wrap gap-1.5">
              {follows.slice(0, 30).map((f, i) => (
                <span
                  key={i}
                  className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 font-sans text-xs"
                >
                  {f.name}
                </span>
              ))}
              {follows.length > 30 && (
                <span className="font-sans text-xs text-muted-foreground">
                  ...还有 {follows.length - 30} 个
                </span>
              )}
            </div>
          </>
        )}
      </GlassCard>

      {/* 右半边 — 已屏蔽 */}
      <GlassCard className="p-6">
        <h3 className="mb-4 font-serif text-lg font-semibold">已屏蔽</h3>

        {bannedItems.length === 0 ? (
          <p className="font-sans text-sm text-muted-foreground">没有屏蔽项目</p>
        ) : (
          <div className="space-y-2">
            {bannedItems.map((item, i) => (
              <div
                key={i}
                className="flex items-center justify-between border-b border-border pb-2 last:border-b-0 last:pb-0"
              >
                <span className="font-sans text-sm">{item.name}</span>
                <span className="font-sans text-xs text-muted-foreground">{item.type}</span>
              </div>
            ))}
          </div>
        )}

        <p className="mt-4 font-serif text-sm italic text-muted-foreground">
          品味不只在于喜欢什么，也在于不喜欢什么
        </p>
      </GlassCard>
    </div>
  )
}

/* ---------------------- 4. 数字足迹 -------------------------------- */

function DigitalFootprint({ profile, inferences }: { profile: ProfileData; inferences: InferencesData | null }) {
  const { prompts, follows } = profile

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      {/* 列1 — AI 对话 */}
      <GlassCard className="p-5">
        <h3 className="mb-3 font-serif text-lg font-semibold">AI 对话</h3>
        {prompts.length === 0 ? (
          <p className="font-sans text-sm italic text-muted-foreground">
            你还没有和 Spotify AI 对话过
          </p>
        ) : (
          <div className="space-y-3">
            {prompts.slice(0, 8).map((prompt, i) => (
              <div key={i} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                <p className="font-sans text-sm line-clamp-2">{prompt.message}</p>
                <p className="font-sans text-xs text-muted-foreground mt-1">{prompt.created}</p>
              </div>
            ))}
            {prompts.length > 8 && (
              <p className="font-sans text-xs text-muted-foreground">
                ...还有 {prompts.length - 8} 条对话
              </p>
            )}
          </div>
        )}
      </GlassCard>

      {/* 列2 — 互动足迹 */}
      <GlassCard className="p-5">
        <h3 className="mb-3 font-serif text-lg font-semibold">互动足迹</h3>
        <div className="space-y-4">
          <div>
            <span className="font-serif text-4xl font-bold">
              {follows.length}
            </span>
            <p className="font-sans text-sm text-muted-foreground mt-1">
              关注总数
            </p>
          </div>
          {prompts.length > 0 && (
            <div>
              <span className="font-serif text-4xl font-bold">
                {prompts.length}
              </span>
              <p className="font-sans text-sm text-muted-foreground mt-1">
                AI 对话次数
              </p>
            </div>
          )}
        </div>
      </GlassCard>

      {/* 列3 — 兴趣推断 */}
      <GlassCard className="p-5">
        <h3 className="mb-3 font-serif text-lg font-semibold">兴趣推断</h3>
        {inferences && inferences.available ? (
          <div className="space-y-3">
            <p className="font-sans text-xs text-muted-foreground">
              Spotify 根据你的收听行为推断出 {inferences.total} 条兴趣标签
            </p>
            {Object.entries(inferences.categories).slice(0, 4).map(([cat, texts]) => (
              <div key={cat}>
                <p className="mb-1 font-sans text-[11px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                  {cat}
                </p>
                <div className="flex flex-wrap gap-1">
                  {texts.slice(0, 8).map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-accent-foreground/6 px-2 py-0.5 font-sans text-[10px] text-foreground"
                    >
                      {t}
                    </span>
                  ))}
                  {texts.length > 8 && (
                    <span className="font-sans text-[10px] text-muted-foreground">
                      +{texts.length - 8}
                    </span>
                  )}
                </div>
              </div>
            ))}
            {Object.keys(inferences.categories).length > 4 && (
              <p className="font-sans text-[10px] text-muted-foreground">
                ...还有 {Object.keys(inferences.categories).length - 4} 个类别
              </p>
            )}
          </div>
        ) : (
          <p className="font-sans text-sm italic text-muted-foreground">
            未导入兴趣推断数据
          </p>
        )}
      </GlassCard>
    </div>
  )
}

/* ---------------------- 5. Spotify DNA ----------------------------- */

function SpotifyDna({ profile }: { profile: ProfileData }) {
  const genes = inferDna(profile)

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {genes.map((gene) => (
        <GlassCard key={gene.name} className="p-4 text-center">
          <p className="text-3xl mb-2">{gene.emoji}</p>
          <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground mb-1">
            {gene.name}
          </p>
          <p className="font-serif text-base font-bold mb-1">{gene.tag}</p>
          <p className="font-sans text-xs text-muted-foreground leading-relaxed">
            {gene.description}
          </p>
        </GlassCard>
      ))}
    </div>
  )
}

/* ---------------------- 6. 声音胶囊 ----------------------------- */

function SoundCapsuleBlock({ data }: { data: SoundCapsuleData | null }) {
  if (!data || !data.available) {
    return (
      <GlassCard className="p-5">
        <p className="font-sans text-sm italic text-muted-foreground">
          未导入声音胶囊数据
        </p>
      </GlassCard>
    )
  }

  return (
    <div className="space-y-4">
      {data.highlights && data.highlights.length > 0 && (
        <GlassCard className="p-5">
          <h3 className="mb-4 font-serif text-lg font-semibold">高光时刻</h3>
          <div className="space-y-3">
            {data.highlights.map((h, i) => (
              <div key={i} className="flex items-start gap-3 border-b border-border pb-3 last:border-b-0 last:pb-0">
                <div className="mt-0.5 flex-shrink-0 rounded-full bg-accent-foreground/8 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground">
                  {h.type}
                </div>
                <div>
                  <p className="font-sans text-sm font-medium">{h.entity_name || h.date}</p>
                  <p className="font-sans text-xs text-muted-foreground">{h.date}</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {data.daily && data.daily.length > 0 && (
        <GlassCard className="p-5">
          <h3 className="mb-4 font-serif text-lg font-semibold">每日聆听</h3>
          <div className="space-y-3">
            {data.daily.map((d, i) => (
              <div key={i} className="flex items-center justify-between border-b border-border pb-3 last:border-b-0 last:pb-0">
                <p className="font-sans text-sm">{d.date}</p>
                <div className="flex gap-6 text-right">
                  <div>
                    <p className="font-serif text-xl font-bold">{d.stream_count.toLocaleString()}</p>
                    <p className="font-sans text-[10px] text-muted-foreground">首</p>
                  </div>
                  <div>
                    <p className="font-serif text-xl font-bold">{Math.round(d.seconds_played / 60).toLocaleString()}</p>
                    <p className="font-sans text-[10px] text-muted-foreground">分钟</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}

/* ---------------------- 主组件 ------------------------------------ */

export function IdentityTab({ profile, wrappedHub, inferences, soundCapsule }: IdentityTabProps) {
  return (
    <div className="space-y-8">
      {/* 1. 身份档案 */}
      <section className="space-y-4">
        <SectionTitle>身份档案</SectionTitle>
        <IdentityArchive profile={profile} />
      </section>

      {/* 2. 官方 Wrapped 身份 */}
      <section className="space-y-4">
        <SectionTitle>官方 Wrapped 身份</SectionTitle>
        <WrappedIdentity wrappedHub={wrappedHub} />
      </section>

      {/* 3. 社交 + 边界 */}
      <section className="space-y-4">
        <SectionTitle>社交 + 边界</SectionTitle>
        <SocialAndBoundaries profile={profile} />
      </section>

      {/* 4. 数字足迹 */}
      <section className="space-y-4">
        <SectionTitle>数字足迹</SectionTitle>
        <DigitalFootprint profile={profile} inferences={inferences} />
      </section>

      {/* 5. 声音胶囊 */}
      <section className="space-y-4">
        <SectionTitle>声音胶囊</SectionTitle>
        <SoundCapsuleBlock data={soundCapsule} />
      </section>

      {/* 6. Spotify DNA */}
      <section className="space-y-4">
        <SectionTitle>Spotify DNA</SectionTitle>
        <SpotifyDna profile={profile} />
      </section>
    </div>
  )
}
