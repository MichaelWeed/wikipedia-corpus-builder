import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface DomainScreenProps {
  client: EngineClient;
}

export const DomainScreen: React.FC<DomainScreenProps> = ({ client }) => {
  const { domainDraft, projectDir, modelConfig, setDomainDraft, setDomainLockPath, setStep, addLog } = useWizardStore();
  const [loading, setLoading] = useState(false);

  const handleProposeFacets = async () => {
    if (!domainDraft.intent.trim()) return;
    setLoading(true);
    try {
      addLog(`Proposing facets for intent "${domainDraft.intent}"...`);
      const res = await client.proposeFacets(domainDraft.intent, modelConfig.provider || undefined);
      if (res && res.facets) {
        setDomainDraft({ facets: res.facets });
      }
      addLog(`Propose facets result: ${JSON.stringify(res)}`);
    } catch (err) {
      addLog(`Propose facets failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCompile = async () => {
    if (!projectDir.trim()) return;
    setLoading(true);
    try {
      addLog(`Compiling domain lock in ${projectDir}...`);
      const domainFile = `${projectDir}/domain.yaml`;
      const res = await client.compileDomain(domainFile, projectDir);
      const lockPath = `${projectDir}/domain.lock.json`;
      setDomainLockPath(lockPath);
      addLog(`Domain compiled successfully (${JSON.stringify(res)}). Lock path: ${lockPath}`);
      setStep(5);
    } catch (err) {
      addLog(`Domain compile failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Domain Definition & Compiler</h2>
      <p style={{ color: "#666" }}>Specify natural language intent, root categories, and max traversal depth.</p>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Natural Language Intent:</label>
        <textarea
          rows={3}
          value={domainDraft.intent}
          placeholder="e.g. Video games, game design, and gaming history"
          onChange={(e) => setDomainDraft({ intent: e.target.value })}
          style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
        <button
          onClick={handleProposeFacets}
          disabled={loading || !domainDraft.intent.trim()}
          style={{ marginTop: "0.5rem", padding: "0.4rem 1rem", background: "#333", color: "#fff", border: "none", borderRadius: "4px" }}
        >
          Propose Facets with AI
        </button>
      </div>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Root Categories (comma-separated):</label>
        <input
          type="text"
          value={domainDraft.rootCategories.join(", ")}
          onChange={(e) => setDomainDraft({ rootCategories: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
          style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Traversal Max Depth:</label>
        <input
          type="number"
          min={1}
          max={20}
          value={domainDraft.depth}
          onChange={(e) => setDomainDraft({ depth: parseInt(e.target.value, 10) || 6 })}
          style={{ width: "100px", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2rem" }}>
        <button onClick={() => setStep(3)} style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}>
          {UX_COPY.wizard.btnBack}
        </button>

        <button
          onClick={handleCompile}
          disabled={loading || domainDraft.rootCategories.length === 0}
          style={{ padding: "0.5rem 1.5rem", background: "#28a745", color: "#fff", border: "none", borderRadius: "4px" }}
        >
          {UX_COPY.wizard.btnCompile}
        </button>
      </div>
    </div>
  );
};
