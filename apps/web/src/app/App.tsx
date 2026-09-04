import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

import { ControlsPage } from "../features/studio/ControlsPage";
import { CreativeHome } from "../features/studio/CreativeHome";
import { GalleryPage } from "../features/studio/GalleryPage";
import { SessionStudio } from "../features/studio/SessionStudio";

function normalizePath(pathname: string) {
  const normalized = pathname.replace(/\/+$/, "");
  return normalized || "/";
}

function usePathname() {
  const [pathname, setPathname] = useState(() => normalizePath(window.location.pathname));

  useEffect(() => {
    const handleNavigation = () => setPathname(normalizePath(window.location.pathname));
    window.addEventListener("popstate", handleNavigation);
    return () => window.removeEventListener("popstate", handleNavigation);
  }, []);

  function navigate(path: string) {
    const next = normalizePath(path);
    if (next === pathname) return;
    window.history.pushState({}, "", next);
    setPathname(next);
    window.scrollTo({ top: 0 });
  }

  return { pathname, navigate };
}

function AppLink({
  href,
  navigate,
  children,
  className,
}: {
  href: string;
  navigate: (path: string) => void;
  children: ReactNode;
  className?: string;
}) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) return;
    event.preventDefault();
    navigate(href);
  }

  return <a href={href} className={className} onClick={handleClick}>{children}</a>;
}

export function App() {
  const { pathname, navigate } = usePathname();
  const sessionMatch = pathname.match(/^\/sessions\/([^/]+)$/);

  return (
    <div className="creative-app-shell">
      <header className="creative-nav">
        <AppLink href="/" navigate={navigate} className="creative-brand">
          <span className="creative-brand-mark" aria-hidden="true">✦</span>
          <span>LearnToDraw</span>
        </AppLink>
        <nav aria-label="Main navigation">
          <AppLink href="/" navigate={navigate} className={pathname === "/" ? "active" : undefined}>Create</AppLink>
          <AppLink href="/gallery" navigate={navigate} className={pathname === "/gallery" ? "active" : undefined}>Gallery</AppLink>
          <AppLink href="/controls" navigate={navigate} className={pathname === "/controls" ? "active" : undefined}>Controls</AppLink>
        </nav>
      </header>

      {pathname === "/" ? <CreativeHome navigate={navigate} /> : null}
      {pathname === "/gallery" ? <GalleryPage /> : null}
      {pathname === "/controls" ? <ControlsPage /> : null}
      {sessionMatch ? <SessionStudio sessionId={decodeURIComponent(sessionMatch[1])} /> : null}
      {!sessionMatch && !["/", "/gallery", "/controls"].includes(pathname) ? (
        <main className="studio-loading">
          <h1>That page does not exist.</h1>
          <AppLink href="/" navigate={navigate} className="button-primary">Return home</AppLink>
        </main>
      ) : null}
    </div>
  );
}
