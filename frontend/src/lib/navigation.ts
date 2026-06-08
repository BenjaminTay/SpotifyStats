/** 给 detail 链接附加 ?tab=overview 参数（已含其他参数时用 & 连接） */
export function billboardDetailLink(path: string): string {
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}tab=overview`
}
