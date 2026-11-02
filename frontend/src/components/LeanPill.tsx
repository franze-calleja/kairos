import type { AIStatus, Lean } from '../api/schemas'
import { leanLabel } from './lean'

export function LeanPill(props: { lean: Lean | null; aiStatus: AIStatus | null; hype?: boolean }) {
  const label = leanLabel(props.lean, props.aiStatus, props.hype)
  const tone = props.hype
    ? 'hype'
    : props.aiStatus === 'not_enough_signal'
      ? 'muted'
      : (props.lean ?? 'none')
  return <span className={`pill pill-${tone}`}>{label}</span>
}
