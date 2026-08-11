export function mobileRecordTitle(title: string): string {
  return title.split(' · ')[0]?.trim() || title
}
