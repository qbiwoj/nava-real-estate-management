import { Link } from 'react-router-dom'

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-3 flex items-center gap-6">
        <Link to="/" className="select-none text-base font-bold tracking-widest text-foreground">
          NAVA
        </Link>
        <Link to="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
          Panel
        </Link>
        <Link to="/analytics" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
          Analityka
        </Link>
      </header>
      <main>{children}</main>
    </div>
  )
}
