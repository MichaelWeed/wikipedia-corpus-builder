import React, { useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface DomainScreenProps {
  client: EngineClient;
}

export const DomainScreen: React.FC<DomainScreenProps> = ({ client }) => {
  const {
    domainDraft,
    projectDir,
    projectName,
    domainPath,
    modelConfig,
    setDomainDraft,
    setDomainPath,
    setDomainLockPath,
    setStep,
    addLog,
  } = useWizardStore();
  const [loading, setLoading] = useState(false);

  const handleProposeFacets = async () => {
    if (!domainDraft.intent.trim()) return;
    setLoading(true);
    try {
      addLog(`Proposing facets for intent "${domainDraft.intent}"...`);
      const res = await client.proposeFacets(domainDraft.intent, modelConfig.provider || undefined);
      if (res && (res.include_facets || res.exclude_facets)) {
        setDomainDraft({
          includeFacets: res.include_facets || [],
          excludeFacets: res.exclude_facets || [],
          facetRationale: res.rationale || "",
          boundaryQuestions: [],
        });
      }
      addLog(`Propose facets result: ${JSON.stringify(res)}`);
    } catch (err) {
      addLog(`Propose facets failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGetBoundaryQuestions = async () => {
    if (!projectDir.trim() || !domainDraft.intent.trim()) return;
    setLoading(true);
    try {
      // domain.boundaryQuestions/applyAnswers operate against a project's
      // domain.yaml on disk, so make sure a draft exists before asking for
      // (or later applying) boundary questions.
      addLog(`Writing draft domain definition for "${projectName}"...`);
      const created = await client.createDomain(projectDir, {
        name: projectName,
        language: "en",
        intent: domainDraft.intent,
        roots: domainDraft.rootCategories,
        maxDepth: domainDraft.depth,
        facets: domainDraft.includeFacets,
        excludeFacets: domainDraft.excludeFacets,
      });
      const domainFile = `${projectDir}/domain.yaml`;
      setDomainPath(domainFile);
      addLog(`Domain draft written: ${JSON.stringify(created)}`);

      addLog(`Requesting boundary questions for intent "${domainDraft.intent}"...`);
      const questions = await client.boundaryQuestions(domainDraft.intent, {
        include_facets: domainDraft.includeFacets,
        exclude_facets: domainDraft.excludeFacets,
        rationale: domainDraft.facetRationale,
      });
      if (Array.isArray(questions)) {
        const defaults: Record<string, string> = {};
        for (const q of questions) defaults[q.id] = q.recommended;
        setDomainDraft({ boundaryQuestions: questions, boundaryAnswers: defaults });
      }
      addLog(`Boundary questions result: ${JSON.stringify(questions)}`);
    } catch (err) {
      addLog(`Boundary questions failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyAnswers = async () => {
    if (!domainPath.trim() || domainDraft.boundaryQuestions.length === 0) return;
    setLoading(true);
    try {
      addLog("Applying boundary answers to domain definition...");
      const updated = await client.applyAnswers(
        domainPath,
        projectDir,
        domainDraft.boundaryQuestions,
        domainDraft.boundaryAnswers,
      );
      setDomainDraft({
        includeFacets: updated?.facets?.include ?? domainDraft.includeFacets,
        excludeFacets: updated?.facets?.exclude ?? domainDraft.excludeFacets,
        boundaryQuestions: [],
      });
      addLog(`Domain updated with answers: ${JSON.stringify(updated)}`);
    } catch (err) {
      addLog(`Apply answers failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCompile = async () => {
    if (!projectDir.trim() || domainDraft.rootCategories.length === 0) return;
    setLoading(true);
    try {
      addLog(`Writing domain definition for "${projectName}"...`);
      // Desktop defaults to English; a full language picker isn't wired yet
      // (see design's source-filename-inferred / manual language selection).
      const created = await client.createDomain(projectDir, {
        name: projectName,
        language: "en",
        intent: domainDraft.intent,
        roots: domainDraft.rootCategories,
        maxDepth: domainDraft.depth,
        facets: domainDraft.includeFacets,
        excludeFacets: domainDraft.excludeFacets,
      });
      addLog(`Domain written: ${JSON.stringify(created)}`);

      addLog(`Compiling domain lock in ${projectDir}...`);
      const domainFile = `${projectDir}/domain.yaml`;
      setDomainPath(domainFile);
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

      {(domainDraft.includeFacets.length > 0 || domainDraft.excludeFacets.length > 0 || domainDraft.facetRationale) && (
        <div style={{ background: "#f8f9fa", padding: "1rem", borderRadius: "4px", border: "1px solid #eee", marginBottom: "1rem" }}>
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Include Facets (comma-separated):</label>
          <input
            type="text"
            value={domainDraft.includeFacets.join(", ")}
            onChange={(e) =>
              setDomainDraft({ includeFacets: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
            }
            style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc", marginBottom: "0.5rem" }}
          />
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: "bold" }}>Exclude Facets (comma-separated):</label>
          <input
            type="text"
            value={domainDraft.excludeFacets.join(", ")}
            onChange={(e) =>
              setDomainDraft({ excludeFacets: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
            }
            style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #ccc" }}
          />
          {domainDraft.facetRationale && (
            <p style={{ color: "#666", marginTop: "0.5rem", marginBottom: 0 }}>{domainDraft.facetRationale}</p>
          )}
          <button
            onClick={handleGetBoundaryQuestions}
            disabled={loading || !projectDir.trim() || !domainDraft.intent.trim()}
            style={{ marginTop: "0.75rem", padding: "0.4rem 1rem", background: "#333", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            Refine Boundaries with AI
          </button>
        </div>
      )}

      {domainDraft.boundaryQuestions.length > 0 && (
        <div style={{ background: "#e9f5ff", padding: "1rem", borderRadius: "4px", marginBottom: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>Boundary Questions</h3>
          {domainDraft.boundaryQuestions.map((q) => (
            <div key={q.id} style={{ padding: "0.5rem 0", borderBottom: "1px solid #d6e9f7" }}>
              <p style={{ margin: "0 0 0.25rem 0" }}>{q.question}</p>
              <label style={{ marginRight: "1rem" }}>
                <input
                  type="radio"
                  name={`boundary-${q.id}`}
                  checked={(domainDraft.boundaryAnswers[q.id] || q.recommended) === "include"}
                  onChange={() => setDomainDraft({ boundaryAnswers: { ...domainDraft.boundaryAnswers, [q.id]: "include" } })}
                />
                <span style={{ marginLeft: "0.25rem" }}>Include{q.recommended === "include" ? " (recommended)" : ""}</span>
              </label>
              <label>
                <input
                  type="radio"
                  name={`boundary-${q.id}`}
                  checked={(domainDraft.boundaryAnswers[q.id] || q.recommended) === "exclude"}
                  onChange={() => setDomainDraft({ boundaryAnswers: { ...domainDraft.boundaryAnswers, [q.id]: "exclude" } })}
                />
                <span style={{ marginLeft: "0.25rem" }}>Exclude{q.recommended === "exclude" ? " (recommended)" : ""}</span>
              </label>
            </div>
          ))}
          <button
            onClick={handleApplyAnswers}
            disabled={loading}
            style={{ marginTop: "0.75rem", padding: "0.4rem 1rem", background: "#28a745", color: "#fff", border: "none", borderRadius: "4px" }}
          >
            Apply Answers
          </button>
        </div>
      )}

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
