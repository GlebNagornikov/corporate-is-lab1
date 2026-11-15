import { useMutation, useQuery } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { Form, Link, useSearchParams } from 'react-router'
import { api, ApiError, requireData } from '../api/client'
import { tokens } from '../auth/tokens'
import { formatPrice } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import { managerReportQuery } from './queries'
import { readReportPeriod, reportPeriodError, type ReportPeriod } from './reportPeriod'
import './report.css'

const ReportCharts = lazy(() => import('./ReportCharts'))

function ExportReport({ period }: { period: ReportPeriod }) {
  const download = useMutation({
    mutationFn: async () => {
      const session = tokens.version()
      const blob = requireData(await api.GET('/api/manager/reports/sales/csv/', {
        params: { query: period }, parseAs: 'blob',
      }))
      return { session, blob }
    },
  })

  return (
    <div className="report-export">
      <button type="button" className="secondary" disabled={download.isPending}
        onClick={() => download.mutate(undefined, {
          onSuccess: ({ session, blob }) => {
            if (session !== tokens.version()) return
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `sales-${period.start}_${period.end}.csv`
            document.body.append(link)
            link.click()
            link.remove()
            window.setTimeout(() => URL.revokeObjectURL(url), 30_000)
          },
        })}>{download.isPending ? 'Подготовка CSV…' : 'Скачать CSV'}</button>
      {download.error && <p className="error" role="alert">{download.error.message}</p>}
    </div>
  )
}

export default function ManagerReportPage() {
  usePageTitle('Отчёт о продажах')
  const [search] = useSearchParams()
  const period = readReportPeriod(search)
  const periodError = reportPeriodError(period)
  const report = useQuery({ ...managerReportQuery(period), enabled: !periodError })
  if (report.error instanceof ApiError && report.error.status === 403) throw report.error
  const periodKey = JSON.stringify(period)

  return (
    <section className="report-page">
      <h1>Отчёт о продажах</h1>
      <div className="details report-period">
        <Form key={periodKey} method="get" className="report-period-form">
          <label>С даты<input type="date" name="start" defaultValue={period.start} required /></label>
          <label>По дату<input type="date" name="end" defaultValue={period.end} required /></label>
          <button type="submit">Показать</button>
          <Link to="/manager/reports">Последние 30 дней</Link>
        </Form>
        {report.data && !periodError && <ExportReport key={`csv-${periodKey}`} period={period} />}
      </div>
      {periodError && <p className="error" role="alert">{periodError}</p>}
      {!periodError && report.isPending && <p role="status">Загрузка отчёта…</p>}
      {report.error && <p className="error" role="alert">{report.error.message}</p>}
      {report.data && !periodError && (
        <>
          <dl className="report-summary">
            <div><dt>Заказы без отменённых</dt><dd>{report.data.summary.count}</dd></div>
            <div><dt>Выручка</dt><dd>{formatPrice(report.data.summary.revenue)}</dd></div>
            <div><dt>Средний чек</dt><dd>{formatPrice(report.data.summary.average)}</dd></div>
          </dl>
          {report.data.statuses.length === 0 ? (
            <p className="details">За выбранный период заказов нет.</p>
          ) : (
            <>
              <p className="muted">Выручка складывается из итоговых сумм заказов без отменённых, с учётом скидок и доставки.</p>
              <Suspense fallback={<p role="status">Загрузка графиков…</p>}>
                <ReportCharts report={report.data} />
              </Suspense>
            </>
          )}
        </>
      )}
    </section>
  )
}
