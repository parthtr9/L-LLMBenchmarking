// RecordDrawer — right-side drawer with full prompt, response, all model answers.

const RecordDrawer = ({ record, onClose }) => {
  if (!record) return null;
  const traceHtml = { __html: record.trace ? ENTITY_HIGHLIGHTS(record.trace) : '<em style="color:var(--lb-fg-4)">No reasoning trace.</em>' };
  const faith = record.faithfulness;

  // Build per-model answer rows from cells
  const cells = record.cells || {};
  const modelIds = Object.keys(cells);

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="head">
          <div>
            <h2>Record {String(record.row).padStart(3, '0')}</h2>
            <div className="id-line">{record.lbId} · {record.sourceDb}:{record.sourceId}</div>
          </div>
          <Button variant="ghost" size="small" className="close" icon="close" onClick={onClose}>Close</Button>
        </div>
        <div className="body">
          <dl className="kv">
            <dt>Domain</dt><dd>{record.organism}</dd>
            {record.gene1 !== '—' && <><dt>Gene</dt><dd className="mono">{record.gene1}{record.gene2 !== '—' ? ` · ${record.gene2}` : ''}</dd></>}
            <dt>Format</dt><dd>{record.format.replace(/_/g, ' ')}</dd>
            <dt>Metric</dt><dd>{record.metric}</dd>
            <dt>Gold answer</dt><dd className="mono" style={{ fontWeight: 600, color: 'var(--lb-green-700)' }}>{record.gold}</dd>
          </dl>

          {/* Full prompt — prefer raw question from export, fall back to legacy userMsg */}
          <div>
            <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Prompt</div>
            {record.system && (
              <div className="msg-block" style={{ background: 'var(--lb-ink-50)', borderLeft: '3px solid var(--lb-border)', marginBottom: 6, fontSize: 12, color: 'var(--lb-fg-3)', fontFamily: 'var(--lb-font-mono)', whiteSpace: 'pre-wrap', padding: '8px 12px' }}>
                <span style={{ fontWeight: 600, display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: 10 }}>System</span>
                {record.system}
              </div>
            )}
            <div className="msg-block user" style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--lb-font-mono)', fontSize: 12 }}>
              {record.question || record.userMsg}
            </div>
          </div>

          {/* Per-model answer comparison */}
          {modelIds.length > 0 && (
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="head"><h3>Model answers</h3><p className="sub">gold: <code style={{ fontFamily: 'var(--lb-font-mono)' }}>{record.gold}</code></p></div>
              <table className="lb" style={{ marginBottom: 0 }}>
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Prediction</th>
                    <th style={{ textAlign: 'center' }}>Match</th>
                    <th style={{ textAlign: 'right' }}>Score</th>
                    <th style={{ textAlign: 'right' }}>Latency</th>
                    <th style={{ textAlign: 'right' }}>Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {modelIds.map(mid => {
                    const c = cells[mid];
                    const displayName = (MODEL_NAMES || {})[mid] || mid;
                    const color = (MODEL_COLORS || {})[mid] || '#8c948c';
                    const pred = c.pred || '—';
                    // truncate long predictions (Claude gives verbose answers)
                    const predShort = pred.length > 120 ? pred.slice(0, 120) + '…' : pred;
                    return (
                      <tr key={mid}>
                        <td>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
                            {displayName}
                          </span>
                        </td>
                        <td className="mono" style={{ fontSize: 12, maxWidth: 260, wordBreak: 'break-word' }}>{predShort}</td>
                        <td style={{ textAlign: 'center' }}>
                          {c.pass == null ? '—' : (c.pass
                            ? <span style={{ color: 'var(--lb-green-700)', fontWeight: 600 }}>✓</span>
                            : <span style={{ color: 'var(--lb-error)', fontWeight: 600 }}>✗</span>)}
                        </td>
                        <td className="num">{c.score != null ? c.score.toFixed(3) : '—'}</td>
                        <td className="num">{c.latency_s != null ? c.latency_s.toFixed(1) + 's' : '—'}</td>
                        <td className="num">{c.tokens != null ? c.tokens : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* L-LLM trace if present */}
          {record.trace && (
            <div className="card" style={{ overflow: 'hidden' }}>
              <div className="head">
                <h3>L-LLM thinking trace</h3>
                <p className="sub">Qwen &lt;think&gt; · entities highlighted</p>
                <div className="right">
                  {record.consistent != null && (
                    record.consistent
                      ? <Badge kind="pass">consistent</Badge>
                      : <Badge kind="err">inconsistent</Badge>
                  )}
                  {faith != null && <span className="badge neutral">faithfulness {faith.toFixed(2)}</span>}
                </div>
              </div>
              <div className="trace-body" dangerouslySetInnerHTML={traceHtml} />
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="ghost" size="small" icon="file">View JSONL</Button>
            <Button variant="primary" size="small" icon="play">Re-run row</Button>
          </div>
        </div>
      </div>
    </>
  );
};

Object.assign(window, { RecordDrawer });
