import { AppShell } from "@/components/AppShell";
import { DocumentLibrary } from "@/components/DocumentLibrary";

export default function LibraryPage() {
  return (
    <AppShell activeSection="library">
      <section className="page-heading">
        <div className="eyebrow">KNOWLEDGE BASE <span className="eyebrow-rule" /></div>
        <div className="heading-row">
          <div>
            <h1>Document library</h1>
            <p className="page-lede">Upload source material and follow its indexing status.</p>
          </div>
        </div>
      </section>
      <DocumentLibrary />
    </AppShell>
  );
}
