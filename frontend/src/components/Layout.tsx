import { Link } from 'react-router-dom'

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-3 flex items-center">
        <Link to="/" className="select-none text-base font-bold tracking-widest text-foreground">
          NAVA
        </Link>
      </header>
      <main>{children}</main>
    </div>
  )
}
