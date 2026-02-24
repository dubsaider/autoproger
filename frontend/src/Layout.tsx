import { Outlet, useNavigate, NavLink } from 'react-router-dom'
import { useAuth } from './useAuth'

export default function Layout() {
  const { user, setToken } = useAuth()
  const navigate = useNavigate()

  const logout = () => {
    setToken(null)
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-zinc-800 bg-zinc-900/50 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <h1 className="font-semibold text-zinc-100">Autoproger — Админ-панель</h1>
          <nav className="flex gap-2">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `text-sm ${isActive ? 'text-amber-400' : 'text-zinc-400 hover:text-zinc-200'}`
              }
            >
              Настройки
            </NavLink>
            <NavLink
              to="/issues"
              className={({ isActive }) =>
                `text-sm ${isActive ? 'text-amber-400' : 'text-zinc-400 hover:text-zinc-200'}`
              }
            >
              Текущие issues
            </NavLink>
            <NavLink
              to="/issues/new"
              className={({ isActive }) =>
                `text-sm ${isActive ? 'text-amber-400' : 'text-zinc-400 hover:text-zinc-200'}`
              }
            >
              Новый issue
            </NavLink>
            <NavLink
              to="/problems"
              className={({ isActive }) =>
                `text-sm ${isActive ? 'text-amber-400' : 'text-zinc-400 hover:text-zinc-200'}`
              }
            >
              Поиск проблем
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-zinc-400 text-sm">{user}</span>
          <button
            type="button"
            onClick={logout}
            className="text-sm text-amber-400 hover:text-amber-300"
          >
            Выйти
          </button>
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
