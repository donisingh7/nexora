import { ArrowRight, Braces, FileSearch, FileUp, Layers3, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";

const steps = [
  {
    icon: FileUp,
    title: "1. Upload",
    detail: "Add a PDF, DOCX, TXT, or Markdown file — validated, sanitized, and stored.",
    status: "Working",
  },
  {
    icon: Layers3,
    title: "2. Index",
    detail: "Parsed, chunked, and embedded for hybrid dense + BM25 search.",
    status: "Working",
  },
  {
    icon: FileSearch,
    title: "3. Ask",
    detail: "Hybrid retrieval with RRF fusion finds the most relevant passages.",
    status: "No LLM key needed",
  },
  {
    icon: ShieldCheck,
    title: "4. Verify",
    detail: "Every answer cites the exact source excerpt it's grounded in.",
    status: "Citations always included",
  },
];

export default function Home() {
  return (
    <AppShell activeSection="overview">
      <section className="overview-hero">
        <div className="hero-copy">
          <div className="eyebrow">ENTERPRISE KNOWLEDGE INTELLIGENCE <span className="eyebrow-rule" /></div>
          <h1>Upload. Index. Ask. Verify the citation.</h1>
          <p>Nexora connects organizational knowledge to useful, traceable answers via hybrid retrieval and grounded generation.</p>
          <div className="hero-note"><span className="status-indicator" /> Implemented locally · hybrid RAG with citations</div>
          <div className="hero-cta">
            <Link href="/library" className="primary-button">
              <FileUp size={16} /> Upload your first document
            </Link>
            <Link href="/chat" className="text-link">Or try Knowledge Chat <ArrowRight size={14} /></Link>
          </div>
        </div>
        <div className="hero-visual" aria-label="Knowledge workflow: upload, index, ask, verify">
          <div className="visual-topline"><span>KNOWLEDGE FLOW</span><span className="planned-label"><span className="planned-dot" /> IMPLEMENTED</span></div>
          <div className="flow-step"><span className="flow-number">01</span><span className="flow-name">Upload</span><span className="flow-state">Documents</span></div>
          <div className="flow-connector" />
          <div className="flow-step"><span className="flow-number">02</span><span className="flow-name">Index</span><span className="flow-state">Searchable knowledge</span></div>
          <div className="flow-connector" />
          <div className="flow-step"><span className="flow-number">03</span><span className="flow-name">Ask</span><span className="flow-state">Relevant passages</span></div>
          <div className="flow-connector" />
          <div className="flow-step"><span className="flow-number">04</span><span className="flow-name">Verify</span><span className="flow-state">Cited answers</span></div>
          <div className="visual-foot"><Braces size={15} /> Provider-neutral foundation</div>
        </div>
      </section>

      <section className="foundation-section" aria-labelledby="foundation-title">
        <div className="section-heading">
          <div><div className="eyebrow">HOW NEXORA WORKS <span className="eyebrow-rule" /></div><h2 id="foundation-title">Upload → Index → Ask → Verify citations</h2></div>
          <span className="section-index">01 / 04</span>
        </div>
        <div className="foundation-list">
          {steps.map(({ icon: Icon, title, detail, status }, index) => (
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
