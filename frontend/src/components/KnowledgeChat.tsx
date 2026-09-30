"use client";

import { ArrowUpRight, AudioLines, LoaderCircle, Quote, Search, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { useToast } from "@/components/Toast";

const API_BASE = process.env.NEXT_PUBLIC_NEXORA_API ?? "http://localhost:8000/api/v1";

type Citation = {
  citation_id: string;
  document_id: string;
  filename: string;
  chunk_id: string;
  page_number: number | null;
  location: Record<string, unknown>;
  excerpt: string;
  relevance_score: number;
  dense_score?: number | null;
  lexical_score?: number | null;
};

type RetrievedChunk = Citation & { text: string; fused_score?: number | null };
type Workspace = { id: string; name: string };
type Mode = "retrieve" | "answer";

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

export function KnowledgeChat() {
  const { notify } = useToast();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [mode, setMode] = useState<Mode>("retrieve");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [retrieved, setRetrieved] = useState<RetrievedChunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/workspaces/development`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(await responseError(response));
        return (await response.json()) as Workspace;
      })
      .then((value) => { if (active) setWorkspace(value); })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to connect to the API.");
      });
    return () => { active = false; };
  }, []);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || !workspace || loading) return;
    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);
    setRetrieved([]);
    try {
      const endpoint = mode === "retrieve" ? "retrieve" : "answer";
      const response = await fetch(`${API_BASE}/query/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: workspace.id, query: question.trim(), top_k: 8 }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      if (mode === "retrieve") {
        setRetrieved(result.results as RetrievedChunk[]);
      } else {
        setAnswer(result.answer as string);
        setCitations(result.citations as Citation[]);
      }
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "The query could not be completed.";
      setError(message);
      notify("error", message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="knowledge-workflow">
      <section className="chat-workspace" aria-label="Ask about indexed workspace documents">
        <div className="chat-symbol"><AudioLines size={22} strokeWidth={1.6} /></div>
        <p className="eyebrow">NEXORA ASSISTANT <span className="eyebrow-rule" /></p>
        <h2>Ask a question. Follow it to the source.</h2>
        <p className="chat-explainer">
          {mode === "retrieve"
            ? "Inspect the hybrid retrieval results without configuring a generation provider."
            : "Answers are based on retrieved document excerpts and include source citations."}
        </p>
        <p className="chat-hint-link">
          New here? <Link href="/library">Upload a document</Link> first, then come back and ask about it.
        </p>
        <div className="mode-switch" role="group" aria-label="Query mode">
          <button type="button" className={mode === "retrieve" ? "mode-active" : ""} onClick={() => setMode("retrieve")}>
            <Search size={15} /> Retrieval only
          </button>
          <button type="button" className={mode === "answer" ? "mode-active" : ""} onClick={() => setMode("answer")}>
            <AudioLines size={15} /> Grounded answer
          </button>
        </div>
        <form className="question-form" onSubmit={submitQuestion}>
          <label className="sr-only" htmlFor="knowledge-question">Your question</label>
          <textarea
            id="knowledge-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask about your indexed documents…"
            rows={3}
            maxLength={4000}
            required
          />
          <div className="question-form-bottom">
            <span>{workspace ? workspace.name : "Connecting to development workspace…"}</span>
            <button className="primary-button" type="submit" disabled={!question.trim() || !workspace || loading}>
              {loading ? <LoaderCircle size={16} className="spin" /> : <ArrowUpRight size={16} />}
              {loading ? "Searching" : mode === "retrieve" ? "Retrieve sources" : "Ask Nexora"}
            </button>
          </div>
        </form>
        {error && (
          <div className="inline-error chat-error" role="alert">
            <TriangleAlert size={16} />
            <span>{error}{mode === "answer" && " Retrieval-only mode works without an LLM key."}</span>
          </div>
        )}
        {answer && (
          <section className="answer-panel" aria-labelledby="answer-title">
            <p className="eyebrow">GROUNDED RESPONSE <span className="eyebrow-rule" /></p>
            <h3 id="answer-title">Answer</h3>
            <p className="answer-text">{answer}</p>
            <SourceList citations={citations} />
          </section>
        )}
        {retrieved.length > 0 && (
          <section className="answer-panel retrieved-panel" aria-labelledby="retrieved-title">
            <p className="eyebrow">HYBRID RESULTS <span className="eyebrow-rule" /></p>
            <h3 id="retrieved-title">Retrieved passages <span className="result-count">{retrieved.length}</span></h3>
            <div className="source-list">
              {retrieved.map((source) => <SourceCard key={source.chunk_id} source={source} />)}
            </div>
          </section>
        )}
        {!answer && retrieved.length === 0 && !loading && !error && (
          <div className="chat-empty-hint"><Quote size={15} /> Sources and citations will appear here after a query.</div>
        )}
      </section>
    </div>
  );
}

function SourceList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return <p className="no-citations">No matching source excerpts were retrieved.</p>;
  return <div className="source-list">{citations.map((source) => <SourceCard key={source.chunk_id} source={source} />)}</div>;
}

function SourceCard({ source }: { source: Citation | RetrievedChunk }) {
  const reference = source.page_number ? `Page ${source.page_number}` : "Document excerpt";
  const fusedScore = "fused_score" in source ? source.fused_score : null;
  const location = Object.entries(source.location ?? {})
    .filter(([key]) => key !== "char_start" && key !== "char_end")
    .map(([key, value]) => `${key.replaceAll("_", " ")} ${String(value)}`)
    .join(" · ");
  return (
    <article className="source-card">
      <div className="source-heading">
        <span className="source-label">{source.citation_id}</span>
        <div className="source-file"><h4>{source.filename}</h4><p>{reference}{location && ` · ${location}`}</p></div>
        {fusedScore != null && <span className="source-score">RRF {fusedScore.toFixed(4)}</span>}
      </div>
      <p className="source-excerpt">{source.excerpt}</p>
      <div className="source-components">
        {source.dense_score != null && <span>Dense {source.dense_score.toFixed(3)}</span>}
        {source.lexical_score != null && <span>BM25 {source.lexical_score.toFixed(3)}</span>}
      </div>
    </article>
  );
}
