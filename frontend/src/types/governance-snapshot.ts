export interface GovernanceSnapshot {
  status: 'ready' | 'warming'
  freshness: 'current' | 'last_known_good'
  checked_at: string
  checked_revision: string
  build_status: 'ready' | 'pending' | 'failed'
}
