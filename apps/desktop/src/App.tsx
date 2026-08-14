import React, { useState } from 'react';
import { UX_COPY } from './copy';

export default function App() {
  const [step, setStep] = useState(1);
  const [projectName, setProjectName] = useState('MyWikis');
  const [sourcePath, setSourcePath] = useState('');
  const [statusMsg, setStatusMsg] = useState(UX_COPY.status.connected);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <header style={{ borderBottom: '1px solid #ccc', paddingBottom: '1rem', marginBottom: '2rem' }}>
        <h1>{UX_COPY.appTitle}</h1>
        <p style={{ color: '#666' }}>{UX_COPY.tagline}</p>
        <span style={{ fontSize: '0.85rem', color: '#2a7b37' }}>{statusMsg}</span>
      </header>

      <nav style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <button disabled={step === 1} onClick={() => setStep(1)}>{UX_COPY.wizard.stepProject}</button>
        <button disabled={step === 2} onClick={() => setStep(2)}>{UX_COPY.wizard.stepSource}</button>
        <button disabled={step === 3} onClick={() => setStep(3)}>{UX_COPY.wizard.stepModel}</button>
        <button disabled={step === 4} onClick={() => setStep(4)}>{UX_COPY.wizard.stepDomain}</button>
        <button disabled={step === 5} onClick={() => setStep(5)}>{UX_COPY.wizard.stepBuild}</button>
      </nav>

      <main style={{ minHeight: '300px', background: '#f9f9f9', padding: '1.5rem', borderRadius: '8px' }}>
        {step === 1 && (
          <div>
            <h2>Project Configuration</h2>
            <label style={{ display: 'block', margin: '1rem 0' }}>
              Project Name:
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                style={{ marginLeft: '0.5rem', padding: '0.4rem' }}
              />
            </label>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2>Wikimedia Source Inspection</h2>
            <label style={{ display: 'block', margin: '1rem 0' }}>
              Source Directory / File:
              <input
                type="text"
                value={sourcePath}
                onChange={(e) => setSourcePath(e.target.value)}
                placeholder="/path/to/dumps"
                style={{ marginLeft: '0.5rem', padding: '0.4rem', width: '300px' }}
              />
            </label>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2>Local AI Assistance</h2>
            <p>Ollama / LM Studio provider setup</p>
            <button onClick={() => setStep(4)}>{UX_COPY.wizard.btnSkipModel}</button>
          </div>
        )}

        {step === 4 && (
          <div>
            <h2>Domain Definition & Compiler</h2>
            <p>Define categories, roots, and compile domain lock</p>
            <button onClick={() => setStatusMsg("Compiling domain lock...")}>{UX_COPY.wizard.btnCompile}</button>
          </div>
        )}

        {step === 5 && (
          <div>
            <h2>Extraction Build & Export</h2>
            <p>Run build and export Markdown / JSONL</p>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
              <button>{UX_COPY.wizard.btnBuild}</button>
              <button>{UX_COPY.wizard.btnExportMarkdown}</button>
              <button>{UX_COPY.wizard.btnExportJsonl}</button>
            </div>
          </div>
        )}
      </main>

      <footer style={{ marginTop: '2rem', display: 'flex', justifyContent: 'space-between' }}>
        <button disabled={step === 1} onClick={() => setStep(s => s - 1)}>{UX_COPY.wizard.btnBack}</button>
        <button disabled={step === 5} onClick={() => setStep(s => s + 1)}>{UX_COPY.wizard.btnNext}</button>
      </footer>
    </div>
  );
}
