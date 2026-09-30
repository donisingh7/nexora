"use client";

import { FileUp, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { useToast } from "@/components/Toast";

const API_BASE = process.env.NEXT_PUBLIC_NEXORA_API ?? "http://localhost:8000/api/v1";

const STAGE_LABELS: Record<string, string> = {
  parsing: "Parsing",
  chunking: "Chunking",
  embedding: "Embedding",
  indexing: "Indexing",
};

type DocumentItem = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: "queued" | "processing" | "completed" | "failed";
  created_at: string | null;
  ingestion_error: string | null;
  ingestion_stage: string | null;
};

type Workspace = { id: string; name: string };

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1_000_000) return `${Math.max(1, Math.round(bytes / 1000))} KB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

function statusLabel(document: DocumentItem): string {
  if (document.status === "processing" && document.ingestion_stage) {
    return STAGE_LABELS[document.ingestion_stage] ?? document.status;
  }
  return document.status;
}

function SkeletonRow() {
  return (
    <div className="document-row skeleton-row" aria-hidden="true">
      <div className="skeleton skeleton-block" />
      <div className="document-main">
        <div className="skeleton skeleton-line" style={{ width: "58%" }} />
        <div className="skeleton skeleton-line" style={{ width: "34%" }} />
      </div>
      <div className="skeleton skeleton-pill" />
    </div>
  );
}

export function DocumentLibrary() {
  const { notify } = useToast();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const refreshDocuments = useCallback(async (workspaceId: string) => {
    const response = await fetch(
      `${API_BASE}/documents?workspace_id=${encodeURIComponent(workspaceId)}`,
      { cache: "no-store" },
    );
    if (!response.ok) throw new Error(await responseError(response));
    setDocuments((await response.json()) as DocumentItem[]);
  }, []);

  useEffect(() => {
    let active = true;
    let interval: ReturnType<typeof setInterval> | undefined;

    async function initialize() {
      try {
        const response = await fetch(`${API_BASE}/workspaces/development`, { cache: "no-store" });
        if (!response.ok) throw new Error(await responseError(response));
        const currentWorkspace = (await response.json()) as Workspace;
        if (!active) return;
        setWorkspace(currentWorkspace);
        await refreshDocuments(currentWorkspace.id);
        interval = setInterval(() => {
          void refreshDocuments(currentWorkspace.id).catch((reason: unknown) => {
            if (active) setError(reason instanceof Error ? reason.message : "Unable to refresh documents.");
          });
        }, 2500);
      } catch (reason) {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Unable to connect to the Nexora API.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void initialize();
    return () => {
      active = false;
      if (interval) clearInterval(interval);
    };
  }, [refreshDocuments]);

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || uploading) return;
    const fileName = selectedFile.name;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", selectedFile);
      const response = await fetch(`${API_BASE}/documents`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await responseError(response));
      setSelectedFile(null);
      event.currentTarget.reset();
      if (workspace) await refreshDocuments(workspace.id);
      notify("success", `"${fileName}" queued for processing.`);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Upload failed.";
      setError(message);
      notify("error", message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="library-workflow">
      <form className="upload-panel" onSubmit={uploadDocument}>
        <div className="upload-panel-copy">
          <div className="upload-icon"><FileUp size={20} aria-hidden="true" /></div>
          <div>
            <h2>Add a document</h2>
            <p>PDF, DOCX, TXT, or Markdown. Maximum size is configured by the API.</p>
          </div>
        </div>
        <div className="upload-controls">
          <label className="file-picker">
            <span>{selectedFile?.name ?? "Choose a file"}</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button className="primary-button" type="submit" disabled={!selectedFile || uploading}>
            {uploading ? <LoaderCircle size={16} className="spin" /> : <FileUp size={16} />}
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </div>
        <p className="upload-hint">
          {selectedFile
            ? `Selected: ${selectedFile.name} (${formatBytes(selectedFile.size)}). Files are stored locally and indexed by the ingestion worker.`
            : "Files are stored locally and indexed by the ingestion worker."}
        </p>
      </form>

      <section className="document-list" aria-labelledby="document-list-title">
        <div className="list-heading">
          <div>
            <p className="eyebrow">WORKSPACE FILES <span className="eyebrow-rule" /></p>
            <h2 id="document-list-title">Documents</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            title="Refresh document status"
            aria-label="Refresh document status"
            onClick={() => workspace && void refreshDocuments(workspace.id).catch((reason: unknown) => setError(String(reason)))}
          >
            <RefreshCw size={16} />
          </button>
        </div>
        {error && <div className="inline-error" role="alert"><TriangleAlert size={16} />{error}</div>}
        {loading ? (
          <div className="document-rows" aria-label="Loading documents">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        ) : documents.length === 0 ? (
          <div className="list-empty">
            <span className="empty-line" />
            No documents yet — upload one above to get started
            <span className="empty-line" />
          </div>
        ) : (
          <div className="document-rows">
            {documents.map((document) => (
              <article className="document-row" key={document.id}>
                <div className="document-type">{document.filename.split(".").pop()?.toUpperCase().slice(0, 4)}</div>
                <div className="document-main">
                  <h3>{document.filename}</h3>
                  <p>{formatBytes(document.size_bytes)} <span>·</span> {document.mime_type}</p>
                  {document.ingestion_error && <p className="document-error">{document.ingestion_error}</p>}
                </div>
                <span className={`status-pill status-${document.status}`}>
                  {document.status === "processing" && <LoaderCircle size={12} className="spin" />}
                  {statusLabel(document)}
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
