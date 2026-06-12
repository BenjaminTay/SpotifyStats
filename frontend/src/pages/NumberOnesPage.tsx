import { useSearchParams } from 'react-router-dom'

import { NumberOnesExperience } from '@/features/billboard/number-ones/NumberOnesExperience'

export function NumberOnesPage() {
  const [searchParams] = useSearchParams()
  const mergeLevel = Number(searchParams.get('merge_level') ?? '2')
  return <NumberOnesExperience mergeLevel={mergeLevel} />
}
