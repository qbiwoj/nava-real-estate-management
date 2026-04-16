import { Loader2 } from 'lucide-react'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  text?: string
}

const sizes = {
  sm: 24,
  md: 32,
  lg: 48,
}

export function Spinner({ size = 'md', text }: SpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <Loader2 size={sizes[size]} className="animate-spin text-muted-foreground" />
      {text && <p className="text-sm text-muted-foreground">{text}</p>}
    </div>
  )
}
