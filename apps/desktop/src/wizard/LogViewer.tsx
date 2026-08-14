import React from "react";
import { useWizardStore } from "../store/wizardStore";

export const LogViewer: React.FC = () => {
  const { logs, clearLogs } = useWizardStore();

  const handleCopyLogs = () => {
    navigator.clipboard.writeText(logs.join("\n"));
  };

  return (
    <div style={{ marginTop: "2rem", background: "#1e1e1e", color: "#d4d4d4", padding: "1rem", borderRadius: "6px", fontFamily: "monospace", fontSize: "0.85rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem", borderBottom: "1px solid #333", paddingBottom: "0.5rem" }}>
        <span>Engine Activity Log ({logs.length} lines)</span>
        <div>
          <button onClick={handleCopyLogs} style={{ background: "#444", color: "#fff", border: "none", borderRadius: "3px", padding: "0.2rem 0.5rem", marginRight: "0.5rem", cursor: "pointer" }}>
            Copy All
          </button>
          <button onClick={clearLogs} style={{ background: "#444", color: "#fff", border: "none", borderRadius: "3px", padding: "0.2rem 0.5rem", cursor: "pointer" }}>
            Clear
          </button>
        </div>
      </div>
      <div style={{ maxHeight: "150px", overflowY: "auto", whiteSpace: "pre-wrap" }}>
        {logs.length === 0 ? (
          <span style={{ color: "#666" }}>No engine events recorded.</span>
        ) : (
          logs.map((log, idx) => <div key={idx}>{log}</div>)
        )}
      </div>
    </div>
  );
};
