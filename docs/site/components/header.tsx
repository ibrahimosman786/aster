import type { NavGroup } from "@/lib/docs";
import { siteConfig } from "@/lib/site";
import { GitHubIcon } from "./github-icon";
import { HeaderNav } from "./header-nav";
import { Logo } from "./logo";
import { MobileNav } from "./mobile-nav";
import { Search } from "./search";
import { ThemeToggle } from "./theme-toggle";

type SearchDocument = { slug: string; title: string; description: string; text: string };

// Two rows: identity, search and the repository, then the section tabs; under 640px the tabs live in the drawer.
export function Header({ documents, navigation }: { documents: SearchDocument[]; navigation: NavGroup[] }) {
  return (
    <header className="site-header">
      <div className="header-row">
        <div className="header-brand">
          <Logo />
        </div>
        <div className="header-search"><Search documents={documents} /></div>
        <nav className="header-actions" aria-label="Global navigation">
          <a className="repo-link" href={siteConfig.repository} target="_blank" rel="noreferrer" aria-label={`${siteConfig.repoName} on GitHub`}>
            <GitHubIcon size={17} />
            <span className="repo-name">{siteConfig.repoName}</span>
          </a>
          <ThemeToggle />
          <MobileNav navigation={navigation} />
        </nav>
      </div>
      <HeaderNav navigation={navigation} />
    </header>
  );
}
