import { useMemo } from "react";
import { UX_COPY } from "./copy";
import { EngineClient } from "./engine/client";
import { useWizardStore } from "./store/wizardStore";

import { ProjectScreen } from "./wizard/ProjectScreen";
import { SourceScreen } from "./wizard/SourceScreen";
import { ModelScreen } from "./wizard/ModelScreen";
import { DomainScreen } from "./wizard/DomainScreen";
import { PreviewScreen } from "./wizard/PreviewScreen";
import { BuildScreen } from "./wizard/BuildScreen";
import { ExportScreen } from "./wizard/ExportScreen";
import { PurgeScreen } from "./wizard/PurgeScreen";
import { LogViewer } from "./wizard/LogViewer";

export default function App() {
  const { step, setStep } = useWizardStore();

  const client = useMemo(() => {
    return new EngineClient(async (method, params) => {
      if (typeof window !== "undefined" && (window as any).__TAURI_INTERNALS__) {
        try {
          const { invoke } = await import("@tauri-apps/api/core");
          return await invoke("engine_call", { method, params });
        } catch (e) {
          console.warn("Tauri invoke failed, falling back to mock", e);
        }
      }
      return { status: "mocked", method, params };
    });
  }, []);

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: "900px", margin: "0 auto", color: "#333" }}>
      <header style={{ borderBottom: "1px solid #ddd", paddingBottom: "1rem", marginBottom: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "1.6rem" }}>{UX_COPY.appTitle}</h1>
          <p style={{ margin: "0.2rem 0 0 0", color: "#666", fontSize: "0.9rem" }}>{UX_COPY.tagline}</p>
        </div>
        <span style={{ fontSize: "0.85rem", color: "#28a745", background: "#eef9f1", padding: "0.3rem 0.6rem", borderRadius: "12px", border: "1px solid #c3e6cb" }}>
          {UX_COPY.status.connected}
        </span>
      </header>

      <nav style={{ display: "flex", gap: "0.4rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        {[
          { id: 1, label: UX_COPY.wizard.stepProject },
          { id: 2, label: UX_COPY.wizard.stepSource },
          { id: 3, label: UX_COPY.wizard.stepModel },
          { id: 4, label: UX_COPY.wizard.stepDomain },
          { id: 5, label: "5. Preview" },
          { id: 6, label: UX_COPY.wizard.stepBuild },
          { id: 7, label: "7. Export" },
          { id: 8, label: "8. Purge" },
        ].map((s) => (
          <button
            key={s.id}
            onClick={() => setStep(s.id)}
            style={{
              padding: "0.4rem 0.8rem",
              borderRadius: "4px",
              border: "1px solid #ccc",
              background: step === s.id ? "#0066cc" : "#fff",
              color: step === s.id ? "#fff" : "#333",
              fontWeight: step === s.id ? "bold" : "normal",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <main style={{ background: "#fdfdfd", padding: "1.5rem", borderRadius: "8px", border: "1px solid #e2e2e2", boxShadow: "0 2px 4px rgba(0,0,0,0.03)" }}>
        {step === 1 && <ProjectScreen />}
        {step === 2 && <SourceScreen client={client} />}
        {step === 3 && <ModelScreen client={client} />}
        {step === 4 && <DomainScreen client={client} />}
        {step === 5 && <PreviewScreen client={client} />}
        {step === 6 && <BuildScreen client={client} />}
        {step === 7 && <ExportScreen client={client} />}
        {step === 8 && <PurgeScreen client={client} />}
      </main>

      <LogViewer />
    </div>
  );
}
