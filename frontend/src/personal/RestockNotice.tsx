import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router'
import type { components } from '../api/schema'
import StoreIcon from '../components/StoreIcon'
import './restockNotice.css'

type Notification = components['schemas']['RestockNotification']

function playChime(audio: AudioContext) {
  const start = audio.currentTime
  for (const [index, frequency] of [660, 880].entries()) {
    const noteStart = start + index * 0.12
    const end = noteStart + 0.22
    const note = audio.createOscillator()
    const volume = audio.createGain()
    note.frequency.value = frequency
    note.connect(volume)
    volume.connect(audio.destination)
    volume.gain.setValueAtTime(0, noteStart)
    volume.gain.linearRampToValueAtTime(0.055, noteStart + 0.025)
    volume.gain.linearRampToValueAtTime(0, end)
    note.onended = () => volume.disconnect()
    note.start(noteStart)
    note.stop(end)
  }
}

export default function RestockNotice({ notifications }: { notifications?: Notification[] }) {
  const audio = useRef<AudioContext | null>(null)
  const seen = useRef<Set<number> | null>(null)
  const [activeIds, setActiveIds] = useState<number[]>([])

  useEffect(() => {
    if (typeof AudioContext === 'undefined') return
    const unlockSound = () => {
      try {
        audio.current ??= new AudioContext()
      } catch {
        return
      }
      if (audio.current.state === 'suspended') void audio.current.resume().catch(() => {})
    }
    if (navigator.userActivation?.hasBeenActive) unlockSound()
    window.addEventListener('click', unlockSound, true)
    window.addEventListener('keydown', unlockSound, true)
    return () => {
      window.removeEventListener('click', unlockSound, true)
      window.removeEventListener('keydown', unlockSound, true)
      void audio.current?.close().catch(() => {})
      audio.current = null
    }
  }, [])

  useEffect(() => {
    if (!notifications) return
    const previous = seen.current
    // The first successful response establishes the baseline for this page session.
    seen.current = new Set(notifications.map(({ id }) => id))
    if (!previous) return
    const added = notifications.filter(({ id, read_at }) => read_at === null && !previous.has(id))
    if (!added.length) return
    setActiveIds((ids) => [...ids, ...added.map(({ id }) => id)])
    if (audio.current?.state === 'running') playChime(audio.current)
  }, [notifications])

  const active = notifications?.filter(({ id, read_at }) => read_at === null && activeIds.includes(id)) ?? []
  const latest = active[0]
  const dismiss = () => setActiveIds([])

  return createPortal(
    <div className={latest ? 'restock-notice' : undefined}>
      <div role="status" aria-atomic="true">
        {latest && <>
          <p className="restock-notice-title"><StoreIcon name="bell" /> Книга снова в наличии</p>
          <p>{latest.product_name}</p>
          {active.length > 1 && <p>Ещё уведомлений: {active.length - 1}</p>}
        </>}
      </div>
      {latest && <div className="restock-notice-actions">
        {latest.product_is_active && (
          <Link to={`/products/${encodeURIComponent(latest.product_slug)}`} onClick={dismiss}>К книге</Link>
        )}
        <Link to="/notifications" onClick={dismiss}>Все уведомления</Link>
        <button type="button" className="secondary" onClick={dismiss}>Закрыть</button>
      </div>}
    </div>,
    document.body,
  )
}
