import { Fragment, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

import { cn } from '@/lib/utils'
import { MobileBottomSheet } from './MobileBottomSheet'

export type MobileRecordColumnRole = 'entity' | 'primary' | 'secondary' | 'fact' | 'hidden'

export interface MobileRecordColumn<T> {
  header: ReactNode
  mobileHeader?: ReactNode
  mobileRole?: MobileRecordColumnRole
  render: (row: T, index: number) => ReactNode
}

interface MobileRecordTableProps<T extends object> {
  rows: T[]
  columns: MobileRecordColumn<T>[]
  record?: { title: string; key: string } | null
  previewCount?: number
  skip?: number
  rowClassName?: string
  renderRank: (rank: number) => ReactNode
  renderRow?: (row: T, index: number) => ReactNode
  sheetDataName?: string
}

/** Shared phone projection for record tables and their complete-list sheet. */
export function MobileRecordTable<T extends object>({
  rows,
  columns,
  record,
  previewCount = 3,
  skip = 0,
  rowClassName,
  renderRank,
  renderRow,
  sheetDataName = 'record-list',
}: MobileRecordTableProps<T>) {
  const [searchParams, setSearchParams] = useSearchParams()
  const fullListTriggerRef = useRef<HTMLButtonElement>(null)
  const fullListOpen = Boolean(record && searchParams.get('record') === record.key)
  const [visibleState, setVisibleState] = useState({ rows, fullListOpen, count: 20 })
  const visibleCount = visibleState.rows === rows && visibleState.fullListOpen === fullListOpen
    ? visibleState.count
    : 20

  const previewRows = rows.slice(skip, skip + previewCount)
  const fullRows = rows.slice(0, visibleCount)
  const hasRankColumn = columns[0]?.header === '#'
  const rankIndex = hasRankColumn ? 0 : -1
  const explicitEntityIndex = columns.findIndex((column) => column.mobileRole === 'entity')
  const entityIndex = explicitEntityIndex >= 0 ? explicitEntityIndex : Math.min(1, columns.length - 1)
  const candidateIndexes = columns
    .map((_column, index) => index)
    .filter((index) => index !== rankIndex && index !== entityIndex && columns[index]?.mobileRole !== 'hidden')
  const explicitPrimaryIndex = columns.findIndex((column) => column.mobileRole === 'primary')
  const defaultPrimaryIndex = hasRankColumn ? 2 : candidateIndexes[0]
  const primaryIndex = explicitPrimaryIndex >= 0
    ? explicitPrimaryIndex
    : candidateIndexes.includes(defaultPrimaryIndex) ? defaultPrimaryIndex : candidateIndexes[0]
  const secondaryIndexes = candidateIndexes.filter((index) => columns[index]?.mobileRole === 'secondary')
  const entityColumn = columns[entityIndex]
  const primaryColumn = primaryIndex == null ? undefined : columns[primaryIndex]
  const secondaryColumns = secondaryIndexes.map((index) => columns[index])
  const factColumns = candidateIndexes
    .filter((index) => index !== primaryIndex && !secondaryIndexes.includes(index))
    .map((index) => columns[index])

  const renderRows = (items: T[], startIndex: number, full = false) => (
    <div className={cn('mobile-record-rank-list', full && 'mobile-record-rank-list-full')}>
      {items.map((row, rowIndex) => {
        const absoluteIndex = startIndex + rowIndex
        if (renderRow) return <Fragment key={absoluteIndex}>{renderRow(row, absoluteIndex)}</Fragment>
        return (
          <article key={absoluteIndex} className={cn('mobile-record-rank-row', rowClassName)}>
            <div className="mobile-record-rank-number">
              <span>{hasRankColumn ? columns[0]?.render(row, absoluteIndex) : renderRank(absoluteIndex + 1)}</span>
            </div>
            <div className="mobile-record-rank-entity">
              <span>{entityColumn?.render(row, absoluteIndex)}</span>
            </div>
            {(primaryColumn || secondaryColumns.length > 0) && (
              <div className={cn('mobile-record-rank-metrics', secondaryColumns.length > 0 && 'mobile-record-rank-metrics-paired')}>
                {primaryColumn && (
                  <div className="mobile-record-rank-primary">
                    {primaryColumn.mobileHeader !== null && (
                      <small>{primaryColumn.mobileHeader ?? primaryColumn.header}</small>
                    )}
                    <span>{primaryColumn.render(row, absoluteIndex)}</span>
                  </div>
                )}
                {secondaryColumns.map((column, columnIndex) => (
                  <div key={columnIndex} className="mobile-record-rank-secondary">
                    {column.mobileHeader !== null && (
                      <small>{column.mobileHeader ?? column.header}</small>
                    )}
                    <span>{column.render(row, absoluteIndex)}</span>
                  </div>
                ))}
              </div>
            )}
            {factColumns.length > 0 && (
              <div className="mobile-record-rank-facts">
                {factColumns.map((column, columnIndex) => (
                  <div key={columnIndex}>
                    <small>{column.header}</small>
                    <span>{column.render(row, absoluteIndex)}</span>
                  </div>
                ))}
              </div>
            )}
          </article>
        )
      })}
    </div>
  )

  const openFullList = () => {
    if (!record) return
    setVisibleState({ rows, fullListOpen: true, count: 20 })
    const next = new URLSearchParams(searchParams)
    next.set('record', record.key)
    setSearchParams(next)
  }

  const closeFullList = () => {
    setVisibleState({ rows, fullListOpen: false, count: 20 })
    const next = new URLSearchParams(searchParams)
    next.delete('record')
    setSearchParams(next, { replace: true })
  }

  return (
    <>
      {renderRows(previewRows, skip)}
      {rows.length > skip + previewCount && record && (
        <button ref={fullListTriggerRef} type="button" className="mobile-record-expand" onClick={openFullList}>
          <span>查看完整榜单</span>
          <small>{rows.length} 项</small>
        </button>
      )}
      {record && (
        <MobileBottomSheet
          open={fullListOpen}
          onOpenChange={(open) => { if (!open) closeFullList() }}
          title={record.title}
          description={`完整榜单 · ${rows.length} 项`}
          triggerRef={fullListTriggerRef}
          className="mobile-record-full-sheet"
          contentClassName="mobile-record-full-content"
          dataSheet={sheetDataName}
        >
          {renderRows(fullRows, 0, true)}
          {visibleCount < rows.length && (
            <button
              type="button"
              className="mobile-record-load-more"
              onClick={() => setVisibleState({ rows, fullListOpen, count: Math.min(visibleCount + 20, rows.length) })}
            >
              加载更多
              <small>{Math.min(visibleCount, rows.length)} / {rows.length}</small>
            </button>
          )}
        </MobileBottomSheet>
      )}
    </>
  )
}
