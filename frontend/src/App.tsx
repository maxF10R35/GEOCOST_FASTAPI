import { useEffect, useState } from 'react'

export default function App() {
  const [estado, setEstado] = useState('consultando...')
  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => setEstado(`API ${d.status} · v${d.version}`))
      .catch(() => setEstado('API no disponible'))
  }, [])
  return <h1>GeoCost SC · {estado}</h1>
}