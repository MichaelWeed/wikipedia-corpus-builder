import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface PreviewScreenProps {
  client: EngineClient;
}

export const PreviewScreen: React.FC<PreviewScreenProps> = ({ client }) => {
  const { domainLockPath, projectDir, setStep, addLog } = useWizardStore();
  const [searchTitle, setSearchTitle] = useState("");
  const [explainResult, setExplainResult] = useState<any>(null);
  const [ackWarnings, setAckWarnings] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleExplain = async () => {
    if (!searchTitle.trim() || !projectDir.trim()) return;
    setLoading(true);
    try {
      addLog(`Explaining provenance for article "${searchTitle}"...`);
      const res = await client.explainDomain(domainLockPath, projectDir, searchTitle);
      setExplainResult(res);
      addLog(`Explain provenance result: ${JSON.stringify(res)}`);
    } catch (err) {
      addLog(`Explain failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Domain Preview & Provenance Audit</h2>
      <p style={{ color: "#666" }}>Audit compilation metrics, category breakdown, and explain page selection provenance.</p>

      <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1.5rem" }}>
        <h3>Selection Metrics</h3>
        <p><strong>Selected Pages:</strong> 36 articles</p>
        <p><strong>Estimated Raw Size:</strong> ~120 KB</p>
        <p><strong>Roots Resolved:</strong> 1 category root</p>
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <h3>Why Included? Search Box</h3>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={searchTitle}
            placeholder="e.g. Super_Mario_Bros"
            onChange={(e) => setSearchTitle(e.target.value)}
            style={{ flex: 1, padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
          />
          <button onClick={handleExplain} disabled={loading || !searchTitle.trim()} style={{ padding: "0.5rem 1rem", background: "#333", color: "#fff", border: "none", borderRadius: "4px" }}>
            Search Provenance
          </button>
        </div>

        {explainResult && (
          <div style={{ background: "#f8f9fa", padding: "1rem", borderRadius: "4px", marginTop: "0.5rem", border: "1px solid #eee" }}>
            <p><strong>Title:</strong> {explainResult.title}</p>
            <p><strong>Selected:</strong> {explainResult.selected ? "YES" : "NO"}</p>
            {explainResult.provenance_chain && (
              <p><strong>Path:</strong> {explainResult.provenance_chain.join(" -> ")}</p>
            )}
          </div>
        )}
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={ackWarnings}
            onChange={(e) => setAckWarnings(e.target.checked)}
          />
          <span>I acknowledge domain compilation coverage and preview warnings</span>
        </label>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2rem" }}>
        <button onClick={() => setStep(4)} style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}>
          {UX_COPY.wizard.btnBack}
        </button>

        <button
          disabled={!ackWarnings}
          onClick={() => setStep(6)}
          style={{ padding: "0.5rem 1.5rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px" }}
        >
          {UX_COPY.wizard.btnNext}
        </button>
      </div>
    </div>
  );
};
