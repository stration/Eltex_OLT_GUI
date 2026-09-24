import { NavLink, Route, Routes } from 'react-router-dom';
import { Network, Terminal, Settings as SettingsIcon } from 'lucide-react';
import OltList from './pages/OltList';
import OltDetail from './pages/OltDetail';
import OntList from './pages/OntList';
import OntDetail from './pages/OntDetail';
import OntUnactivated from './pages/OntUnactivated';
import TerminalPage from './pages/TerminalPage';
import Settings from './pages/Settings';
import TopLoadingBar from './components/TopLoadingBar';

export default function App() {
  return (
    <div className="min-h-full flex bg-slate-50">
      <TopLoadingBar />

      <aside className="w-60 shrink-0 border-r border-slate-200 bg-white flex flex-col">
        {/* Логотип */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="text-base font-semibold text-slate-900 tracking-tight">
            LTP-GUI
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Eltex LTP management
          </div>
        </div>

        {/* Меню */}
        <nav className="flex-1 px-3 py-3 flex flex-col gap-0.5">
          <SidebarLink to="/" icon={<Network size={18} />} end>
            OLT
          </SidebarLink>
          <SidebarLink to="/terminal" icon={<Terminal size={18} />}>
            Терминал
          </SidebarLink>
          <SidebarLink to="/settings" icon={<SettingsIcon size={18} />}>
            Настройки
          </SidebarLink>
        </nav>

        {/* Футер */}
        <div className="px-5 py-3 border-t border-slate-100 text-xs text-slate-400">
          v0.4.0 · спринт 4
        </div>
      </aside>

      <main className="flex-1 p-6 overflow-auto">
        <Routes>
          <Route path="/" element={<OltList />} />
          <Route path="/olts/:id" element={<OltDetail />} />
          <Route path="/olts/:id/onts" element={<OntList />} />
          <Route path="/olts/:id/onts/unactivated" element={<OntUnactivated />} />
          <Route path="/olts/:id/onts/:port/:ont" element={<OntDetail />} />
          <Route path="/terminal" element={<TerminalPage />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

// ---- SidebarLink --------------------------------------------------------

function SidebarLink({
  to,
  icon,
  end,
  children,
}: {
  to: string;
  icon: React.ReactNode;
  end?: boolean;
  children: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          'relative flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
          isActive
            ? 'bg-accent-50 text-accent-700'
            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          {/* Акцентная полоса слева */}
          <span
            className={[
              'absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r transition-opacity',
              isActive ? 'bg-accent-500 opacity-100' : 'opacity-0',
            ].join(' ')}
            aria-hidden
          />
          <span
            className={
              isActive ? 'text-accent-600' : 'text-slate-400 group-hover:text-slate-600'
            }
          >
            {icon}
          </span>
          <span>{children}</span>
        </>
      )}
    </NavLink>
  );
}