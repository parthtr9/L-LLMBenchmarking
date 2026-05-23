// TrustView — primary screen. Shows trace faithfulness, entity verification,
// trace ↔ label consistency. This is the trust-in-AI-reasoning story.

const FaithfulnessHist = () => {
  // 10 buckets, 0.0 → 1.0
  const buckets = [2, 1, 3, 5, 8, 12, 22, 38, 65, 34];
  const max = Math.max(...buckets);
  return (
    <div className="card">
      <div className="head">
        <h3>Faithfulness distribution</h3>
        <p className="sub">all 190 L-LLM traces · weighted score · last run LB-0038</p>
        <div className="right">
          <span className="badge neutral">μ = 0.81</span>
          <span className="badge neutral">σ = 0.18</span>
        </div>
      </div>
      <div style={{ padding: '20px 24px 22px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 6, alignItems: 'end', height: 140 }}>
          {buckets.map((v, i) => {
            const lo = (i / 10).toFixed(1);
            const isLow = i < 4;
            const color = isLow ? 'var(--lb-error)' : (i < 7 ? 'var(--lb-warning)' : 'var(--lb-green-500)');
            const h = Math.max(6, (v / max) * 120);
            return (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                <span style={{ font: '500 11px var(--lb-font-mono)', color: 'var(--lb-fg-3)' }}>{v}</span>
                <div style={{ width: '100%', height: h, background: color, opacity: 0.88, borderRadius: '3px 3px 0 0' }} title={`${lo}–${(i / 10 + 0.1).toFixed(1)}: ${v} traces`} />
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
          <span><span style={{ width: 8, height: 8, background: 'var(--lb-error)', display: 'inline-block', borderRadius: 2, marginRight: 6 }} />Low (&lt; 0.4) · 11</span>
          <span><span style={{ width: 8, height: 8, background: 'var(--lb-warning)', display: 'inline-block', borderRadius: 2, marginRight: 6 }} />Medium · 42</span>
          <span><span style={{ width: 8, height: 8, background: 'var(--lb-green-500)', display: 'inline-block', borderRadius: 2, marginRight: 6 }} />High (≥ 0.7) · 137</span>
        </div>
      </div>
    </div>
  );
};

const EntityVerification = () => {
  // Components of trace_faithfulness formula
  const rows = [
    { kind: 'C. elegans genes',  verified: 487, total: 512, source: 'WormBase REST',   color: 'var(--lb-green-500)' },
    { kind: 'Human genes',         verified: 312, total: 318, source: 'NCBI Gene eutils', color: 'var(--lb-green-500)' },
    { kind: 'Mouse genes',         verified: 188, total: 211, source: 'MGI API',          color: 'var(--lb-green-500)' },
    { kind: 'KEGG pathways',       verified: 94,  total: 142, source: 'KEGG REST /get/',  color: 'var(--lb-warning)' },
    { kind: 'Protein interactions',verified: 27,  total: 88,  source: 'STRING-DB',        color: 'var(--lb-error)' },
    { kind: 'Trace ↔ label',      verified: 187, total: 190, source: 'keyword direction',color: 'var(--lb-green-500)' },
  ];
  return (
    <div className="card">
      <div className="head">
        <h3>Entity verification</h3>
        <p className="sub">live calls to external scientific databases · per trace_faithfulness formula</p>
        <div className="right">
          <Button variant="ghost" size="small" icon="refresh">Re-verify</Button>
        </div>
      </div>
      <div style={{ padding: '14px 24px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {rows.map((r) => {
          const pct = (r.verified / r.total) * 100;
          return (
            <div key={r.kind}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4, gap: 10 }}>
                <span style={{ font: '500 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', whiteSpace: 'nowrap' }}>{r.kind}</span>
                <span style={{ font: '500 12px var(--lb-font-mono)', color: 'var(--lb-fg-2)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                  <span style={{ color: r.color }}>{r.verified}</span>
                  <span style={{ color: 'var(--lb-fg-4)' }}> / {r.total}</span>
                  <span style={{ color: 'var(--lb-fg-3)', marginLeft: 8 }}>({pct.toFixed(0)}%)</span>
                </span>
              </div>
              <div style={{ height: 6, background: 'var(--lb-ink-100)', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: r.color, borderRadius: 3 }} />
              </div>
              <div style={{ font: '400 10px var(--lb-font-mono)', color: 'var(--lb-fg-4)', marginTop: 4 }}>{r.source}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const FeaturedTrace = ({ record, onOpenRecord }) => {
  if (!record) return null;
  const traceHtml = { __html: ENTITY_HIGHLIGHTS(record.trace) };
  return (
    <div className="card">
      <div className="head">
        <h3>Trace inspection · row {String(record.row).padStart(3, '0')}</h3>
        <p className="sub">{record.lbId} · {record.organism} · {record.gene1} · {record.gene2}</p>
        <div className="right">
          {record.consistent
            ? <Badge kind="pass">consistent</Badge>
            : <Badge kind="err">inconsistent</Badge>}
          <Badge kind="neutral">faithfulness {record.faithfulness.toFixed(2)}</Badge>
          <Button variant="ghost" size="small" icon="chevR" onClick={() => onOpenRecord(record)}>Open record</Button>
        </div>
      </div>
      <div className="trace-body" dangerouslySetInnerHTML={traceHtml} />
      <div style={{ padding: '10px 20px 14px', borderTop: '1px solid var(--lb-border)', display: 'flex', gap: 22, font: '400 12px var(--lb-font-sans)', color: 'var(--lb-fg-3)' }}>
        <span><span className="gene" style={{ background: 'var(--lb-green-50)', color: 'var(--lb-green-700)', padding: '1px 6px', borderRadius: 2 }}>gene</span> verified via WormBase / NCBI</span>
        <span><span className="verify" style={{ background: 'var(--lb-success-bg)', color: 'var(--lb-green-700)', padding: '1px 6px', borderRadius: 2 }}>direction</span> matches gold</span>
        <span><span className="fail" style={{ background: 'var(--lb-error-bg)', color: '#8a2419', padding: '1px 6px', borderRadius: 2 }}>conflict</span> trace disagrees with label</span>
      </div>
    </div>
  );
};

const LowFaithList = ({ records, onOpenRecord }) => {
  // Pick the lowest-faithfulness records.
  const sorted = [...records].sort((a, b) => a.faithfulness - b.faithfulness).slice(0, 4);
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="head">
        <h3>Lowest-faithfulness traces</h3>
        <p className="sub">audit these first · click to drill in</p>
        <div className="right">
          <Button variant="ghost" size="small">View all 11</Button>
        </div>
      </div>
      <table className="lb">
        <thead>
          <tr><th>Row</th><th>Task</th><th>Genes</th><th>Pred / Gold</th><th>Trace</th><th style={{ textAlign: 'right' }}>Faith.</th></tr>
        </thead>
        <tbody>
          {sorted.map(r => (
            <tr key={r.row} onClick={() => onOpenRecord(r)}>
              <td className="id">{String(r.row).padStart(3, '0')}</td>
              <td>{r.lbId}</td>
              <td className="mono">{r.gene1} · {r.gene2}</td>
              <td className="mono">
                <span style={{ color: r.match ? 'var(--lb-green-700)' : 'var(--lb-error)' }}>{r.pred}</span>
                <span style={{ color: 'var(--lb-fg-4)' }}> / {r.gold}</span>
              </td>
              <td>
                {r.consistent
                  ? <Badge kind="pass">consistent</Badge>
                  : <Badge kind="err">inconsistent</Badge>}
              </td>
              <td className="num" style={{ color: r.faithfulness < 0.5 ? 'var(--lb-error)' : (r.faithfulness < 0.7 ? '#8a5d12' : 'var(--lb-green-700)') }}>
                {r.faithfulness.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const TrustView = ({ records, onOpenRecord }) => {
  const featured = records.find(r => !r.consistent) || records[0];
  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Primary view · trustworthy AI reasoning</div>
          <h1>Trust &amp; reasoning</h1>
          <div className="sub">Automated bio-fact-checker on L-LLM thinking traces · NCBI · KEGG · WormBase · MGI · STRING-DB</div>
        </div>
        <div className="actions">
          <Button variant="ghost" icon="download" size="small">trace_scores.json</Button>
          <Button variant="secondary" icon="refresh" size="small">Re-score</Button>
        </div>
      </div>

      <div className="metric-grid">
        <MetricCard label="Avg faithfulness" value="0.81" sub="190 traces · L-LLM" delta={0.04} />
        <MetricCard label="Trace ↔ label" value="98.4%" sub="187 / 190 consistent" />
        <MetricCard label="Entities verified" value="1,135" sub="92% of 1,234 cited" />
        <MetricCard label="Hallucinated" value="11" sub="genes / pathways not in DB" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 16, marginBottom: 16 }}>
        <FaithfulnessHist />
        <EntityVerification />
      </div>

      <div style={{ marginBottom: 16 }}>
        <FeaturedTrace record={featured} onOpenRecord={onOpenRecord} />
      </div>

      <LowFaithList records={records} onOpenRecord={onOpenRecord} />
    </>
  );
};

Object.assign(window, { TrustView });
