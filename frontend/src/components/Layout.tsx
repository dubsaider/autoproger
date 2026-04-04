import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";
import clsx from "clsx";

const NAV = [
  { path: "/", label: "Dashboard" },
  { path: "/repos", label: "Repos" },
  { path: "/tasks", label: "Tasks" },
  { path: "/settings", label: "Settings" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation();
  const nav = useNavigate();

  const logout = () => {
    clearToken();
    nav("/login");
  };

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-5 border-b border-gray-800">
          <h1 className="text-lg font-bold tracking-tight text-white">
            Autoproger <span className="text-xs text-gray-500">v2</span>
          </h1>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map((n) => (
            <Link
              key={n.path}
              to={n.path}
              className={clsx(
                "block px-3 py-2 rounded-lg text-sm transition-colors",
                loc.pathname === n.path
                  ? "bg-indigo-600/20 text-indigo-400"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-800">
          <button
            onClick={logout}
            className="w-full px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors text-left"
          >
            Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 p-8 overflow-auto">{children}</main>
    </div>
  );
}
