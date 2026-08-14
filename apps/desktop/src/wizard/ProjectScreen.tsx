import React from "react";
import { useWizardStore } from "../store/wizardStore";
import { UX_COPY } from "../copy";

export const ProjectScreen: React.FC = () => {
  const { projectName, projectDir, setProjectInfo, setStep } = useWizardStore();

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Project Configuration</h2>
      <p style={{ color: "#666" }}>Set your workspace project name and local folder path.</p>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>
          Project Name:
        </label>
        <input
          type="text"
          value={projectName}
          onChange={(e) => setProjectInfo(e.target.value, projectDir)}
          style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>
          Project Working Directory:
        </label>
        <input
          type="text"
          value={projectDir}
          placeholder="/path/to/my_project"
          onChange={(e) => setProjectInfo(projectName, e.target.value)}
          style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
        />
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          disabled={!projectName.trim() || !projectDir.trim()}
          onClick={() => setStep(2)}
          style={{ padding: "0.5rem 1.5rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer" }}
        >
          {UX_COPY.wizard.btnNext}
        </button>
      </div>
    </div>
  );
};
