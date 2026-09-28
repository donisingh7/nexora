"use client";

import { FileUp, LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_NEXORA_API ?? "http://localhost:8000/api/v1";

type DocumentItem = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: "queued" | "processing" | "completed" | "failed";
  created_at: string | null;
  ingestion_error: string | null;
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

export function DocumentLibrary() {
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
    if (!selectedFile) return;
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
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
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
            {uploading ? "Uploading" : "Upload"}
          </button>
        </div>
        <p className="upload-hint">Files are stored locally and indexed by the development worker.</p>
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
          <div className="list-message"><LoaderCircle size={17} className="spin" /> Loading workspace documents…</div>
        ) : documents.length === 0 ? (
          <div className="list-empty"><span className="empty-line" />No documents yet<span className="empty-line" /></div>
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
                  {document.status}
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
