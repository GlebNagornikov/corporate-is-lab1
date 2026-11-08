const paths = {
  bag: 'M5 7h14l1 14H4L5 7Zm4 2V6a3 3 0 0 1 6 0v3',
  heart: 'M12 20 4 12a4.5 4.5 0 0 1 6.4-6.4L12 7l1.6-1.4A4.5 4.5 0 0 1 20 12l-8 8Z',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-2 7-2 9h16c0-2-2-2-2-9Zm-8 12a2 2 0 0 0 4 0',
}

export default function StoreIcon({ name }: { name: keyof typeof paths }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true"><path d={paths[name]} /></svg>
}
