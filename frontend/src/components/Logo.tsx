/** The Kairos forelock: the single lock of hair you grab while the moment is in front of you. */
export const FORELOCK_PATH = 'M14 50 C10 30 22 12 40 12 C52 12 56 24 48 30 C42 35 33 30 36 24 C38 20 44 21 44 25'

export function LogoMark({ size = 24, color = '#fbbf24' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Kairos logo">
      <path d={FORELOCK_PATH} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round" />
    </svg>
  )
}
