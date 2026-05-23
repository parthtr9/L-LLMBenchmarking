// RecordDrawer — right-side drawer with full prompt, response, trace.

const RecordDrawer = ({ record, onClose }) => {
  if (!record) return null;
  const traceHtml = { __html: ENTITY_HIGHLIGHTS(record.trace) };
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
            <dt>Organism</dt><dd>{record.organism}</dd>
            <dt>Genes</dt><dd className="mono">{record.gene1} · {record.gene2}</dd>
            <dt>Format</dt><dd>{record.format.replace(/_/g, ' ')}</dd>
            <dt>Metric</dt><dd>{record.metric}</dd>
            <dt>Latency</dt><dd className="mono">{record.latencyS.toFixed(2)}s · {record.tokens} tok</dd>
          </dl>

          <div>
            <div className="lb-eyebrow" style={{ marginBottom: 6 }}>User message</div>
            <div className="msg-block user">{record.userMsg}</div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Gold</div>
              <div className="msg-block" style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 13 }}>{record.gold}</div>
            </div>
            <div>
              <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Predicted {record.match ? '· ✓ match' : '· ✗ miss'}</div>
              <div className="msg-block" style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 13, color: record.match ? 'var(--lb-green-700)' : 'var(--lb-error)' }}>{record.pred}</div>
            </div>
          </div>

          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="head">
              <h3>Thinking trace</h3>
              <p className="sub">Qwen &lt;think&gt; · entities highlighted</p>
              <div className="right">
                <Badge kind={record.consistent ? 'pass' : 'err'}>{record.consistent ? 'consistent' : 'inconsistent'}</Badge>
                <span className="badge neutral">faithfulness {record.faithfulness.toFixed(2)}</span>
              </div>
            </div>
            <div className="trace-body" dangerouslySetInnerHTML={traceHtml} />
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="ghost" size="small" icon="file">View JSONL</Button>
            <Button variant="secondary" size="small" icon="refresh">Re-score trace</Button>
            <Button variant="primary" size="small" icon="play">Re-run row</Button>
          </div>
        </div>
      </div>
    </>
  );
};

Object.assign(window, { RecordDrawer });
