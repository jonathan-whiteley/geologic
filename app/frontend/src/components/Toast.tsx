import { createContext, useCallback, useContext, useRef, useState, ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

const Ctx = createContext<(msg: string) => void>(() => {})
export const useToast = () => useContext(Ctx)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null)
  const timer = useRef<number>()
  const show = useCallback((m: string) => {
    setMsg(m); window.clearTimeout(timer.current); timer.current = window.setTimeout(() => setMsg(null), 2600)
  }, [])
  return (
    <Ctx.Provider value={show}>
      {children}
      <AnimatePresence>
        {msg && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="fixed right-6 bottom-6 z-50 bg-lce-black text-white text-sm font-medium px-4 py-3 rounded-xl shadow-strong">
            {msg}
          </motion.div>
        )}
      </AnimatePresence>
    </Ctx.Provider>
  )
}
