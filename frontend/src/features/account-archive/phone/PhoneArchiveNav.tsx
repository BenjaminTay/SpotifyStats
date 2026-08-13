import { ARCHIVE_SECTIONS } from '@/features/account-archive/model/archiveModel'
import type { ArchiveSectionKey } from '@/types/accountArchive'

export function PhoneArchiveNav({
  activeSection,
  onSelect,
}: {
  activeSection: ArchiveSectionKey
  onSelect: (section: ArchiveSectionKey) => void
}) {
  return (
    <nav className="phone-archive-nav" aria-label="音乐档案章节">
      <ol>
        {ARCHIVE_SECTIONS.map((section, index) => (
          <li key={section.key}>
            <button
              type="button"
              className={activeSection === section.key ? 'active' : undefined}
              aria-current={activeSection === section.key ? 'true' : undefined}
              onClick={() => onSelect(section.key)}
            >
              <span>{String(index).padStart(2, '0')}</span>{section.shortLabel}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
