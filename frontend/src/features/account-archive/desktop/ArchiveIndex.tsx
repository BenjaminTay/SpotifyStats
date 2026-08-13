import type { ArchiveSectionKey } from '@/types/accountArchive'
import { ARCHIVE_SECTIONS } from '@/features/account-archive/model/archiveModel'
import { cn } from '@/lib/utils'

export function ArchiveIndex({
  activeSection,
  onSelect,
}: {
  activeSection: ArchiveSectionKey
  onSelect: (section: ArchiveSectionKey) => void
}) {
  return (
    <nav className="archive-index" aria-label="音乐档案章节">
      <p>章节目录</p>
      <ol>
        {ARCHIVE_SECTIONS.map((section) => (
          <li key={section.key}>
            <button
              type="button"
              className={cn(activeSection === section.key && 'active')}
              aria-current={activeSection === section.key ? 'location' : undefined}
              onClick={() => onSelect(section.key)}
            >
              <span>{section.number}</span>
              <strong className="archive-index-label-full">{section.label}</strong>
              <strong className="archive-index-label-short">{section.shortLabel}</strong>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
