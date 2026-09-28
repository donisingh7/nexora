import Link from "next/link";
import type { ReactNode } from "react";
import { BookOpen, Compass, MessageSquareText, Sparkles } from "lucide-react";

const navigation = [
  { href: "/", label: "Overview", icon: Compass, section: "overview" },
  { href: "/library", label: "Library", icon: BookOpen, section: "library" },
  { href: "/chat", label: "Knowledge chat", icon: MessageSquareText, section: "chat" },
] as const;

type Section = (typeof navigation)[number]["section"];

export function AppShell({ children, activeSection }: { children: ReactNode; activeSection: Section }) {
  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="Nexora overview">
          <span className="brand-mark">N</span>
          <span className="brand-name">nexora<span>.</span></span>
        </Link>

        <div className="workspace-label">WORKSPACE</div>
        <div className="workspace-name"><span className="workspace-dot" /> Knowledge space</div>

        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ href, label, icon: Icon, section }) => (
            <Link
              key={section}
              href={href}
              className={`nav-link${activeSection === section ? " nav-link-active" : ""}`}
              aria-current={activeSection === section ? "page" : undefined}
            >
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>{label}</span>
            </Link>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="foundation-mark"><Sparkles size={15} aria-hidden="true" /> Functional foundation</div>
          <div className="sidebar-caption">Upload, retrieval, and grounded answers work end-to-end locally.</div>
        </div>
      </aside>

      <div className="workspace-main">
        <header className="topbar">
          <div className="breadcrumb"><span>Knowledge space</span><span className="breadcrumb-slash">/</span><strong>{navigation.find((item) => item.section === activeSection)?.label}</strong></div>
          <div className="topbar-status"><span className="status-indicator" /> Local development mode</div>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
