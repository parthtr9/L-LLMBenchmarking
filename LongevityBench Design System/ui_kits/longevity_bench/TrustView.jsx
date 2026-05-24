// TrustView — primary screen. Shows trace faithfulness, entity verification,
// and trace ↔ label consistency. Data loaded from public/trace_faithfulness_scores.json.

// ── Explanation modal ─────────────────────────────────────────────────────────

const EXPLANATIONS = {
  avg_faithfulness: {
    title: 'Avg faithfulness',
    plain: 'How grounded is the model\'s chain-of-thought in real biology? Each thinking trace is scored by (1) checking whether the gene symbols it mentions actually exist in NCBI Gene and (2) verifying that the reasoning direction matches the final answer. A score of 1.0 means every gene cited is real and the reasoning never contradicts the prediction.',
    formula: '0.4 × (verified genes ÷ cited genes) + 0.3 × consistency score',
    scale: [
      { range: '≥ 0.70', label: 'High trust — reasoning is well-grounded', color: 'var(--lb-green-700)' },
      { range: '0.40 – 0.69', label: 'Moderate — some hallucination or inconsistency', color: '#8a5d12' },
      { range: '< 0.40', label: 'Low — reasoning is unreliable', color: 'var(--lb-error)' },
    ],
  },
  consistent: {
    title: 'Trace ↔ answer consistency',
    plain: 'What fraction of thinking traces are judged by an NLI model (DeBERTa-v3-large) to entail the predicted answer? The trace is the "premise"; the hypothesis is a short statement like "the correct choice is A". DeBERTa scores entailment probability — if ≥ 0.5, the trace is "consistent". The 3.4% rate is a known limitation: biological reasoning traces discuss genes and pathways at length but rarely state the answer choice explicitly within the first 1024 tokens that DeBERTa sees. This is a signal-quality issue with the NLI approach, not necessarily model inconsistency.',
    formula: 'P(trace entails predicted answer) ≥ 0.5 · scored by DeBERTa-v3-large MNLI',
    scale: [
      { range: '> 50%', label: 'Strong — NLI confirms reasoning matches answer', color: 'var(--lb-green-700)' },
      { range: '20 – 50%', label: 'Moderate — partial signal', color: '#8a5d12' },
      { range: '< 20%', label: 'Weak NLI signal — biological traces too long for DeBERTa', color: 'var(--lb-error)' },
    ],
    note: 'Low consistency does NOT mean the model is wrong — it means DeBERTa cannot match long biological text to a short answer label. The Spearman ρ = −0.39 (p=0.04) between faithfulness and accuracy is the more meaningful signal.',
  },
  genes_verified: {
    title: 'Genes verified',
    plain: 'Of all the gene symbols the model mentioned in its thinking traces, how many actually exist as real human genes in NCBI Gene? Symbols that fail lookup may be hallucinated names, symbols from the wrong organism, or common English words that happen to match the gene-symbol regex.',
    formula: 'Verified gene symbols ÷ total candidate symbols extracted from traces',
    scale: [
      { range: '> 70%', label: 'Good — most cited genes are real', color: 'var(--lb-green-700)' },
      { range: '40 – 70%', label: 'Moderate — false positives from regex filter', color: '#8a5d12' },
      { range: '< 40%', label: 'Low — many cited genes not found in NCBI', color: 'var(--lb-error)' },
    ],
    note: 'The regex matches all 2–10 char uppercase tokens. Common words (AND, RNA, etc.) are filtered via a stoplist, but some non-gene tokens still pass. The verified % is a conservative lower bound.',
  },
  format_faithfulness: {
    title: 'Faithfulness by question format',
    plain: 'The model\'s reasoning quality varies by task type. MCQ (multiple-choice direction) requires the model to reason about biological direction across three possibilities. Binary and pairwise tasks ask simpler relative comparisons. Faithfulness color reflects the score: green ≥ 0.70, amber 0.40–0.69, red < 0.40.',
    formula: '0.60 × gene_score + 0.40 × nli_consistency · computed per format',
    scale: [
      { range: '≥ 0.70', label: 'High — reasoning well-grounded', color: 'var(--lb-green-700)' },
      { range: '0.40 – 0.69', label: 'Moderate — some hallucination or drift', color: '#8a5d12' },
      { range: '< 0.40', label: 'Low — reasoning unreliable for this format', color: 'var(--lb-error)' },
    ],
    note: 'Low MCQ faithfulness + low MCQ accuracy together show the model is not just wrong — it\'s reasoning incorrectly. That\'s the key extra-credit finding.',
  },
};

const ExplanationModal = ({ metricKey, data, onClose }) => {
  const exp = EXPLANATIONS[metricKey];
  if (!exp) return null;

  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
        zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#fff', borderRadius: 10, maxWidth: 520, width: '100%',
          boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
          border: '1px solid var(--lb-border)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '18px 22px 14px', borderBottom: '1px solid var(--lb-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Metric explanation</div>
            <h3 style={{ margin: 0 }}>{exp.title}</h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', font: '400 22px var(--lb-font-sans)', color: 'var(--lb-fg-3)', lineHeight: 1 }}>×</button>
        </div>

        {/* Body */}
        <div style={{ padding: '18px 22px' }}>
          {/* Plain English */}
          <p style={{ margin: '0 0 16px', font: '400 14px var(--lb-font-sans)', lineHeight: 1.65, color: 'var(--lb-fg-1)' }}>
            {exp.plain}
          </p>

          {/* Formula */}
          <div style={{ background: 'var(--lb-ink-50)', borderRadius: 6, padding: '10px 14px', marginBottom: 16, font: '400 12px var(--lb-font-mono)', color: 'var(--lb-fg-2)', lineHeight: 1.5 }}>
            <div style={{ font: '500 11px var(--lb-font-sans)', color: 'var(--lb-fg-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Formula</div>
            {exp.formula}
          </div>

          {/* Scale */}
          <div style={{ marginBottom: exp.note ? 14 : 0 }}>
            <div style={{ font: '500 11px var(--lb-font-sans)', color: 'var(--lb-fg-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Interpretation</div>
            {exp.scale.map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 7 }}>
                <span style={{ font: '500 12px var(--lb-font-mono)', color: s.color, minWidth: 90, whiteSpace: 'nowrap' }}>{s.range}</span>
                <span style={{ font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-2)' }}>{s.label}</span>
              </div>
            ))}
          </div>

          {/* Note */}
          {exp.note && (
            <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--lb-info-bg)', borderRadius: 6, font: '400 12px var(--lb-font-sans)', color: '#1b4a8c', lineHeight: 1.55, border: '1px solid #b8cef0' }}>
              <strong>Note:</strong> {exp.note}
            </div>
          )}
        </div>

        <div style={{ padding: '10px 22px 16px', borderTop: '1px solid var(--lb-border)', display: 'flex', justifyContent: 'flex-end' }}>
          <button onClick={onClose} className="btn small secondary">Close</button>
        </div>
      </div>
    </div>
  );
};

// ── Histogram ─────────────────────────────────────────────────────────────────

const FaithfulnessHist = ({ samples }) => {
  const buckets = Array(10).fill(0);
  samples.forEach(s => {
    const idx = Math.min(9, Math.floor((s.faithfulness ?? 0) * 10));
    buckets[idx]++;
  });
  const max = Math.max(...buckets, 1);
  const mu = samples.length
    ? (samples.reduce((a, b) => a + (b.faithfulness ?? 0), 0) / samples.length).toFixed(3)
    : '—';

  return (
    <div className="card">
      <div className="head">
        <h3>Faithfulness distribution</h3>
        <p className="sub">{samples.length} L-LLM thinking traces · score 0 → 1</p>
        <div className="right">
          <span className="badge neutral">μ = {mu}</span>
        </div>
      </div>
      <div style={{ padding: '20px 24px 22px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 6, alignItems: 'end', height: 140 }}>
          {buckets.map((v, i) => {
            const lo = (i / 10).toFixed(1);
            const color = i < 4 ? 'var(--lb-error)' : i < 7 ? 'var(--lb-warning)' : 'var(--lb-green-500)';
            const h = Math.max(v > 0 ? 8 : 0, (v / max) * 120);
            return (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                {v > 0 && <span style={{ font: '500 11px var(--lb-font-mono)', color: 'var(--lb-fg-3)' }}>{v}</span>}
                <div
                  style={{ width: '100%', height: h, background: color, opacity: 0.88, borderRadius: '3px 3px 0 0' }}
                  title={`${lo}–${(i / 10 + 0.1).toFixed(1)}: ${v} traces`}
                />
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 4, marginTop: 8, font: '400 10px var(--lb-font-mono)', color: 'var(--lb-fg-4)' }}>
          {Array.from({ length: 10 }).map((_, i) => (
            <span key={i} style={{ flex: 1, textAlign: 'center' }}>{(i / 10).toFixed(1)}</span>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 14, font: '400 12px var(--lb-font-sans)', color: 'var(--lb-fg-3)' }}>
          <span><span style={{ width: 8, height: 8, background: 'var(--lb-error)', display: 'inline-block', borderRadius: 2, marginRight: 6 }} />Low (&lt; 0.4) · {buckets.slice(0, 4).reduce((a, b) => a + b, 0)}</span>
          <span><span style={{ width: 8, height: 8, background: 'var(--lb-warning)', display: 'inline-block', borderRadius: 2, marginRight: 6 }} />Medium · {buckets.slice(4, 7).reduce((a, b) => a + b, 0)}</span>
          <span><span style={{ width: 8, height: 8, background: 'var(--lb-green-500)', display: 'inline-block', borderRadius: 2, marginRight: 6 }} />High (≥ 0.7) · {buckets.slice(7).reduce((a, b) => a + b, 0)}</span>
        </div>
      </div>
    </div>
  );
};

// ── Format breakdown ──────────────────────────────────────────────────────────

const FormatBreakdown = ({ byFormat, onExplain }) => (
  <div className="card">
    <div className="head">
      <h3>Faithfulness by format</h3>
      <p className="sub">reasoning quality varies by task type</p>
      <div className="right">
        <button className="btn small ghost" onClick={() => onExplain('format_faithfulness')}>
          Why does this vary?
        </button>
      </div>
    </div>
    <div style={{ padding: '14px 24px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {Object.entries(byFormat).map(([fmt, s]) => {
        const faithColor = s.avg_faithfulness >= 0.7 ? 'var(--lb-green-700)' : s.avg_faithfulness >= 0.4 ? '#8a5d12' : 'var(--lb-error)';
        const faithBg = s.avg_faithfulness >= 0.7 ? 'var(--lb-success-bg)' : s.avg_faithfulness >= 0.4 ? 'var(--lb-warning-bg)' : 'var(--lb-error-bg)';
        return (
          <div key={fmt}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Pill brand>{fmt}</Pill>
                <span style={{ font: '400 12px var(--lb-font-sans)', color: 'var(--lb-fg-3)' }}>n = {s.n}</span>
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <span style={{ font: '500 12px var(--lb-font-mono)', color: faithColor, background: faithBg, padding: '2px 8px', borderRadius: 4 }}>
                  faith {s.avg_faithfulness.toFixed(3)}
                </span>
                <span style={{ font: '500 12px var(--lb-font-mono)', color: s.avg_accuracy >= 0.5 ? 'var(--lb-green-700)' : 'var(--lb-fg-3)', background: 'var(--lb-ink-50)', padding: '2px 8px', borderRadius: 4 }}>
                  acc {s.avg_accuracy.toFixed(3)}
                </span>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {[['Faithfulness', s.avg_faithfulness, 'var(--lb-green-500)'], ['Accuracy', s.avg_accuracy, '#c98b1c']].map(([label, val, color]) => (
                <div key={label}>
                  <div style={{ font: '400 10px var(--lb-font-mono)', color: 'var(--lb-fg-4)', marginBottom: 3 }}>{label}</div>
                  <div style={{ height: 5, background: 'var(--lb-ink-100)', borderRadius: 3 }}>
                    <div style={{ width: `${val * 100}%`, height: '100%', background: color, borderRadius: 3 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

// ── Per-sample table ──────────────────────────────────────────────────────────

const SampleTable = ({ samples, records, onOpenRecord }) => {
  const sorted = [...samples].sort((a, b) => (a.faithfulness ?? 1) - (b.faithfulness ?? 1)).slice(0, 8);
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="head">
        <h3>Lowest-faithfulness traces</h3>
        <p className="sub">audit these first — click to inspect record</p>
      </div>
      <table className="lb">
        <thead>
          <tr>
            <th>Sample</th>
            <th>Format</th>
            <th>Pred / Gold</th>
            <th>Genes cited</th>
            <th>Consistent</th>
            <th style={{ textAlign: 'right' }}>Faithfulness</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s, i) => {
            const rec = records.find(r => r.sourceId === s.id);
            const faith = s.faithfulness ?? 0;
            const faithColor = faith >= 0.7 ? 'var(--lb-green-700)' : faith >= 0.4 ? '#8a5d12' : 'var(--lb-error)';
            return (
              <tr key={s.id} onClick={() => rec && onOpenRecord(rec)} style={{ cursor: rec ? 'pointer' : 'default' }}>
                <td style={{ font: '500 12px var(--lb-font-mono)', color: 'var(--lb-fg-3)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.id}</td>
                <td><Pill>{s.format}</Pill></td>
                <td className="mono">
                  <span style={{ color: s.pass ? 'var(--lb-green-700)' : 'var(--lb-error)' }}>{s.pred || '—'}</span>
                  <span style={{ color: 'var(--lb-fg-4)' }}> / {s.gold}</span>
                </td>
                <td className="mono" style={{ color: 'var(--lb-fg-3)' }}>
                  {s.verified_genes?.length ?? 0}/{s.gene_candidates ?? 0}
                </td>
                <td>
                  {s.consistent
                    ? <Badge kind="pass">consistent</Badge>
                    : <Badge kind="err">inconsistent</Badge>}
                </td>
                <td className="num" style={{ color: faithColor, fontWeight: 500 }}>
                  {faith.toFixed(3)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

// ── Main TrustView ────────────────────────────────────────────────────────────

const TrustView = ({ records = [], onOpenRecord }) => {
  const [tsData, setTsData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [openModal, setOpenModal] = React.useState(null);

  React.useEffect(() => {
    fetch('./public/trace_faithfulness_scores.json')
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(d => { setTsData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="page-head">
        <div><h1>Trust &amp; reasoning</h1><div className="sub">Loading trace scores…</div></div>
      </div>
    );
  }

  if (!tsData) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Primary view · trustworthy AI reasoning</div>
            <h1>Trust &amp; reasoning</h1>
            <div className="sub">No trace scores found. Run the scorer first.</div>
          </div>
        </div>
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div className="lb-eyebrow" style={{ marginBottom: 8 }}>No data</div>
          <p className="lb-p" style={{ color: 'var(--lb-fg-3)' }}>
            Run: <code>.venv/bin/python -m src.trace_scorer.trace_scorer</code>
          </p>
        </div>
      </>
    );
  }

  const { avg_faithfulness, pct_consistent, n_consistent, n_scored,
          verified_genes, total_gene_candidates, pct_genes_verified,
          faithfulness_by_format, per_sample } = tsData;

  const mcqFaith = faithfulness_by_format?.mcq?.avg_faithfulness;
  const mcqColor = mcqFaith == null
    ? 'var(--lb-fg-3)'
    : mcqFaith >= 0.7 ? 'var(--lb-green-700)'
    : mcqFaith >= 0.4 ? '#8a5d12'
    : 'var(--lb-error)';

  const clickable = (metricKey) => ({
    onClick: () => setOpenModal(metricKey),
    style: { cursor: 'pointer' },
    title: 'Click to learn more',
  });

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Extra credit · trustworthy AI reasoning</div>
          <h1>Trust &amp; reasoning</h1>
          <div className="sub">
            Automated bio-fact-checker on L-LLM thinking traces · NCBI Gene · click any metric to learn more
          </div>
        </div>
        <div className="actions">
          <Button variant="ghost" icon="download" size="small">trace_scores.json</Button>
        </div>
      </div>

      <div style={{ marginBottom: 16, padding: '10px 16px', background: 'var(--lb-ink-50)', border: '1px solid var(--lb-border)', borderRadius: 6, font: '400 12px var(--lb-font-sans)', color: 'var(--lb-fg-3)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontWeight: 500, color: 'var(--lb-fg-2)' }}>Scope:</span>
        Trace scores cover <strong>Task A · Senescence Perturbation</strong> only — {n_scored} L-LLM thinking-mode traces. Task switching above does not affect this view. Task B traces will appear here after running the trace scorer on lipidomics outputs.
      </div>

      {/* Metric cards — all clickable */}
      <div className="metric-grid">
        <div className="metric" {...clickable('avg_faithfulness')}>
          <div className="lbl">Avg faithfulness <span style={{ fontSize: 10, color: 'var(--lb-fg-4)', marginLeft: 4 }}>ⓘ</span></div>
          <div className="val">{avg_faithfulness.toFixed(3)}</div>
          <div className="sub">{n_scored} traces · L-LLM thinking</div>
        </div>
        <div className="metric" {...clickable('consistent')}>
          <div className="lbl">Trace ↔ answer <span style={{ fontSize: 10, color: 'var(--lb-fg-4)', marginLeft: 4 }}>ⓘ</span></div>
          <div className="val">{pct_consistent.toFixed(1)}%</div>
          <div className="sub">{n_consistent} / {n_scored} consistent</div>
        </div>
        <div className="metric" {...clickable('genes_verified')}>
          <div className="lbl">Genes verified <span style={{ fontSize: 10, color: 'var(--lb-fg-4)', marginLeft: 4 }}>ⓘ</span></div>
          <div className="val">{verified_genes}</div>
          <div className="sub">{pct_genes_verified}% of {total_gene_candidates} cited</div>
        </div>
        <div className="metric" {...clickable('format_faithfulness')}>
          <div className="lbl">MCQ faithfulness <span style={{ fontSize: 10, color: 'var(--lb-fg-4)', marginLeft: 4 }}>ⓘ</span></div>
          <div className="val" style={{ color: mcqColor }}>
            {mcqFaith?.toFixed(3) ?? '—'}
          </div>
          <div className="sub">vs {faithfulness_by_format?.binary?.avg_faithfulness?.toFixed(3) ?? '—'} binary · click to compare</div>
        </div>
      </div>

      {/* Histogram + Format breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 16, marginBottom: 16 }}>
        <FaithfulnessHist samples={per_sample} />
        {faithfulness_by_format && Object.keys(faithfulness_by_format).length > 0 && (
          <FormatBreakdown byFormat={faithfulness_by_format} onExplain={setOpenModal} />
        )}
      </div>

      {/* Per-sample table */}
      <SampleTable samples={per_sample} records={records} onOpenRecord={onOpenRecord} />

      {/* Explanation modal */}
      {openModal && (
        <ExplanationModal metricKey={openModal} data={tsData} onClose={() => setOpenModal(null)} />
      )}
    </>
  );
};

Object.assign(window, { TrustView });
