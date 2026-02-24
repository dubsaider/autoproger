import { useState, useEffect } from 'react'
import { me } from './api'

let token: string | null = localStorage.getItem('token')

export function useAuth() {
  const [loading, setLoading] = useState(!!token)
  const [user, setUser] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }
    me()
      .then((d) => {
        setUser(d.username)
      })
      .catch(() => {
        localStorage.removeItem('token')
        token = null
      })
      .finally(() => setLoading(false))
  }, [])

  const setToken = (t: string | null) => {
    token = t
    if (t) localStorage.setItem('token', t)
    else localStorage.removeItem('token')
    setUser(t ? 'admin' : null)
  }

  return { token, user, loading, setToken }
}
