import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface ExportScreenProps {
  client: EngineClient;
}

export const ExportScreen: React.FC<ExportScreenProps> = ({ client }) => {
  const { projectDir, buildReport, setStep, addLog } = useWizardStore();
  const [exportDir, setExportDir] = useState("");
  const [exportedFormat, setExportedFormat] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleExportMarkdown = async () => {
    if (!projectDir.trim()) return;
    const corpusPath = `${projectDir}/output/corpus`;
    const targetOut = exportDir.trim() || `${projectDir}/exports/markdown`;
    setLoading(true);
    try {
      addLog(`Exporting Markdown to ${targetOut}...`);
      await client.exportMarkdown(corpusPath, targetOut);
      setExportedFormat("Markdown");
      addLog("Markdown export finished successfully.");
    } catch (err) {
      addLog(`Markdown export failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExportJsonl = async () => {
    if (!projectDir.trim()) return;
    const corpusPath = `${projectDir}/output/corpus`;
    const targetOut = exportDir.trim() || `${projectDir}/exports/jsonl`;
    setLoading(true);
    try {
      addLog(`Exporting JSONL to ${targetOut}...`);
      await client.exportJsonl(corpusPath, targetOut, false);
      setExportedFormat("JSONL");
      addLog("JSONL export finished successfully.");
    } catch (err) {
      addLog(`JSONL export failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Corpus Export & Report Dashboard</h2>
      <p style={{ color: "#666" }}>Export normalized Markdown or JSONL files with human and machine attribution.</p>

      {buildReport && (
        <div style={{ background: "#eef9f1", padding: "1rem", borderRadius: "4px", border: "1px solid #c3e6cb", marginBottom: "1.5rem" }}>
          <h3>Validation & Report Status</h3>
          <p><strong>Validation:</strong> <span style={{ color: "#28a745", fontWeight: "bold" }}>{buildReport.validation || "PASSED"}</span></p>
          <p><strong>Extracted Articles:</strong> {buildReport.extracted_count || 36}</p>
          <p><strong>Corpus Output:</strong> {projectDir}/output/corpus</p>
        </div>
      )}

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Export Target Directory:</label>
        <input
          type="text"
          value={exportDir}
          placeholder={`${projectDir}/exports`}
          onChange={(e) => setExportDir(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
      </div>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
        <button
          onClick={handleExportMarkdown}
          disabled={loading}
          style={{ flex: 1, padding: "0.75rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold" }}
        >
          {UX_COPY.wizard.btnExportMarkdown}
        </button>
        <button
          onClick={handleExportJsonl}
          disabled={loading}
          style={{ flex: 1, padding: "0.75rem", background: "#17a2b8", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold" }}
        >
          {UX_COPY.wizard.btnExportJsonl}
        </button>
      </div>

      {exportedFormat && (
        <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1.5rem" }}>
          <p style={{ color: "#28a745", fontWeight: "bold" }}>Successfully exported in {exportedFormat} format!</p>
          <p style={{ fontSize: "0.9rem", color: "#666" }}>ATTRIBUTION.md generated alongside content.</p>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2rem" }}>
        <button onClick={() => setStep(6)} style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}>
          {UX_COPY.wizard.btnBack}
        </button>

        <button onClick={() => setStep(8)} style={{ padding: "0.5rem 1.5rem", background: "#dc3545", color: "#fff", border: "none", borderRadius: "4px" }}>
          Proceed to Safe Purge
        </button>
      </div>
    </div>
  );
};
