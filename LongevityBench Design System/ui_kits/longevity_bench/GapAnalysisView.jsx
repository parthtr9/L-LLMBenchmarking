// GapAnalysisView — interactive gap analysis built from gap_analysis_data.json.
// Modular: each sub-component (GapHeader, GapLeaderboard, GapFormatPanel,
// GapHeadToHead, GapConfusionMatrix, GapDistributionBar) is self-contained.

const _GAP_BASELINE_IDS = ['majority_baseline', 'random_baseline'];
const _GAP_FORMAT_ORDER = ['mcq', 'binary', 'pairwise', 'regression'];
const _GAP_FORMAT_LABELS = { mcq: 'MCQ', binary: 'Binary', pairwise: 'Pairwise', regression: 'Regression' };

// ── helpers ───────────────────────────────────────────────────────────────────

function _primaryScore(fmtMetrics, fmt) {
  if (!fmtMetrics) return null;
  if (fmt === 'regression') {
    const mae = fmtMetrics.mae;
    return mae != null ? 1 / (1 + mae) : null;
  }
  return fmtMetrics.balanced_accuracy ?? fmtMetrics.accuracy ?? null;
}

function _fmtPct(v, decimals = 1) {
  return v != null ? (v * 100).toFixed(decimals) + '%' : '—';
}

function _fmtNum(v, decimals = 3) {
  return v != null ? Number(v).toFixed(decimals) : '—';
}

function _overallScore(modelMetrics) {
  const fmts = ['mcq', 'binary', 'pairwise'];
  const vals = fmts.map(f => _primaryScore(modelMetrics[f], f)).filter(v => v != null);
  return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}

// ── GapHeader ─────────────────────────────────────────────────────────────────

const GapHeader = ({ generatedAt, dataset }) => {
  const trainN = dataset?.train?.n;
  const testN = dataset?.test?.n;
  const formats = Object.keys(dataset?.test?.formats || {}).sort();
  return (
    <div className="page-head">
      <div>
        <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Computed · gap_analysis_data.json</div>
        <h1>Gap analysis</h1>
        <div className="sub">
          {trainN != null && testN != null
            ? `${trainN} train · ${testN} test · ${formats.join(', ')}`
            : 'Run python -m src.analysis.gap_analysis to generate data'}
          {generatedAt && (
            <span style={{ marginLeft: 12, color: 'var(--lb-fg-4)' }}>
              {new Date(generatedAt).toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

// ── GapFormatTabs ─────────────────────────────────────────────────────────────

const GapFormatTabs = ({ formats, active, onChange }) => (
  <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
    {['all', ...formats].map(f => (
      <button
        key={f}
        onClick={() => onChange(f)}
        style={{
          padding: '5px 14px', borderRadius: 4,
          border: '1px solid var(--lb-border)',
          background: active === f ? 'var(--lb-green-500)' : 'transparent',
          color: active === f ? '#fff' : 'var(--lb-fg-3)',
          font: '500 12px var(--lb-font-sans)', cursor: 'pointer',
        }}
      >
        {f === 'all' ? 'All formats' : (_GAP_FORMAT_LABELS[f] || f)}
      </button>
    ))}
  </div>
);

// ── GapBaselineBadge ──────────────────────────────────────────────────────────

const GapBaselineBadge = ({ value, baseline, isMAE = false }) => {
  if (value == null || baseline == null) return null;
  const delta = isMAE ? baseline - value : value - baseline;
  const pct = (delta * 100).toFixed(1);
  const positive = delta > 0;
  const color = positive ? 'var(--lb-green-700)' : 'var(--lb-error)';
  return (
    <span style={{
      fontSize: 10, fontFamily: 'var(--lb-font-mono)', fontWeight: 600,
      color, marginLeft: 6,
    }}>
      {positive ? '+' : ''}{pct}%
    </span>
  );
};

// ── GapLeaderboard ────────────────────────────────────────────────────────────

const GapLeaderboard = ({ metrics, modelDisplay, modelOrder }) => {
  const models = modelOrder
    .filter(mid => metrics[mid])
    .map(mid => ({
      id: mid,
      name: modelDisplay[mid] || mid,
      color: (MODEL_COLORS || {})[mid] || '#8c948c',
      isBaseline: _GAP_BASELINE_IDS.includes(mid),
      overall: _overallScore(metrics[mid] || {}),
    }));

  const nonBaselines = [...models]
    .filter(m => !m.isBaseline && m.overall != null)
    .sort((a, b) => b.overall - a.overall);
  const majorityOverall = _overallScore(metrics['majority_baseline'] || {});
  const bestScore = nonBaselines[0]?.overall;

  return (
    <div className="card" style={{ marginBottom: 20, padding: '18px 24px' }}>
      <div className="head" style={{ marginBottom: 14 }}>
        <h3>Model leaderboard</h3>
        <p className="sub">avg balanced accuracy across MCQ · Binary · Pairwise</p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {models.map(m => {
          const rankPos = nonBaselines.findIndex(x => x.id === m.id);
          const rank = rankPos >= 0 ? rankPos + 1 : null;
          const barWidth = bestScore > 0 && m.overall != null
            ? (m.overall / bestScore) * 100
            : 0;
          return (
            <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 24, textAlign: 'right',
                font: '600 12px var(--lb-font-mono)',
                color: m.isBaseline ? 'var(--lb-fg-4)' : 'var(--lb-fg-2)',
              }}>
                {rank ? `#${rank}` : '—'}
              </div>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: m.color, flexShrink: 0 }} />
              <div style={{
                width: 130, font: '500 13px var(--lb-font-sans)',
                color: m.isBaseline ? 'var(--lb-fg-4)' : 'var(--lb-fg-1)',
                flexShrink: 0,
              }}>
                {m.name}
                {m.isBaseline && (
                  <span style={{ font: '400 10px var(--lb-font-sans)', marginLeft: 4, color: 'var(--lb-fg-4)' }}>
                    baseline
                  </span>
                )}
              </div>
              <div style={{
                flex: 1, height: 8, background: 'var(--lb-ink-100)',
                borderRadius: 4, overflow: 'hidden',
              }}>
                <div style={{
                  width: `${barWidth}%`, height: '100%', borderRadius: 4,
                  background: m.color, opacity: m.isBaseline ? 0.4 : 0.85,
                  transition: 'width 0.4s ease',
                }} />
              </div>
              <div style={{
                width: 54, textAlign: 'right',
                font: '600 13px var(--lb-font-mono)', color: m.color,
              }}>
                {m.overall != null ? (m.overall * 100).toFixed(1) + '%' : '—'}
              </div>
              {!m.isBaseline && (
                <GapBaselineBadge value={m.overall} baseline={majorityOverall} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── GapConfusionMatrix ────────────────────────────────────────────────────────

const GapConfusionMatrix = ({ cmInfo }) => {
  if (!cmInfo) return null;
  const { labels, matrix } = cmInfo;
  const maxVal = Math.max(...matrix.flat(), 1);
  return (
    <table style={{ borderCollapse: 'collapse', fontSize: 11, fontFamily: 'var(--lb-font-mono)' }}>
      <thead>
        <tr>
          <th style={{ padding: '3px 6px', color: 'var(--lb-fg-4)', fontWeight: 400, textAlign: 'left', fontSize: 10 }}>
            gold↓ pred→
          </th>
          {labels.map(l => (
            <th key={l} style={{ padding: '3px 8px', color: 'var(--lb-fg-3)', fontWeight: 600, textAlign: 'center' }}>
              {l}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {matrix.map((row, i) => (
          <tr key={i}>
            <td style={{ padding: '3px 6px', color: 'var(--lb-fg-3)', fontWeight: 600 }}>{labels[i]}</td>
            {row.map((v, j) => {
              const isDiag = i === j;
              const intensity = v / maxVal;
              const bg = isDiag
                ? `rgba(34,139,34,${0.08 + intensity * 0.45})`
                : v > 0 ? `rgba(200,50,50,${0.04 + intensity * 0.35})` : 'transparent';
              return (
                <td key={j} style={{
                  padding: '3px 8px', textAlign: 'center',
                  background: bg,
                  color: isDiag ? 'var(--lb-green-700)' : v > 0 ? 'var(--lb-error)' : 'var(--lb-fg-4)',
                  fontWeight: isDiag ? 600 : 400,
                  border: '1px solid var(--lb-border)',
                }}>
                  {v}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
};

// ── GapDistributionBar ────────────────────────────────────────────────────────

const GapDistributionBar = ({ predFraction }) => {
  if (!predFraction) return null;
  const aFrac = predFraction['A'] || 0;
  const bFrac = predFraction['B'] || 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{
        height: 6, width: 72, borderRadius: 3, overflow: 'hidden',
        background: 'var(--lb-ink-100)', display: 'flex',
      }}>
        <div
          style={{ width: `${aFrac * 100}%`, background: 'var(--lb-green-500)', transition: 'width 0.3s' }}
          title={`A: ${(aFrac * 100).toFixed(0)}%`}
        />
        <div
          style={{ width: `${bFrac * 100}%`, background: '#8c948c', transition: 'width 0.3s' }}
          title={`B: ${(bFrac * 100).toFixed(0)}%`}
        />
      </div>
      <span style={{ fontSize: 10, fontFamily: 'var(--lb-font-mono)', color: 'var(--lb-fg-4)' }}>
        {(aFrac * 100).toFixed(0)}A/{(bFrac * 100).toFixed(0)}B
      </span>
    </div>
  );
};

// ── GapFormatPanel ────────────────────────────────────────────────────────────

const GapFormatPanel = ({ fmt, metrics, modelDisplay, modelOrder }) => {
  const ordered = modelOrder.filter(mid => metrics[mid]?.[fmt]);
  if (ordered.length === 0) return null;

  const isMAE = fmt === 'regression';
  const label = _GAP_FORMAT_LABELS[fmt] || fmt;
  const majorityScore = _primaryScore(metrics['majority_baseline']?.[fmt], fmt);

  const subLabels = {
    mcq: 'balanced accuracy · macro F1 · CI · confusion matrix',
    binary: 'balanced accuracy · class-level · prediction distribution',
    pairwise: 'accuracy · A/B distribution · position bias',
    regression: 'MAE · median AE · Spearman r · sign accuracy · CI',
  };

  return (
    <div className="card" style={{ marginBottom: 16, overflow: 'hidden' }}>
      <div className="head" style={{ marginBottom: 0 }}>
        <h3>{label}</h3>
        <p className="sub">{subLabels[fmt]}</p>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="lb" style={{ minWidth: 580 }}>
          <thead>
            <tr>
              <th>Model</th>
              <th style={{ textAlign: 'right' }}>N</th>
              {fmt === 'mcq' && <>
                <th style={{ textAlign: 'right' }}>Bal Acc</th>
                <th style={{ textAlign: 'right' }}>Macro F1</th>
                <th style={{ textAlign: 'right' }}>CI (F1)</th>
              </>}
              {(fmt === 'binary' || fmt === 'pairwise') && <>
                <th style={{ textAlign: 'right' }}>Bal Acc</th>
                <th style={{ textAlign: 'right' }}>Acc(A)</th>
                <th style={{ textAlign: 'right' }}>Acc(B)</th>
                <th>Pred dist</th>
                <th style={{ textAlign: 'right' }}>A-bias</th>
              </>}
              {fmt === 'regression' && <>
                <th style={{ textAlign: 'right' }}>MAE</th>
                <th style={{ textAlign: 'right' }}>Med AE</th>
                <th style={{ textAlign: 'right' }}>Spearman r</th>
                <th style={{ textAlign: 'right' }}>Sign Acc</th>
                <th style={{ textAlign: 'right', fontSize: 10 }}>CI (MAE)</th>
              </>}
              <th style={{ textAlign: 'right' }}>vs Majority</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map(mid => {
              const m = metrics[mid][fmt];
              const isBaseline = _GAP_BASELINE_IDS.includes(mid);
              const name = modelDisplay[mid] || mid;
              const color = (MODEL_COLORS || {})[mid] || '#8c948c';
              const primaryVal = _primaryScore(m, fmt);

              return (
                <tr key={mid}>
                  <td style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 120 }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: 2,
                      background: color, flexShrink: 0,
                    }} />
                    <span style={{
                      color: isBaseline ? 'var(--lb-fg-4)' : 'var(--lb-fg-1)',
                      fontWeight: isBaseline ? 400 : 500,
                    }}>
                      {name}
                    </span>
                  </td>
                  <td className="mono" style={{ textAlign: 'right' }}>{m.n}</td>

                  {fmt === 'mcq' && <>
                    <td className="mono" style={{ textAlign: 'right', fontWeight: 600, color }}>
                      {_fmtPct(m.balanced_accuracy)}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>{_fmtNum(m.macro_f1)}</td>
                    <td className="mono" style={{ textAlign: 'right', color: 'var(--lb-fg-4)', fontSize: 10 }}>
                      {m.ci_macro_f1
                        ? `[${m.ci_macro_f1[0].toFixed(3)}, ${m.ci_macro_f1[1].toFixed(3)}]`
                        : '—'}
                    </td>
                  </>}

                  {(fmt === 'binary' || fmt === 'pairwise') && <>
                    <td className="mono" style={{ textAlign: 'right', fontWeight: 600, color }}>
                      {_fmtPct(m.balanced_accuracy)}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {m.class_accuracy?.A != null ? _fmtPct(m.class_accuracy.A) : '—'}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {m.class_accuracy?.B != null ? _fmtPct(m.class_accuracy.B) : '—'}
                    </td>
                    <td><GapDistributionBar predFraction={m.prediction_fraction} /></td>
                    <td className="mono" style={{
                      textAlign: 'right',
                      color: m.a_bias != null && Math.abs(m.a_bias) > 0.2
                        ? 'var(--lb-error)' : 'var(--lb-fg-3)',
                    }}>
                      {m.a_bias != null ? (m.a_bias >= 0 ? '+' : '') + m.a_bias.toFixed(3) : '—'}
                    </td>
                  </>}

                  {fmt === 'regression' && <>
                    <td className="mono" style={{ textAlign: 'right', fontWeight: 600, color }}>
                      {m.mae != null ? m.mae.toFixed(3) : '—'}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {m.median_ae != null ? m.median_ae.toFixed(3) : '—'}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {m.spearman_r != null ? m.spearman_r.toFixed(3) : '—'}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {_fmtPct(m.sign_accuracy)}
                    </td>
                    <td className="mono" style={{ textAlign: 'right', color: 'var(--lb-fg-4)', fontSize: 10 }}>
                      {m.ci_mae
                        ? `[${m.ci_mae[0].toFixed(2)}, ${m.ci_mae[1].toFixed(2)}]`
                        : '—'}
                    </td>
                  </>}

                  <td style={{ textAlign: 'right' }}>
                    {!isBaseline && (
                      <GapBaselineBadge value={primaryVal} baseline={majorityScore} isMAE={isMAE} />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Confusion matrices for MCQ */}
      {fmt === 'mcq' && ordered.some(mid => metrics[mid]?.mcq?.confusion_matrix) && (
        <div style={{ padding: '14px 20px 18px', borderTop: '1px solid var(--lb-border)' }}>
          <div style={{
            font: '500 10px var(--lb-font-sans)', color: 'var(--lb-fg-4)',
            textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12,
          }}>
            Confusion matrices
          </div>
          <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
            {ordered
              .filter(mid => !_GAP_BASELINE_IDS.includes(mid))
              .map(mid => {
                const cm = metrics[mid]?.mcq?.confusion_matrix;
                if (!cm) return null;
                return (
                  <div key={mid}>
                    <div style={{
                      font: '500 11px var(--lb-font-sans)',
                      color: (MODEL_COLORS || {})[mid] || '#8c948c',
                      marginBottom: 6,
                    }}>
                      {modelDisplay[mid] || mid}
                    </div>
                    <GapConfusionMatrix cmInfo={cm} />
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
};

// ── GapHeadToHead ─────────────────────────────────────────────────────────────

const GapHeadToHead = ({ metrics, modelDisplay, modelOrder }) => {
  const selectable = modelOrder.filter(mid => metrics[mid]);
  const [modelA, setModelA] = React.useState(selectable[0] || '');
  const [modelB, setModelB] = React.useState(
    selectable.find(m => m !== selectable[0] && !_GAP_BASELINE_IDS.includes(m)) ||
    selectable[1] || ''
  );

  const sharedFormats = _GAP_FORMAT_ORDER.filter(f =>
    metrics[modelA]?.[f] || metrics[modelB]?.[f]
  );

  const selectStyle = {
    padding: '4px 10px', borderRadius: 4,
    border: '1px solid var(--lb-border)',
    background: 'var(--lb-bg-1)', color: 'var(--lb-fg-1)',
    font: '500 13px var(--lb-font-sans)', cursor: 'pointer',
  };

  return (
    <div className="card" style={{ marginBottom: 20, overflow: 'hidden' }}>
      <div className="head" style={{ marginBottom: 0 }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          Head-to-head
          <select value={modelA} onChange={e => setModelA(e.target.value)} style={selectStyle}>
            {selectable.map(mid => (
              <option key={mid} value={mid}>{modelDisplay[mid] || mid}</option>
            ))}
          </select>
          <span style={{ font: '400 12px var(--lb-font-sans)', color: 'var(--lb-fg-4)' }}>vs</span>
          <select value={modelB} onChange={e => setModelB(e.target.value)} style={selectStyle}>
            {selectable.map(mid => (
              <option key={mid} value={mid}>{modelDisplay[mid] || mid}</option>
            ))}
          </select>
        </h3>
        <p className="sub">per-format delta · ▲ = left model leads</p>
      </div>

      {sharedFormats.length === 0 ? (
        <p style={{ padding: '16px 20px', color: 'var(--lb-fg-4)', fontSize: 13 }}>
          No shared formats between selected models.
        </p>
      ) : (
        <div>
          {sharedFormats.map((fmt, i) => {
            const mA = metrics[modelA]?.[fmt];
            const mB = metrics[modelB]?.[fmt];
            const scoreA = _primaryScore(mA, fmt);
            const scoreB = _primaryScore(mB, fmt);
            const isMAE = fmt === 'regression';
            const colorA = (MODEL_COLORS || {})[modelA] || '#8c948c';
            const colorB = (MODEL_COLORS || {})[modelB] || '#8c948c';

            const rawDelta = scoreA != null && scoreB != null ? scoreA - scoreB : null;
            const maeDelta = isMAE && mA?.mae != null && mB?.mae != null
              ? mA.mae - mB.mae : null;

            let winner = null;
            if (isMAE) {
              if (maeDelta != null) winner = maeDelta < -0.001 ? 'A' : maeDelta > 0.001 ? 'B' : 'tie';
            } else {
              if (rawDelta != null) winner = rawDelta > 0.001 ? 'A' : rawDelta < -0.001 ? 'B' : 'tie';
            }

            const deltaDisplay = isMAE
              ? (maeDelta != null ? Math.abs(maeDelta).toFixed(2) + ' MAE' : null)
              : (rawDelta != null ? (Math.abs(rawDelta) * 100).toFixed(1) + '%' : null);

            const rowBg = winner === 'A'
              ? 'rgba(34,139,34,0.025)'
              : winner === 'B' ? 'rgba(180,30,30,0.025)' : 'transparent';

            return (
              <div key={fmt} style={{
                display: 'grid',
                gridTemplateColumns: '90px 1fr 100px 1fr',
                alignItems: 'center', gap: 12,
                padding: '12px 20px',
                borderTop: i > 0 ? '1px solid var(--lb-border)' : 'none',
                background: rowBg,
              }}>
                <div style={{
                  font: '500 10px var(--lb-font-sans)', color: 'var(--lb-fg-4)',
                  textTransform: 'uppercase', letterSpacing: '0.07em',
                }}>
                  {_GAP_FORMAT_LABELS[fmt] || fmt}
                </div>

                {/* Model A */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ font: '700 16px var(--lb-font-mono)', color: colorA }}>
                    {isMAE && mA?.mae != null ? mA.mae.toFixed(2) : _fmtPct(scoreA)}
                  </span>
                  {isMAE && <span style={{ font: '400 10px var(--lb-font-sans)', color: 'var(--lb-fg-4)' }}>MAE</span>}
                  {winner === 'A' && deltaDisplay && (
                    <span style={{
                      padding: '1px 6px', borderRadius: 3,
                      background: 'rgba(34,139,34,0.12)',
                      font: '600 10px var(--lb-font-mono)', color: 'var(--lb-green-700)',
                    }}>
                      ▲ {deltaDisplay}
                    </span>
                  )}
                </div>

                {/* Center: tie or B leads */}
                <div style={{ textAlign: 'center', font: '600 11px var(--lb-font-mono)', color: 'var(--lb-fg-4)' }}>
                  {winner === 'tie' && <span>= tie</span>}
                  {winner === 'B' && deltaDisplay && (
                    <span style={{
                      padding: '1px 6px', borderRadius: 3,
                      background: 'rgba(180,30,30,0.1)',
                      color: 'var(--lb-error)',
                      font: '600 10px var(--lb-font-mono)',
                    }}>
                      ▼ {deltaDisplay}
                    </span>
                  )}
                  {winner == null && <span>—</span>}
                </div>

                {/* Model B */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ font: '700 16px var(--lb-font-mono)', color: colorB }}>
                    {isMAE && mB?.mae != null ? mB.mae.toFixed(2) : _fmtPct(scoreB)}
                  </span>
                  {isMAE && <span style={{ font: '400 10px var(--lb-font-sans)', color: 'var(--lb-fg-4)' }}>MAE</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ── GapAnalysisView (orchestrator) ────────────────────────────────────────────

const GapAnalysisView = () => {
  const [data, setData] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [activeFormat, setActiveFormat] = React.useState('all');

  React.useEffect(() => {
    fetch('./public/gap_analysis_data.json')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => setData(d))
      .catch(e => setErr(e.message));
  }, []);

  if (err) return (
    <>
      <div className="page-head">
        <div><h1>Gap analysis</h1><div className="sub">No data found.</div></div>
      </div>
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <div className="lb-eyebrow" style={{ marginBottom: 8 }}>Not generated</div>
        <p className="lb-p" style={{ color: 'var(--lb-fg-3)' }}>
          Run <code>python -m src.analysis.gap_analysis</code> then reload.
        </p>
        <p style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11, color: 'var(--lb-fg-4)', marginTop: 8 }}>
          {err}
        </p>
      </div>
    </>
  );

  if (!data) return (
    <>
      <div className="page-head">
        <div><h1>Gap analysis</h1><div className="sub">Loading…</div></div>
      </div>
    </>
  );

  const { generated_at, dataset, model_display, model_order, metrics } = data;

  const formatsPresent = _GAP_FORMAT_ORDER.filter(f =>
    Object.values(metrics).some(m => m[f])
  );
  const visibleFormats = activeFormat === 'all' ? formatsPresent : [activeFormat];

  return (
    <>
      <GapHeader generatedAt={generated_at} dataset={dataset} />
      <GapFormatTabs formats={formatsPresent} active={activeFormat} onChange={setActiveFormat} />
      <GapLeaderboard metrics={metrics} modelDisplay={model_display} modelOrder={model_order} />
      <GapHeadToHead metrics={metrics} modelDisplay={model_display} modelOrder={model_order} />
      {visibleFormats.map(fmt => (
        <GapFormatPanel
          key={fmt}
          fmt={fmt}
          metrics={metrics}
          modelDisplay={model_display}
          modelOrder={model_order}
        />
      ))}
    </>
  );
};

Object.assign(window, { GapAnalysisView });
