import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { LoopDiagram } from "@/components/home/loop-diagram";
import { NewsTicker } from "@/components/home/news-ticker";
import { GitHubIcon } from "@/components/github-icon";
import { news } from "@/lib/news";
import { siteConfig } from "@/lib/site";

export const metadata: Metadata = {
  title: { absolute: siteConfig.title },
  description: siteConfig.description,
  alternates: { canonical: "/" },
  openGraph: { title: siteConfig.title, description: siteConfig.description, url: "/" },
};

const recipeGroups = [
  {
    title: "Model weights",
    note: "GPU · Slime and SGLang",
    recipes: [
      { name: "SAO", href: "/docs/user-guide/recipes/sao", signal: "learns from a single rollout" },
      { name: "OpenClaw-RL", href: "/docs/user-guide/recipes/openclawrl", signal: "learns from personalized chat" },
      { name: "TTT-Discover", href: "/docs/user-guide/recipes/tttd", signal: "trains at test time" },
      { name: "Guidance-TTT", href: `${siteConfig.repository}/tree/main/recipes/tttd/examples/guidance_ttt`, signal: "guides a program search" },
    ],
  },
  {
    title: "Agent harness",
    note: "no GPU · any model endpoint",
    recipes: [
      { name: "GEPA", href: "/docs/user-guide/recipes/gepa", signal: "reflective prompt evolution" },
      { name: "Meta-Harness", href: `${siteConfig.repository}/tree/main/recipes/meta_harness`, signal: "searches full harness designs" },
    ],
  },
];

export default function Home() {
  const ticker = [...news].sort((a, b) => b.date.localeCompare(a.date));

  return (
    <main className="home">
      <NewsTicker items={ticker} />

      <section className="home-hero">
        <div>
          <p className="pill">Open source · Apache-2.0</p>
          <h1>Infrastructure for continually <em>self‑improving</em> agents</h1>
          <p className="lead">The first <strong>inference-native</strong> infrastructure for agents to learn from <strong>live traffic</strong> and continually update their <strong>weights and harness</strong>.</p>
          <div className="home-actions">
            <Link className="primary-action" href="/docs/getting-started/quickstart">Quickstart <ArrowRight size={16} /></Link>
            <Link className="secondary-action" href="/company">The company</Link>
            <a className="secondary-action" href={siteConfig.repository} target="_blank" rel="noreferrer">
              <GitHubIcon size={16} /> GitHub
            </a>
          </div>
        </div>
      </section>
      <section className="hero-stage" aria-label="How Aster improves an agent">
        <LoopDiagram />
      </section>

      <section className="band">
        <div className="home-section quick-start">
          <div>
            <p className="section-label">Quickstart</p>
            <h2>Start a local stack</h2>
            <p>Start a stack, send a provider-native request, grade the receipt Aster returns.</p>
            <div className="home-actions">
              <Link className="primary-action" href="/docs/getting-started/quickstart">Open the quickstart <ArrowRight size={16} /></Link>
            </div>
          </div>
          <pre className="terminal"><code>{`export ASTER_TOKEN="$(openssl rand -hex 16)"
aster serve -c recipes/basic/local-sglang.yaml

curl http://localhost:8900/healthz`}</code></pre>
          <div className="recipe-strip" aria-label="Bundled recipes">
            {recipeGroups.map((group) => (
              <div className="recipe-row" key={group.title}>
                <div className="recipe-row-label">
                  <strong>{group.title}</strong>
                  <span>{group.note}</span>
                </div>
                <ul>
                  {group.recipes.map((recipe) => (
                    <li key={recipe.name}>
                      {recipe.href.startsWith("http") ? (
                        <a href={recipe.href} title={recipe.signal} target="_blank" rel="noreferrer">
                          <strong>{recipe.name}</strong>
                          <span>{recipe.signal}</span>
                        </a>
                      ) : (
                        <Link href={recipe.href} title={recipe.signal}>
                          <strong>{recipe.name}</strong>
                          <span>{recipe.signal}</span>
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <Link className="text-link recipe-strip-link" href="/docs/user-guide/recipes">Compare them all <ArrowRight size={15} /></Link>
          </div>
        </div>
      </section>

      <footer className="site-footer">
        <div>ibrahimosman786/aster · Apache-2.0</div>
        <nav aria-label="Project links">
          <a href={siteConfig.repository} target="_blank" rel="noreferrer">GitHub</a>
          <a href="/slides/" target="_blank" rel="noreferrer">Slides</a>
          <Link href="/docs/getting-started/intro">Docs</Link>
        </nav>
      </footer>
    </main>
  );
}
