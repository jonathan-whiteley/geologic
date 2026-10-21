import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export const MASCOT = {
  default: '/lce-mascot.svg',
  halloween: '/count-caesar.png',
}

/** Recharts takes colors as SVG attributes, so charts read them from here instead of CSS variables. */
interface ChartTheme {
  orange: string
  orangeDark: string
  ink: string
  rival: string
  gridColor: string
  tickColor: string
  axisColor: string
  series: string[]
}

interface ThemeContextType {
  isHalloween: boolean
  toggle: () => void
  chart: ChartTheme
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const STORAGE_KEY = 'geologic-theme'

/** ?theme=halloween|light wins (handy for demo links), then the saved choice. */
function initialHalloween(): boolean {
  const param = new URLSearchParams(window.location.search).get('theme')
  if (param === 'halloween' || param === 'light') {
    localStorage.setItem(STORAGE_KEY, param)
    return param === 'halloween'
  }
  return localStorage.getItem(STORAGE_KEY) === 'halloween'
}

const LIGHT_CHART: ChartTheme = {
  orange: '#FF671B',
  orangeDark: '#E0530F',
  ink: '#1A1A1A',
  rival: '#D1D5DB',
  gridColor: '#F0F1F2',
  tickColor: '#9CA3AF',
  axisColor: '#6B7280',
  series: ['#FF671B', '#1A1A1A', '#FF9A5C', '#9CA3AF', '#C2410C', '#6B7280'],
}

const HALLOWEEN_CHART: ChartTheme = {
  orange: '#FF671B',
  orangeDark: '#FF9A5C',
  ink: '#E8DCC8',
  rival: '#857C93',
  gridColor: '#2E2538',
  tickColor: '#857C93',
  axisColor: '#B8AFC4',
  series: ['#FF671B', '#B57BFF', '#FF9A5C', '#7CE38B', '#E8DCC8', '#857C93'],
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isHalloween, setIsHalloween] = useState(initialHalloween)

  useEffect(() => {
    document.documentElement.classList.toggle('halloween', isHalloween)
    document.documentElement.classList.toggle('dark', isHalloween)
    localStorage.setItem(STORAGE_KEY, isHalloween ? 'halloween' : 'light')
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (icon) {
      icon.type = isHalloween ? 'image/png' : 'image/svg+xml'
      icon.href = isHalloween ? MASCOT.halloween : MASCOT.default
    }
  }, [isHalloween])

  const toggle = () => setIsHalloween(v => !v)

  return (
    <ThemeContext.Provider value={{ isHalloween, toggle, chart: isHalloween ? HALLOWEEN_CHART : LIGHT_CHART }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
