import { ArrowRight, Braces, FileSearch, Layers3, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";

const foundations = [
  { icon: Layers3, title: "Bring knowledge together", detail: "Upload PDF, DOCX, TXT, and Markdown files.", status: "Working" },
  { icon: FileSearch, title: "Find the useful detail", detail: "Hybrid dense and BM25 retrieval with RRF fusion.", status: "Working" },
  { icon: ShieldCheck, title: "Keep answers traceable", detail: "Answers cite the retrieved source excerpts.", status: "Needs LLM key" },
];

export default function Home() {
  return (
    <AppShell activeSection="overview">
      <section className="overview-hero">
        <div className="hero-copy">
          <div className="eyebrow">ENTERPRISE KNOWLEDGE INTELLIGENCE <span className="eyebrow-rule" /></div>
          <h1>Good knowledge deserves a clear path.</h1>
          <p>Nexora connects organizational knowledge to useful, traceable answers via hybrid retrieval and grounded generation.</p>
          <div className="hero-note"><span className="status-indicator" /> Implemented locally · hybrid RAG with citations</div>
        </div>
        <div className="hero-visual" aria-label="Knowledge workflow: collect, index, and ask">
          <div className="visual-topline"><span>KNOWLEDGE FLOW</span><span className="planned-label"><span className="planned-dot" /> IMPLEMENTED</span></div>
          <div className="flow-step"><span className="flow-number">01</span><span className="flow-name">Collect</span><span className="flow-state">Documents</span></div>
          <div className="flow-connector" />
          <div className="flow-step"><span className="flow-number">02</span><span className="flow-name">Index</span><span className="flow-state">Searchable knowledge</span></div>
          <div className="flow-connector" />
          <div className="flow-step"><span className="flow-number">03</span><span className="flow-name">Ask</span><span className="flow-state">Cited answers</span></div>
          <div className="visual-foot"><Braces size={15} /> Provider-neutral foundation</div>
        </div>
      </section>

      <section className="foundation-section" aria-labelledby="foundation-title">
        <div className="section-heading">
          <div><div className="eyebrow">BUILDING BLOCKS <span className="eyebrow-rule" /></div><h2 id="foundation-title">Designed for grounded knowledge work</h2></div>
          <span className="section-index">01 / 03</span>
        </div>
        <div className="foundation-list">
          {foundations.map(({ icon: Icon, title, detail, status }, index) => (
            <article className="foundation-row" key={title}>
              <span className="foundation-index">0{index + 1}</span>
              <span className="foundation-icon"><Icon size={19} strokeWidth={1.7} /></span>
              <div className="foundation-row-copy"><h3>{title}</h3><p>{detail}</p></div>
              <span className="row-status">{status}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="next-steps" aria-label="Explore the workspace">
        <div><span className="eyebrow">EXPLORE THE WORKSPACE <span className="eyebrow-rule" /></span><p>Upload documents, then search them with hybrid retrieval.</p></div>
        <div className="next-links"><Link href="/library">Document library <ArrowRight size={16} /></Link><Link href="/chat">Knowledge chat <ArrowRight size={16} /></Link></div>
      </section>
    </AppShell>
  );
}
