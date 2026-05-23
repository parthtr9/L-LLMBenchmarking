// RunDetail — metric cards + model comparison bar chart + records table.

const ModelBar = () => {
  const rows = [
    { lbl: 'L-LLM (Qwen3.5-9B)',    val: 0.62, color: 'var(--lb-green-500)' },
    { lbl: 'GPT-4o',                val: 0.58, color: '#2a6dc8' },
    { lbl: 'Majority baseline',     val: 0.42, color: '#c98b1c' },
    { lbl: 'Random uniform',        val: 0.33, color: '#8c948c' },
  ];
  const max = 1.0;
  return (
    <div className="card">
      <div className="head">
        <h3>Macro F1 — LB-0038 · epistasis ternary</h3>
        <p className="sub">test split · n=200 · 95% CI from 1,000 bootstrap resamples</p>
        <div className="right">
          <Button variant="ghost" size="small" icon="download">Export</Button>
        </div>
      </div>
      <div className="barchart">
        {rows.map(r => (
          <div className="row" key={r.lbl}>
            <span className="lbl">{r.lbl}</span>
            <div className="track">
              <div className="fill" style={{ width: `${(r.val / max) * 100}%`, background: r.color }} />
            </div>
            <span className="val">{r.val.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const RunDetail = ({ run, records, onOpenRecord }) => (
  <>
    <div className="page-head">
      <div>
        <div style={{ marginBottom: 6 }}>
          <Pill brand>{run.lbId}</Pill>
          <span style={{ marginLeft: 8 }}><Pill>{run.taskName.replace(/_/g, ' ')}</Pill></span>
        </div>
        <h1>{run.id}</h1>
        <div className="sub">
          Model <code style={{ background: 'transparent', border: 0, padding: 0, fontSize: 13 }}>{run.model}</code> ·
          {' '}{run.n} rows · seed 42 · {run.think ? 'think mode' : 'no think'} ·
          {' '}duration {Math.round(run.durationS / 60)}m {run.durationS % 60}s
        </div>
      </div>
      <div className="actions">
        <Button variant="ghost" icon="download" size="small">records.jsonl</Button>
        <Button variant="ghost" icon="download" size="small">summary.json</Button>
        <Button variant="secondary" icon="refresh" size="small">Re-score</Button>
        <Button variant="primary" icon="play">Re-run</Button>
      </div>
    </div>

    <div className="metric-grid">
      <MetricCard label="Macro F1" value={run.f1 != null ? run.f1.toFixed(2) : '—'} sub={run.ci ? `CI ${run.ci[0]} — ${run.ci[1]} · n=${run.n}` : `n=${run.n}`} delta={0.04} />
      <MetricCard label="Balanced acc." value={run.bal_acc != null ? run.bal_acc.toFixed(2) : '—'} sub="vs GPT-4o 0.55" />
      <MetricCard label="Latency p50" value="5.6s" sub="p95 9.4s · 200 calls" />
      <MetricCard label="Trace faithfulness" value={run.faithfulness != null ? run.faithfulness.toFixed(2) : '—'} sub={run.faithfulness ? `${Math.round(run.faithfulness * 190)} / 190 verified` : '—'} />
    </div>

    <div style={{ marginBottom: 22 }}>
      <ModelBar />
    </div>

    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="head">
        <h3>Records</h3>
        <p className="sub">{records.length} of {run.n} shown</p>
        <div className="right">
          <Button variant="ghost" size="small">All</Button>
          <Button variant="ghost" size="small">Errors</Button>
          <Button variant="ghost" size="small">Inconsistent traces</Button>
        </div>
      </div>
      <div style={{ maxHeight: 420, overflow: 'auto' }}>
        <table className="lb">
          <thead>
            <tr>
              <th>Row</th>
              <th>Format</th>
              <th>Organism</th>
              <th>Genes</th>
              <th>Gold</th>
              <th>Pred</th>
              <th style={{ textAlign: 'right' }}>Latency</th>
              <th>Trace</th>
            </tr>
          </thead>
          <tbody>
            {records.map(r => (
              <tr key={r.row} onClick={() => onOpenRecord(r)}>
                <td className="id">{String(r.row).padStart(3, '0')}</td>
                <td>{r.format.replace(/_/g, ' ')}</td>
                <td>{r.organism}</td>
                <td className="mono gene">{r.gene1} · {r.gene2}</td>
                <td className="mono">{r.gold}</td>
                <td>
                  {r.match
                    ? <Badge kind="pass">{r.pred}</Badge>
                    : <Badge kind="err">{r.pred}</Badge>}
                </td>
                <td className="num">{r.latencyS.toFixed(2)}s</td>
                <td>
                  {r.consistent
                    ? <Badge kind="pass">consistent</Badge>
                    : <Badge kind="err">inconsistent</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </>
);

Object.assign(window, { RunDetail, ModelBar });
