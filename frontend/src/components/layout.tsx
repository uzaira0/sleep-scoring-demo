import { Outlet, Link, useLocation } from "react-router-dom";
import { Settings, Database, Activity, Download, LogOut, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme-provider";
import { useSleepScoringStore } from "@/store";
import { cn } from "@/lib/utils";

/**
 * Main application layout with sidebar navigation
 */
export function Layout() {
  const location = useLocation();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const user = useSleepScoringStore((state) => state.user);
  const clearAuth = useSleepScoringStore((state) => state.clearAuth);

  const cycleTheme = () => {
    if (theme === "light") {
      setTheme("dark");
    } else if (theme === "dark") {
      setTheme("system");
    } else {
      setTheme("light");
    }
  };

  const navItems = [
    { path: "/settings/study", label: "Study Settings", icon: Settings },
    { path: "/settings/data", label: "Data Settings", icon: Database },
    { path: "/scoring", label: "Scoring", icon: Activity },
    { path: "/export", label: "Export", icon: Download },
  ];

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-card flex flex-col">
        {/* Logo/Title */}
        <div className="h-14 border-b border-border flex items-center px-4">
          <Activity className="h-6 w-6 text-primary mr-2" />
          <span className="font-semibold text-lg">Sleep Scoring</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-border space-y-3">
          {/* User info */}
          <div className="text-sm text-muted-foreground">
            Signed in as{" "}
            <span className="font-medium text-foreground">
              {user?.username ?? "User"}
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={cycleTheme}
              title={`Theme: ${theme} (${resolvedTheme})`}
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAuth}
              className="flex items-center gap-2"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
