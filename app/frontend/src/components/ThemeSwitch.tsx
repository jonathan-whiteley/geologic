import { Sun, Ghost } from 'lucide-react'
import { useTheme } from '../theme/ThemeContext'

/** Two-position slider between Light and Spooky (Halloween) mode. */
export default function ThemeSwitch({ className = '' }: { className?: string }) {
  const { isHalloween, toggle } = useTheme()

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isHalloween}
      aria-label="Spooky mode"
      title={isHalloween ? 'Switch to Light mode' : 'Switch to Spooky mode'}
      onClick={toggle}
      className={`relative grid grid-cols-2 w-[8.5rem] h-9 p-1 rounded-full bg-surface-secondary border border-gray-100 text-xs font-semibold select-none shrink-0 ${className}`}
    >
      <span
        aria-hidden="true"
        className={`absolute top-1 bottom-1 left-1 w-[calc(50%-0.25rem)] rounded-full shadow-soft transition-all duration-300 ease-out ${
          isHalloween
            ? 'translate-x-full bg-gradient-to-r from-[#6D28D9] to-lce-orange'
            : 'translate-x-0 bg-surface'
        }`}
      />
      <span className={`relative z-10 flex items-center justify-center gap-1 transition-colors ${isHalloween ? 'text-text-tertiary' : 'text-lce-orange'}`}>
        <Sun className="w-3.5 h-3.5" />
        Light
      </span>
      <span className={`relative z-10 flex items-center justify-center gap-1 transition-colors ${isHalloween ? 'text-white' : 'text-text-tertiary'}`}>
        <Ghost className="w-3.5 h-3.5" />
        Spooky
      </span>
    </button>
  )
}
