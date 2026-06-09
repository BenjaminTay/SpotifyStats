/** 给 detail 链接附加 ?tab=overview 参数（已含其他参数时用 & 连接） */
export function billboardDetailLink(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}tab=overview`
}

/** 从多艺人数据中提取主艺人名用于链接 */
export function primaryArtistName(entry: {
  artist_name: string
  artist_names?: string[]
}): string {
  return entry.artist_names?.[0] ?? entry.artist_name
}
