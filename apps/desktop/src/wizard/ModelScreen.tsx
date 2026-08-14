import React, { useState, useEffect } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface ModelScreenProps {
  client: EngineClient;
}

export const ModelScreen: React.FC<ModelScreenProps> = ({ client }) => {
  const { modelConfig, setModelConfig, setStep, addLog } = useWizardStore();
  const [detected, setDetected] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  useEffect(() => {
    handleProbe();
  }, []);

  const handleProbe = async () => {
    setLoading(true);
    try {
      addLog("Detecting local AI models (Ollama / LM Studio)...");
      const res = await client.detectModels();
      if (Array.isArray(res)) {
        setDetected(res);
      }
      addLog(`Model probe response: ${JSON.stringify(res)}`);
    } catch (err) {
      addLog(`Model probe error: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    setLoading(true);
    try {
      addLog(`Testing model ${modelConfig.modelName} at ${modelConfig.endpoint}...`);
      await client.testModel(modelConfig.provider || "ollama", modelConfig.endpoint, modelConfig.modelName);
      addLog("Model test PASSED.");
    } catch (err) {
      addLog(`Model test failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (modelConfig.endpoint && !modelConfig.endpoint.includes("localhost") && !modelConfig.endpoint.includes("127.0.0.1") && !modelConfig.privacyAccepted) {
      setShowPrivacyModal(true);
      return;
    }
    setStep(4);
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Local AI Assistance</h2>
      <p style={{ color: "#666" }}>Optionally connect Ollama or LM Studio for automated domain boundary suggestions.</p>

      {detected.length > 0 ? (
        <div style={{ background: "#e9f5ff", padding: "1rem", borderRadius: "4px", marginBottom: "1rem" }}>
          <h3>Detected AI Providers</h3>
          {detected.map((m: any, i: number) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0" }}>
              <span>{m.provider} — {m.model_id || m.model || "default"} ({m.base_url || m.endpoint})</span>
              <button
                onClick={() => setModelConfig({ provider: m.provider, endpoint: m.base_url || m.endpoint, modelName: m.model_id || m.model })}
                style={{ padding: "0.25rem 0.5rem" }}
              >
                Use Model
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginBottom: "1.5rem" }}>
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Provider Endpoint:</label>
          <input
            type="text"
            value={modelConfig.endpoint}
            onChange={(e) => setModelConfig({ endpoint: e.target.value })}
            style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc", marginBottom: "0.5rem" }}
          />

          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Model Name:</label>
          <input
            type="text"
            value={modelConfig.modelName}
            onChange={(e) => setModelConfig({ modelName: e.target.value })}
            style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
          />

          <button
            onClick={handleTest}
            disabled={loading}
            style={{ marginTop: "0.5rem", padding: "0.4rem 1rem", background: "#333", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            Test Connection
          </button>
        </div>
      )}

      {showPrivacyModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#fff", padding: "2rem", borderRadius: "8px", maxWidth: "500px" }}>
            <h3>Non-Loopback Endpoint Warning</h3>
            <p>Your configured endpoint ({modelConfig.endpoint}) is outside localhost. Article titles or category names may be sent to this endpoint.</p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
              <button onClick={() => setShowPrivacyModal(false)} style={{ padding: "0.5rem 1rem" }}>Cancel</button>
              <button
                onClick={() => {
                  setModelConfig({ privacyAccepted: true });
                  setShowPrivacyModal(false);
                  setStep(4);
                }}
                style={{ padding: "0.5rem 1rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px" }}
              >
                I Understand & Continue
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "2rem" }}>
        <button onClick={() => setStep(2)} style={{ padding: "0.5rem 1.5rem", background: "#ccc", border: "none", borderRadius: "4px" }}>
          {UX_COPY.wizard.btnBack}
        </button>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={() => {
              setModelConfig({ skip: true });
              setStep(4);
            }}
            style={{ padding: "0.5rem 1rem", background: "#6c757d", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            {UX_COPY.wizard.btnSkipModel}
          </button>
          <button onClick={handleNext} style={{ padding: "0.5rem 1.5rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px" }}>
            {UX_COPY.wizard.btnNext}
          </button>
        </div>
      </div>
    </div>
  );
};
