// NewRunModal — pick parquet + models, get CLI command to run locally.

const KNOWN_MODELS = [
  { id: 'longevity_llm',          label: 'L-LLM',                 sub: 'HF endpoint · thinking off' },
  { id: 'longevity_llm_thinking', label: 'L-LLM (thinking)',       sub: 'HF endpoint · thinking on · 3000 tok' },
  { id: 'claude_sonnet',          label: 'Claude Sonnet',          sub: 'anthropic/claude-sonnet-4-6' },
  { id: 'majority_baseline',      label: 'Majority baseline',      sub: 'train-distribution prior' },
  { id: 'random_baseline',        label: 'Random baseline',        sub: 'uniform random label' },
];

const KNOWN_PARQUETS = [
  { label: 'Task A · Senescence (test, 59)',  path: 'data/task_a_senescence/processed/task_a_senescence_test.parquet' },
  { label: 'Task A · Senescence (train, 239)', path: 'data/task_a_senescence/processed/task_a_senescence_train.parquet' },
  { label: 'Task A · Thinking subset (30)',  path: 'data/task_a_senescence/processed/task_a_senescence_test_30.parquet' },
  { label: 'Task B · Lipidomics (test, 57)', path: 'data/task_b_lipidomics/task_b_lipidomics_test.parquet' },
  { label: 'Task B · Lipidomics (train, 228)', path: 'data/task_b_lipidomics/task_b_lipidomics_train.parquet' },
];

const NewRunModal = ({ onCancel, onStart }) => {
  const [parquetMode, setParquetMode] = React.useState('known'); // 'known' | 'custom'
  const [selectedParquet, setSelectedParquet] = React.useState(KNOWN_PARQUETS[0].path);
  const [customFile, setCustomFile] = React.useState(null);
  const [selectedModels, setSelectedModels] = React.useState(
    new Set(['longevity_llm', 'claude_sonnet', 'majority_baseline', 'random_baseline'])
  );
  const [copied, setCopied] = React.useState(false);

  const toggleModel = (id) => {
    setSelectedModels(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const parquetPath = parquetMode === 'known'
    ? selectedParquet
    : (customFile ? customFile.name : '<path/to/file.parquet>');

  const needsThinkingTokens = selectedModels.has('longevity_llm_thinking');
  const modelsStr = [...selectedModels].join(',');

  const cmd = [
    `.venv/bin/python -m src.eval.run_inspect`,
    `  --parquet ${parquetPath}`,
    `  --models ${modelsStr || '<select models>'}`,
    needsThinkingTokens ? `  --max-tokens 3000` : null,
  ].filter(Boolean).join(' \\\n');

  const handleCopy = () => {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="head">
          <h2>New run</h2>
          <p>Select dataset and models — copy the command to run locally.</p>
        </div>

        <div className="body">

          {/* Parquet selector */}
          <div className="field full">
            <label>Dataset (parquet)</label>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              {['known', 'custom'].map(m => (
                <button key={m} onClick={() => setParquetMode(m)} style={{
                  font: '500 11px var(--lb-font-sans)',
                  padding: '4px 12px',
                  border: '1px solid var(--lb-border)',
                  borderRadius: 4,
                  background: parquetMode === m ? 'var(--lb-green-500)' : 'transparent',
                  color: parquetMode === m ? '#fff' : 'var(--lb-fg-2)',
                  cursor: 'pointer',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}>
                  {m === 'known' ? 'Known datasets' : 'Browse file'}
                </button>
              ))}
            </div>

            {parquetMode === 'known' ? (
              <select className="input" value={selectedParquet} onChange={e => setSelectedParquet(e.target.value)}>
                {KNOWN_PARQUETS.map(p => (
                  <option key={p.path} value={p.path}>{p.label}</option>
                ))}
              </select>
            ) : (
              <label style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px',
                border: '1px dashed var(--lb-border)',
                borderRadius: 6,
                cursor: 'pointer',
                font: '13px var(--lb-font-sans)',
                color: customFile ? 'var(--lb-fg-1)' : 'var(--lb-fg-3)',
              }}>
                <Icon name="flask" className="ico" style={{ flexShrink: 0 }} />
                {customFile ? customFile.name : 'Click to select .parquet file'}
                <input type="file" accept=".parquet" style={{ display: 'none' }}
                  onChange={e => setCustomFile(e.target.files[0] || null)} />
              </label>
            )}
          </div>

          {/* Model checkboxes */}
          <div className="field full">
            <label>Models</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {KNOWN_MODELS.map(m => (
                <label key={m.id} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 12px',
                  border: '1px solid',
                  borderColor: selectedModels.has(m.id) ? 'var(--lb-green-400)' : 'var(--lb-border)',
                  borderRadius: 6,
                  background: selectedModels.has(m.id) ? 'var(--lb-green-50)' : 'transparent',
                  cursor: 'pointer',
                }}>
                  <input type="checkbox" checked={selectedModels.has(m.id)}
                    onChange={() => toggleModel(m.id)}
                    style={{ accentColor: 'var(--lb-green-500)', width: 14, height: 14, flexShrink: 0 }} />
                  <div>
                    <div style={{ font: '500 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>{m.label}</div>
                    <div style={{ font: '11px var(--lb-font-mono)', color: 'var(--lb-fg-4)', marginTop: 1 }}>{m.sub}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Generated command */}
          <div className="field full">
            <label>Command to run</label>
            <div style={{ position: 'relative' }}>
              <pre style={{
                margin: 0,
                padding: '12px 14px',
                background: 'var(--lb-ink-50)',
                border: '1px solid var(--lb-border)',
                borderRadius: 6,
                font: '12px var(--lb-font-mono)',
                color: 'var(--lb-fg-1)',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                lineHeight: 1.7,
              }}>{cmd}</pre>
              <button onClick={handleCopy} style={{
                position: 'absolute', top: 8, right: 8,
                font: '500 10px var(--lb-font-sans)',
                padding: '3px 10px',
                border: '1px solid var(--lb-border)',
                borderRadius: 4,
                background: copied ? 'var(--lb-green-500)' : '#fff',
                color: copied ? '#fff' : 'var(--lb-fg-2)',
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}>{copied ? 'Copied!' : 'Copy'}</button>
            </div>
            <span className="hint">Run from repo root. After run: export logs → refresh dashboard.</span>
          </div>

        </div>

        <div className="foot">
          <Button variant="ghost" onClick={onCancel}>Close</Button>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { NewRunModal });
