export function rankToneClass(rank: number, highlightTopThree = false): string {
  return rank === 1
    ? 'text-accent-foreground'
    : rank === 2 && highlightTopThree
      ? 'text-[#727B88] dark:text-[#B8BEC8]'
      : rank === 3
        ? 'text-[#C17A4E] dark:text-[#C97B6B]'
        : 'text-muted-foreground'
}
