import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface SourceScreenProps {
  client: EngineClient;
}

export const SourceScreen: React.FC<SourceScreenProps> = ({ client }) => {
  const { sourcePath, projectDir, sourceInspection, metadataBuilt, setSourceInfo, setMetadataBuilt, setStep, addLog } =
    useWizardStore();

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleInspect = async () => {
    if (!sourcePath.trim()) return;
    setLoading(true);
    setErrorMsg("");
    try {
      addLog(`Inspecting source dump at ${sourcePath}...`);
      const res = await client.inspectSource(sourcePath);
      setSourceInfo(sourcePath, res);
      addLog(`Source inspection successful: ${JSON.stringify(res)}`);
    } catch (err: any) {
      setErrorMsg(err?.message || String(err));
      addLog(`Source inspection failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleBuildMetadata = async () => {
    if (!sourcePath.trim() || !projectDir.trim()) return;
    setLoading(true);
    setErrorMsg("");
    try {
      addLog(`Building metadata index for project ${projectDir}...`);
      await client.buildMetadata(sourcePath, projectDir);
      setMetadataBuilt(true);
      addLog("Metadata build completed successfully.");
    } catch (err: any) {
      setErrorMsg(err?.message || String(err));
      addLog(`Metadata build failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Wikimedia Source Inspection</h2>
      <p style={{ color: "#666" }}>Select your MediaWiki dump folder or files.</p>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>
          Source Dump Directory / File:
        </label>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <input
            type="text"
            value={sourcePath}
            placeholder="/path/to/dumps"
            onChange={(e) => setSourceInfo(e.target.value, sourceInspection)}
            style={{ flex: 1, padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
          />
          <button
            onClick={handleInspect}
            disabled={loading || !sourcePath.trim()}
            style={{ padding: "0.5rem 1rem", background: "#333", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            Inspect
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ color: "#d9534f", background: "#fdf7f7", padding: "0.75rem", borderRadius: "4px", marginBottom: "1rem" }}>
          {errorMsg}
        </div>
      )}

      {sourceInspection && (
        <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1rem" }}>
          <h3>Dump Inspection Results</h3>
          <p><strong>Project:</strong> {sourceInspection.fingerprint?.project || sourceInspection.project || "Wikimedia"}</p>
          <p><strong>Language:</strong> {sourceInspection.fingerprint?.language || sourceInspection.language || "en"}</p>
          <p><strong>Dump Kind:</strong> {sourceInspection.dump_kind || sourceInspection.kind || "multistream"}</p>
          {sourceInspection.fingerprint?.dump_date && (
            <p><strong>Dump Date:</strong> {sourceInspection.fingerprint.dump_date}</p>
          )}

          <div style={{ marginTop: "0.75rem", fontSize: "0.9rem" }}>
            <p style={{ margin: "0.25rem 0" }}>
              <strong>Companions:</strong>{" "}
              {sourceInspection.has_page_sql ? "✓ page.sql" : "✗ page.sql missing"} |{" "}
              {sourceInspection.has_categorylinks_sql ? "✓ categorylinks.sql" : "✗ categorylinks.sql missing"}{" "}
              {sourceInspection.has_linktarget ? "| ✓ linktarget.sql" : ""}
            </p>
          </div>

          {(!sourceInspection.has_categorylinks_sql || !sourceInspection.has_page_sql || (sourceInspection.warnings && sourceInspection.warnings.length > 0)) && (
            <div style={{ color: "#8a6d3b", background: "#fcf8e3", padding: "0.5rem", borderRadius: "4px", marginTop: "0.5rem" }}>
              {sourceInspection.warnings && sourceInspection.warnings.length > 0 ? (
                sourceInspection.warnings.map((w: string, i: number) => <div key={i}>{w}</div>)
              ) : (
                <div>Warning: Companion SQL dumps missing. Download page.sql.gz and categorylinks.sql.gz for category graph traversal.</div>
              )}
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "1.5rem" }}>
        <button
          onClick={() => setStep(1)}
          style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}
        >
          {UX_COPY.wizard.btnBack}
        </button>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={handleBuildMetadata}
            disabled={loading || !sourceInspection}
            style={{ padding: "0.5rem 1rem", background: "#28a745", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            Build Metadata Index
          </button>
          <button
            onClick={() => setStep(3)}
            disabled={!metadataBuilt && !sourceInspection}
            style={{ padding: "0.5rem 1.5rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            {UX_COPY.wizard.btnNext}
          </button>
        </div>
      </div>
    </div>
  );
};
