import { AppShell } from "@/components/AppShell";
import { KnowledgeChat } from "@/components/KnowledgeChat";

export default function ChatPage() {
  return (
    <AppShell activeSection="chat">
      <section className="page-heading">
        <div className="eyebrow">GROUNDED ANSWERS <span className="eyebrow-rule" /></div>
        <div className="heading-row">
          <div>
            <h1>Knowledge chat</h1>
            <p className="page-lede">Search indexed workspace material and inspect its sources.</p>
          </div>
        </div>
      </section>
      <KnowledgeChat />
    </AppShell>
  );
}
