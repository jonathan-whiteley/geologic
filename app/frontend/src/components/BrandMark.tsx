import { useState } from 'react'
import { MASCOT, useTheme } from '../theme/ThemeContext'

/** Mascot only: the classic Caesar, or the glowing Count in Halloween mode. */
export default function BrandMark({ className = '', alt = 'Little Caesars' }: { className?: string; alt?: string }) {
  const { isHalloween } = useTheme()
  const [failed, setFailed] = useState(false)

  if (isHalloween && !failed) {
    return (
      <img
        src={MASCOT.halloween}
        alt={alt}
        title="Count Little Caesars"
        className={`count-glow ${className}`}
        onError={() => setFailed(true)}
      />
    )
  }

  return <img src={MASCOT.default} alt={alt} className={className} />
}

/**
 * Header lockup. Light: the official mascot + wordmark lockup, unchanged.
 * Halloween: the glowing Count takes the mascot's place next to the wordmark.
 */
export function BrandLockup() {
  const { isHalloween } = useTheme()

  if (!isHalloween) {
    return <img src="/lce-logo.svg" alt="Little Caesars" className="h-12 w-auto" />
  }

  return (
    <div className="flex items-center gap-2">
      <BrandMark className="h-14 w-auto -my-2" />
      <img src="/lc-wordmark.svg" alt="" aria-hidden="true" className="h-7 w-auto" />
    </div>
  )
}
