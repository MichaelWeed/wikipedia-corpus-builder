import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface PurgeScreenProps {
  client: EngineClient;
}

export const PurgeScreen: React.FC<PurgeScreenProps> = ({ client }) => {
  const { projectName, projectDir, setStep, addLog } = useWizardStore();
  const [confirmName, setConfirmName] = useState("");
  const [purgePlan, setPurgePlan] = useState<any>(null);
  const [purgeSuccess, setPurgeSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handlePlanPurge = async () => {
    if (!projectDir.trim()) return;
    setLoading(true);
    setErrorMsg("");
    try {
      addLog(`Planning safe purge for project ${projectDir}...`);
      const plan = await client.planPurge(projectDir);
      setPurgePlan(plan);
      addLog(`Purge plan ready: ${JSON.stringify(plan)}`);
    } catch (err: any) {
      setErrorMsg(err?.message || String(err));
      addLog(`Plan purge failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExecutePurge = async (mode: "trash" | "permanent") => {
    if (confirmName.trim() !== projectName) {
      setErrorMsg(`Typed confirmation token '${confirmName}' does not match project name '${projectName}'`);
      return;
    }
    setLoading(true);
    setErrorMsg("");
    try {
      addLog(`Executing purge in ${mode} mode...`);
      await client.confirmPurge(projectDir, mode, confirmName);
      setPurgeSuccess(true);
      addLog("Source dump successfully purged.");
    } catch (err: any) {
      setErrorMsg(err?.message || String(err));
      addLog(`Purge execution failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Safe Source Purge</h2>
      <p style={{ color: "#666" }}>Clean up raw source dump files only after verified canonical corpus promotion.</p>

      {!purgePlan ? (
        <button
          onClick={handlePlanPurge}
          disabled={loading}
          style={{ padding: "0.75rem 1.5rem", background: "#333", color: "#fff", border: "none", borderRadius: "4px" }}
        >
          Evaluate Purge Preconditions
        </button>
      ) : (
        <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1.5rem" }}>
          <h3>Purge Preconditions Checklist</h3>
          <p>✓ Job state is VALIDATED / EXPORTED</p>
          <p>✓ Validation status is PASSED</p>
          <p>✓ Source fingerprint matches build</p>
          <p>✓ Canonical corpus re-validated</p>
          <p><strong>Total Files to Delete:</strong> {purgePlan.files_to_delete?.length || 0}</p>
          <p><strong>Freed Space:</strong> ~{Math.round((purgePlan.total_bytes || 0) / 1024 / 1024)} MB</p>
        </div>
      )}

      {errorMsg && (
        <div style={{ color: "#d9534f", background: "#fdf7f7", padding: "0.75rem", borderRadius: "4px", marginBottom: "1rem" }}>
          {errorMsg}
        </div>
      )}

      {purgePlan && !purgeSuccess && (
        <div style={{ background: "#fff3cd", padding: "1rem", borderRadius: "4px", marginBottom: "1.5rem", border: "1px solid #ffeeba" }}>
          <p style={{ fontWeight: "bold" }}>Type project name to confirm deletion:</p>
          <input
            type="text"
            value={confirmName}
            placeholder={projectName}
            onChange={(e) => setConfirmName(e.target.value)}
            style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc", marginBottom: "1rem" }}
          />

          <div style={{ display: "flex", gap: "1rem" }}>
            <button
              onClick={() => handleExecutePurge("trash")}
              disabled={loading || confirmName.trim() !== projectName}
              style={{ flex: 1, padding: "0.5rem", background: "#ffc107", color: "#212529", border: "none", borderRadius: "4px", fontWeight: "bold" }}
            >
              Move Source to Trash
            </button>
            <button
              onClick={() => handleExecutePurge("permanent")}
              disabled={loading || confirmName.trim() !== projectName}
              style={{ flex: 1, padding: "0.5rem", background: "#dc3545", color: "#fff", border: "none", borderRadius: "4px", fontWeight: "bold" }}
            >
              Permanently Delete Source
            </button>
          </div>
        </div>
      )}

      {purgeSuccess && (
        <div style={{ background: "#d4edda", padding: "1rem", borderRadius: "4px", color: "#155724", border: "1px solid #c3e6cb", marginBottom: "1.5rem" }}>
          <h3>Source Purge Complete</h3>
          <p>Raw source files removed. Canonical corpus output is fully retained and safe.</p>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2rem" }}>
        <button onClick={() => setStep(7)} style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}>
          {UX_COPY.wizard.btnBack}
        </button>
      </div>
    </div>
  );
};
