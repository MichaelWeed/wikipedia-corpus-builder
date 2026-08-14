import React, { useEffect, useState } from "react";
import { useWizardStore } from "../store/wizardStore";
import { EngineClient } from "../engine/client";
import { UX_COPY } from "../copy";

interface PreviewScreenProps {
  client: EngineClient;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return "0 MB";
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export const PreviewScreen: React.FC<PreviewScreenProps> = ({ client }) => {
  const { domainPath, projectDir, sourceInspection, previewData, setPreviewData, setStep, addLog } =
    useWizardStore();
  const [searchTitle, setSearchTitle] = useState("");
  const [explainResult, setExplainResult] = useState<any>(null);
  const [ackWarnings, setAckWarnings] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPreview = async () => {
    if (!domainPath.trim() || !projectDir.trim()) return;
    setLoading(true);
    setError(null);
    try {
      addLog(`Loading domain preview for ${domainPath}...`);
      const res = await client.previewDomain(domainPath, projectDir);
      setPreviewData(res);
      addLog(`Preview loaded: ${res.article_count} articles selected.`);
    } catch (err) {
      setError(String(err));
      addLog(`Preview failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (domainPath.trim() && projectDir.trim() && !previewData) {
      loadPreview();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainPath, projectDir]);

  const handleExplain = async () => {
    if (!searchTitle.trim() || !domainPath.trim() || !projectDir.trim()) return;
    setLoading(true);
    try {
      addLog(`Explaining provenance for article "${searchTitle}"...`);
      const res = await client.explainDomain(domainPath, projectDir, searchTitle);
      setExplainResult(res);
      addLog(`Explain provenance result: ${JSON.stringify(res)}`);
    } catch (err) {
      addLog(`Explain failed: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const sourceBytes: number =
    sourceInspection?.fingerprint?.files?.reduce(
      (sum: number, f: any) => sum + (f.size_bytes || 0),
      0,
    ) || 0;
  const estimatedOutputBytes: number = previewData?.estimated_output_bytes || 0;
  const reclaimableBytes = Math.max(0, sourceBytes - estimatedOutputBytes);

  const warnings: string[] = previewData?.warnings || [];
  const hasBroadWarning = warnings.includes("selection_too_broad");
  const hasIncompleteWarning = warnings.includes("selection_probably_incomplete");
  const contamination: Record<string, string[]> = previewData?.contamination_groups || {};
  const hasContamination = Object.keys(contamination).length > 0;

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Domain Preview & Provenance Audit</h2>
      <p style={{ color: "#666" }}>
        Dry run: nothing is extracted or deleted here. Review what would be kept, then go back and
        adjust roots/exclusions if it doesn't look right.
      </p>

      {error && (
        <div style={{ background: "#fdecea", color: "#a33", padding: "0.75rem", borderRadius: "4px", marginBottom: "1rem" }}>
          Preview failed: {error}
          <button onClick={loadPreview} style={{ marginLeft: "1rem", padding: "0.25rem 0.75rem" }}>
            Retry
          </button>
        </div>
      )}

      {loading && !previewData && <p>Compiling and previewing selection…</p>}

      {previewData && (
        <>
          <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1rem" }}>
            <h3>Selection Metrics</h3>
            <p><strong>Selected Pages:</strong> {previewData.article_count?.toLocaleString()} articles</p>
            <p><strong>Estimated Raw Size:</strong> ~{formatBytes(previewData.estimated_output_bytes)}</p>
            <p><strong>Roots Resolved:</strong> {Object.keys(previewData.counts_by_root || {}).length} category root(s)</p>
            <button onClick={loadPreview} disabled={loading} style={{ padding: "0.3rem 0.8rem", marginTop: "0.5rem" }}>
              {loading ? "Refreshing…" : "Refresh Preview"}
            </button>
          </div>

          <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1rem" }}>
            <h3>Disk Space: Before vs. After</h3>
            <p><strong>Source dump:</strong> {formatBytes(sourceBytes)}</p>
            <p><strong>Estimated corpus output:</strong> ~{formatBytes(estimatedOutputBytes)}</p>
            {sourceBytes > 0 && (
              <p style={{ color: "#2a7b37" }}>
                <strong>Space reclaimable if you purge the source after a validated build:</strong>{" "}
                ~{formatBytes(reclaimableBytes)}
              </p>
            )}
            <p style={{ fontSize: "0.85rem", color: "#888" }}>
              Estimate only, based on average article size — the actual build report has the real
              figure. Purge is a separate, explicit, confirmed step; nothing is deleted by preview or build.
            </p>
          </div>

          {Object.keys(previewData.counts_by_root || {}).length > 0 && (
            <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1rem" }}>
              <h3>Counts by Root</h3>
              {Object.entries(previewData.counts_by_root).map(([root, count]) => (
                <p key={root}>{root}: {(count as number).toLocaleString()}</p>
              ))}
            </div>
          )}

          {previewData.sample_included?.length > 0 && (
            <div style={{ background: "#fff", padding: "1rem", borderRadius: "4px", border: "1px solid #ddd", marginBottom: "1rem" }}>
              <h3>Sample Included Pages</h3>
              <p>{previewData.sample_included.join(", ")}</p>
            </div>
          )}

          {(warnings.length > 0 || hasContamination) && (
            <div style={{ background: "#fff8e1", padding: "1rem", borderRadius: "4px", border: "1px solid #f0c36d", marginBottom: "1.5rem" }}>
              <h3>Warnings</h3>
              {hasBroadWarning && <p>⚠️ Selection may be too broad — over half of all articles were selected.</p>}
              {hasIncompleteWarning && <p>⚠️ Selection looks unusually small — fewer than 5 articles matched.</p>}
              {warnings
                .filter((w) => w !== "selection_too_broad" && w !== "selection_probably_incomplete")
                .map((w, i) => (
                  <p key={i}>⚠️ {w}</p>
                ))}
              {hasContamination && (
                <div>
                  <p><strong>Possible contamination</strong> (categories matching an excluded facet):</p>
                  {Object.entries(contamination).map(([facet, cats]) => (
                    <p key={facet}>&nbsp;&nbsp;"{facet}" → {(cats as string[]).join(", ")}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

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
            <p><strong>Title:</strong> {explainResult.target}</p>
            <p><strong>Status:</strong> {explainResult.status}</p>
            <p><strong>Reason:</strong> {explainResult.reason}</p>
            {explainResult.provenance_chain?.length > 0 && (
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
          disabled={!ackWarnings || !previewData}
          onClick={() => setStep(6)}
          style={{ padding: "0.5rem 1.5rem", background: "#0066cc", color: "#fff", border: "none", borderRadius: "4px" }}
        >
          {UX_COPY.wizard.btnNext}
        </button>
      </div>
    </div>
  );
};
