import { useAdminStats } from '@/hooks/useThreads'
import { Skeleton } from '@/components/ui/skeleton'

const STATUS_LABEL: Record<string, string> = {
  new: 'Nowy',
  pending_review: 'Do sprawdzenia',
  replied: 'Odpowiedziano',
  resolved: 'Zamknięty',
  escalated: 'Eskalowany',
}

const PRIORITY_LABEL: Record<string, string> = {
  urgent: 'Pilny',
  high: 'Wysoki',
  medium: 'Średni',
  low: 'Niski',
}

const PRIORITY_COLOR: Record<string, string> = {
  urgent: 'bg-red-500',
  high: 'bg-orange-400',
  medium: 'bg-yellow-400',
  low: 'bg-gray-400',
}

const CATEGORY_LABEL: Record<string, string> = {
  maintenance: 'Usterka',
  payment: 'Płatność',
  noise_complaint: 'Hałas',
  lease: 'Najem',
  general: 'Ogólne',
  supplier: 'Dostawca',
  other: 'Inne',
}

function BarSection({
  title,
  data,
  labelMap,
  colorMap,
}: {
  title: string
  data: Record<string, number>
  labelMap: Record<string, string>
  colorMap?: Record<string, string>
}) {
  const total = Object.values(data).reduce((s, n) => s + n, 0)
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])

  return (
    <div>
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">{title}</h2>
      <div className="space-y-2">
        {entries.map(([key, count]) => {
          const pct = total > 0 ? Math.round((count / total) * 100) : 0
          const barColor = colorMap?.[key] ?? 'bg-blue-400'
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="w-32 text-sm text-right shrink-0">{labelMap[key] ?? key}</span>
              <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
                <div
                  className={`h-full rounded ${barColor} transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="w-16 text-xs text-muted-foreground shrink-0">
                {count} ({pct}%)
              </span>
            </div>
          )
        })}
        {entries.length === 0 && (
          <p className="text-sm text-muted-foreground">Brak danych.</p>
        )}
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const { data: stats, isLoading } = useAdminStats()

  const totalThreads = stats
    ? Object.values(stats.by_status).reduce((s, n) => s + n, 0)
    : 0

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">Analityka</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="border rounded-lg p-4">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))
        ) : (
          <>
            <div className="border rounded-lg p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Wątki łącznie</p>
              <p className="text-2xl font-bold">{totalThreads}</p>
            </div>
            <div className="border rounded-lg p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Uruchomień agenta</p>
              <p className="text-2xl font-bold">{stats?.costs.agent_runs ?? 0}</p>
            </div>
            <div className="border rounded-lg p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Łączny koszt</p>
              <p className="text-2xl font-bold">${stats?.costs.agent_total_usd.toFixed(4) ?? '0.0000'}</p>
              <p className="text-xs text-muted-foreground mt-1">
                śr. ${stats?.costs.avg_cost_per_run_usd.toFixed(5) ?? '0.00000'}/uruchomienie
              </p>
            </div>
          </>
        )}
      </div>

      {/* Bar charts */}
      {isLoading ? (
        <div className="space-y-8">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-32 mb-3" />
              {Array.from({ length: 4 }).map((_, j) => (
                <Skeleton key={j} className="h-4 w-full" />
              ))}
            </div>
          ))}
        </div>
      ) : stats ? (
        <div className="space-y-8">
          <BarSection title="Wg statusu" data={stats.by_status} labelMap={STATUS_LABEL} />
          <BarSection title="Wg priorytetu" data={stats.by_priority} labelMap={PRIORITY_LABEL} colorMap={PRIORITY_COLOR} />
          <BarSection title="Wg kategorii" data={stats.by_category} labelMap={CATEGORY_LABEL} />

          {/* Cost by model */}
          {Object.keys(stats.costs.by_model).length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Koszty wg modelu</h2>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Model</th>
                    <th className="py-2 pr-4 font-medium">Uruchomień</th>
                    <th className="py-2 font-medium">Koszt (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats.costs.by_model).map(([model, row]) => (
                    <tr key={model} className="border-b">
                      <td className="py-2 pr-4 font-mono text-xs">{model}</td>
                      <td className="py-2 pr-4">{row.runs}</td>
                      <td className="py-2">${row.cost_usd.toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
