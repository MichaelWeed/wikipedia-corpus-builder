import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface BuildScreenProps {
  client: EngineClient;
}

export const BuildScreen: React.FC<BuildScreenProps> = ({ client }) => {
  const { domainLockPath, projectDir, buildProgress, setBuildProgress, setBuildReport, setStep, addLog } = useWizardStore();
  const [purgeAfterBuild, setPurgeAfterBuild] = useState(false);
  const [building, setBuilding] = useState(false);
  const [outputDir, setOutputDir] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  const handleStartBuild = async () => {
    if (!projectDir.trim() || !domainLockPath.trim()) return;
    const out = outputDir.trim() || `${projectDir}/output`;
    setBuilding(true);
    setBuildProgress({ stage: "BUILDING", percent: 10, message: "Extracting articles from source dump..." });
    try {
      addLog(`Starting extraction build for project ${projectDir}...`);
      const res = await client.startBuild(domainLockPath, projectDir, out, true);
      setBuildReport(res);
      if (res && res.job_id) {
        setJobId(res.job_id);
      }
      setBuildProgress({ stage: "VALIDATED", percent: 100, message: "Build completed & validated successfully." });
      addLog(`Build finished: ${JSON.stringify(res)}`);
      setStep(7);
    } catch (err: any) {
      setBuildProgress({ stage: "FAILED", percent: 0, message: String(err) });
      addLog(`Build failed: ${err}`);
    } finally {
      setBuilding(false);
    }
  };

  const handleCancel = async () => {
    if (jobId) {
      try {
        await client.cancelBuild(jobId);
        addLog("Build cancellation sent.");
      } catch (err) {
        addLog(`Cancel error: ${err}`);
      }
    }
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Extraction Build Dashboard</h2>
      <p style={{ color: "#666" }}>Run canonical corpus extraction, atomic promoter, and validation checks.</p>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Output Directory:</label>
        <input
          type="text"
          value={outputDir}
          placeholder={`${projectDir}/output`}
          onChange={(e) => setOutputDir(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
      </div>

      <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1.5rem" }}>
        <h3>Build Mode Choice</h3>
        <label style={{ display: "block", margin: "0.5rem 0", cursor: "pointer" }}>
          <input
            type="radio"
            name="buildMode"
            checked={!purgeAfterBuild}
            onChange={() => setPurgeAfterBuild(false)}
          />
          <span style={{ marginLeft: "0.5rem", fontWeight: "bold" }}>Extract and keep source (Default)</span>
        </label>
        <label style={{ display: "block", margin: "0.5rem 0", cursor: "pointer" }}>
          <input
            type="radio"
            name="buildMode"
            checked={purgeAfterBuild}
            onChange={() => setPurgeAfterBuild(true)}
          />
          <span style={{ marginLeft: "0.5rem", fontWeight: "bold" }}>Extract, verify, then purge source (Advanced)</span>
        </label>
      </div>

      {buildProgress.stage !== "IDLE" && (
        <div style={{ background: "#f8f9fa", padding: "1rem", borderRadius: "4px", marginBottom: "1.5rem", border: "1px solid #eee" }}>
          <h4>Status: {buildProgress.stage}</h4>
          <p>{buildProgress.message}</p>
          <div style={{ background: "#e9ecef", height: "10px", borderRadius: "5px", overflow: "hidden", marginTop: "0.5rem" }}>
            <div style={{ background: "#28a745", width: `${buildProgress.percent}%`, height: "100%" }} />
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2rem" }}>
        <button onClick={() => setStep(5)} style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}>
          {UX_COPY.wizard.btnBack}
        </button>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          {building && (
            <button onClick={handleCancel} style={{ padding: "0.5rem 1rem", background: "#dc3545", color: "#fff", border: "none", borderRadius: "4px" }}>
              Cancel
            </button>
          )}
          <button
            onClick={handleStartBuild}
            disabled={building}
            style={{ padding: "0.5rem 1.5rem", background: "#28a745", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            {UX_COPY.wizard.btnBuild}
          </button>
        </div>
      </div>
    </div>
  );
};
