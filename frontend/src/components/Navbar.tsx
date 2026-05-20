import { BookmarkPlus, Film, FlaskConical, Home, Search, UserCircle2 } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Home", icon: Home },
  { to: "/discover", label: "Discover", icon: Search },
  { to: "/profile", label: "My Profile", icon: UserCircle2 },
  { to: "/watchlist", label: "Watchlist", icon: BookmarkPlus },
  { to: "/similar", label: "Similar Movies", icon: Film },
  { to: "/algorithm-lab", label: "Algorithm Lab", icon: FlaskConical },
  { to: "/evaluation", label: "Evaluation", icon: Film }
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-ink/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 md:px-8">
        <NavLink to="/" className="text-xl font-semibold tracking-wide text-neon">
          MovieMate
        </NavLink>
        <nav className="hidden gap-2 md:flex">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `rounded-full px-4 py-2 text-sm transition ${
                  isActive ? "bg-neon/20 text-neon" : "text-slate-300 hover:bg-white/10 hover:text-white"
                }`
              }
            >
              <span className="flex items-center gap-2">
                <Icon size={14} />
                {label}
              </span>
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
