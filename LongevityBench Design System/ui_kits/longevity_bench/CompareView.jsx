// CompareView — model comparison with grouped bar chart and per-model cards.
// Receives runs + records props from App.

const BASELINE_IDS = ['majority_baseline', 'random_baseline', 'population_prior_baseline'];
const FORMAT_ORDER = ['mcq', 'binary', 'pairwise', 'regression'];
const FORMAT_LABELS = { mcq: 'MCQ', binary: 'Binary', pairwise: 'Pairwise', regression: 'Regression' };

// ── Grouped bar chart (SVG) ───────────────────────────────────────────────────

const GroupedBarChart = ({ matrix, models, formats }) => {
  const W = 680;
  const LEGEND_COLS = Math.min(models.length, 3);
  const LEGEND_ROW_H = 16;
  const legendRows = Math.max(1, Math.ceil(models.length / LEGEND_COLS));
  const ML = 44, MR = 16, MT = 20;
  const MB = 44 + legendRows * LEGEND_ROW_H;
  const H = 240 + legendRows * LEGEND_ROW_H;
  const chartW = W - ML - MR;
  const chartH = H - MT - MB;
  const legendSpacing = chartW / LEGEND_COLS;

  const GROUP_GAP = 32;
  const barAreaW = (chartW - GROUP_GAP * (formats.length - 1)) / formats.length;
  const barW = Math.min(22, (barAreaW - 12) / models.length);
  const barSpacing = 3;
  const groupBarTotalW = barW * models.length + barSpacing * (models.length - 1);
  const barPad = (barAreaW - groupBarTotalW) / 2;

  const yTicks = [0, 0.25, 0.5, 0.75, 1.0];

  const groupX = (fi) => ML + fi * (barAreaW + GROUP_GAP);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W, display: 'block' }}>
      {/* Y grid + labels */}
      {yTicks.map(t => {
        const y = MT + chartH - t * chartH;
        return (
          <g key={t}>
            <line x1={ML} x2={ML + chartW} y1={y} y2={y}
              stroke="var(--lb-border)" strokeWidth={t === 0 ? 1.5 : 1} strokeDasharray={t > 0 ? '3 3' : ''} />
            <text x={ML - 6} y={y + 4} textAnchor="end"
              style={{ font: '10px var(--lb-font-mono)', fill: 'var(--lb-fg-4)' }}>
              {t.toFixed(2)}
            </text>
          </g>
        );
      })}

      {/* Bars + format labels */}
      {formats.map((fmt, fi) => {
        const gx = groupX(fi);
        const labelY = MT + chartH + 14;
        return (
          <g key={fmt}>
            {/* Format label */}
            <text x={gx + barAreaW / 2} y={labelY + 10}
              textAnchor="middle"
              style={{ font: '500 11px var(--lb-font-sans)', fill: 'var(--lb-fg-2)' }}>
              {FORMAT_LABELS[fmt] || fmt}
            </text>
            {/* Bars per model */}
            {models.map((m, mi) => {
              const v = matrix[fmt]?.[m.id];
              if (v == null) return null;
              const barH = v * chartH;
              const x = gx + barPad + mi * (barW + barSpacing);
              const y = MT + chartH - barH;
              const isBaseline = BASELINE_IDS.includes(m.id);
              return (
                <g key={m.id}>
                  <rect
                    x={x} y={y} width={barW} height={Math.max(barH, 1)}
                    fill={m.color}
                    opacity={isBaseline ? 0.4 : 0.88}
                    rx={2}
                  />
                  <title>{m.name}: {v.toFixed(3)}</title>
                  {barH >= 16 && (
                    <text x={x + barW / 2} y={y - 3} textAnchor="middle"
                      style={{ font: '9px var(--lb-font-mono)', fill: m.color, fontWeight: 600 }}>
                      {v.toFixed(2)}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        );
      })}

      {/* Legend (wraps to multiple rows when crowded) */}
      {models.map((m, i) => {
        const row = Math.floor(i / LEGEND_COLS);
        const col = i % LEGEND_COLS;
        const lx = ML + col * legendSpacing;
        const ly = H - 12 - (legendRows - 1 - row) * LEGEND_ROW_H;
        return (
          <g key={m.id} transform={`translate(${lx}, ${ly})`}>
            <rect x={0} y={-7} width={10} height={10} fill={m.color}
              opacity={BASELINE_IDS.includes(m.id) ? 0.45 : 0.9} rx={2} />
            <text x={14} y={2} style={{ font: '11px var(--lb-font-sans)', fill: 'var(--lb-fg-2)' }}>
              {m.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// ── Radial score ring (per-model card) ───────────────────────────────────────

const ScoreRing = ({ value, color, size = 52 }) => {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const dash = value * circ;
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="var(--lb-ink-100)" strokeWidth={6} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth={6}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.4s ease' }}
      />
    </svg>
  );
};

const ModelCard = ({ model, formatScores, formats, avgScore, nCorrect, nTotal }) => {
  const isBaseline = BASELINE_IDS.includes(model.id);
  return (
    <div className="card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ position: 'relative', width: 52, height: 52, flexShrink: 0 }}>
          <ScoreRing value={avgScore ?? 0} color={model.color} />
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
            justifyContent: 'center', font: '600 11px var(--lb-font-mono)',
            color: model.color, transform: 'none',
          }}>
            {avgScore != null ? (avgScore * 100).toFixed(0) + '%' : '—'}
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '500 14px var(--lb-font-sans)', color: 'var(--lb-fg-1)', marginBottom: 2 }}>
            {model.name}
            {isBaseline && <span style={{ marginLeft: 6, font: '400 11px var(--lb-font-sans)', color: 'var(--lb-fg-4)' }}>baseline</span>}
          </div>
          <div className="lb-meta">{nCorrect}/{nTotal} correct</div>
        </div>
      </div>

      {/* Per-format mini bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {formats.map(fmt => {
          const v = formatScores[fmt];
          if (v == null) return null;
          const color = v >= 0.6 ? 'var(--lb-green-500)' : v >= 0.4 ? '#c98b1c' : 'var(--lb-error)';
          return (
            <div key={fmt}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ font: '400 11px var(--lb-font-sans)', color: 'var(--lb-fg-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {FORMAT_LABELS[fmt] || fmt}
                </span>
                <span style={{ font: '500 11px var(--lb-font-mono)', color }}>
                  {v.toFixed(3)}
                </span>
              </div>
              <div style={{ height: 4, background: 'var(--lb-ink-100)', borderRadius: 3 }}>
                <div style={{ width: `${v * 100}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.3s ease' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── Main CompareView ──────────────────────────────────────────────────────────

const CompareView = ({ runs = [], records = [] }) => {
  const [showBaselines, setShowBaselines] = React.useState(true);

  // Derive model list from completed runs
  const modelMap = {};
  runs.filter(r => r.status === 'complete').forEach(r => {
    if (!modelMap[r.modelId]) {
      modelMap[r.modelId] = {
        id: r.modelId,
        name: r.model,
        color: (MODEL_COLORS || {})[r.modelId] || '#8c948c',
      };
    }
  });

  const _order = MODEL_ORDER || [];
  const models = Object.values(modelMap).sort((a, b) => {
    const ai = _order.indexOf(a.id);
    const bi = _order.indexOf(b.id);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.name.localeCompare(b.name);
  });

  // Derive formats present in records
  const formats = FORMAT_ORDER.filter(f =>
    records.some(r => r.format === f)
  );

  // Compute accuracy matrix: matrix[format][modelId] = accuracy
  const matrix = {};
  formats.forEach(fmt => {
    matrix[fmt] = {};
    models.forEach(m => {
      const fmtRecords = records.filter(r => r.format === fmt);
      if (fmtRecords.length === 0) return;
      const modelCells = fmtRecords.map(r => r.cells?.[m.id]);
      const scored = modelCells.filter(c => c && c.score != null);
      if (scored.length === 0) return;
      matrix[fmt][m.id] = scored.reduce((s, c) => s + c.score, 0) / scored.length;
    });
  });

  // Per-model stats
  const modelStats = models.map(m => {
    const formatScores = {};
    formats.forEach(f => { formatScores[f] = matrix[f]?.[m.id]; });
    const vals = Object.values(formatScores).filter(v => v != null);
    const avgScore = vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    const modelCells = records.map(r => r.cells?.[m.id]).filter(c => c && c.score != null);
    const nCorrect = modelCells.filter(c => c.pass).length;
    return { ...m, formatScores, avgScore, nCorrect, nTotal: modelCells.length };
  });

  // Best / second for key finding
  const nonBaselines = modelStats.filter(m => !BASELINE_IDS.includes(m.id) && m.avgScore != null);
  const best = nonBaselines.sort((a, b) => (b.avgScore ?? 0) - (a.avgScore ?? 0))[0];
  const second = nonBaselines.filter(m => m.id !== best?.id)[0];
  const majorityAvg = modelStats.find(m => m.id === 'majority_baseline')?.avgScore;

  if (models.length === 0 || records.length === 0) {
    return (
      <>
        <div className="page-head">
          <div><h1>Model comparison</h1><div className="sub">No completed runs yet.</div></div>
        </div>
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div className="lb-eyebrow" style={{ marginBottom: 8 }}>No data</div>
          <p className="lb-p" style={{ color: 'var(--lb-fg-3)' }}>Run <code>pipeline.py</code> then export logs.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Live results · built from outputs/inspect/</div>
          <h1>Model comparison</h1>
          <div className="sub">
            {models.length} models · {formats.length} format{formats.length !== 1 ? 's' : ''} · {records.length} samples
          </div>
        </div>
      </div>

      {/* Key findings strip */}
      {best && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 20 }}>
          <div className="card" style={{ padding: '14px 18px' }}>
            <div className="lb-eyebrow" style={{ color: 'var(--lb-green-700)', marginBottom: 6 }}>Best model</div>
            <div style={{ font: '600 22px var(--lb-font-mono)', color: best.color, marginBottom: 4 }}>
              {(best.avgScore * 100).toFixed(1)}%
            </div>
            <div style={{ font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>
              {best.name} avg across {formats.length} format{formats.length !== 1 ? 's' : ''}
            </div>
          </div>
          {second && (
            <div className="card" style={{ padding: '14px 18px' }}>
              <div className="lb-eyebrow" style={{ color: '#1b4a8c', marginBottom: 6 }}>Gap to 2nd</div>
              <div style={{ font: '600 22px var(--lb-font-mono)', color: best.avgScore >= second.avgScore ? 'var(--lb-green-700)' : 'var(--lb-error)', marginBottom: 4 }}>
                {best.avgScore >= second.avgScore ? '+' : ''}{((best.avgScore - second.avgScore) * 100).toFixed(1)}%
              </div>
              <div style={{ font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>
                {best.name} vs {second.name}
              </div>
            </div>
          )}
          {majorityAvg != null && best && (
            <div className="card" style={{ padding: '14px 18px' }}>
              <div className="lb-eyebrow" style={{ color: '#8a5d12', marginBottom: 6 }}>vs Majority baseline</div>
              <div style={{ font: '600 22px var(--lb-font-mono)', color: best.avgScore > majorityAvg ? 'var(--lb-green-700)' : 'var(--lb-error)', marginBottom: 4 }}>
                {best.avgScore > majorityAvg ? '+' : ''}{((best.avgScore - majorityAvg) * 100).toFixed(1)}%
              </div>
              <div style={{ font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>
                {best.name} above majority class
              </div>
            </div>
          )}
        </div>
      )}

      {/* Grouped bar chart */}
      {(() => {
        const visibleModels = showBaselines
          ? models
          : models.filter(m => !BASELINE_IDS.includes(m.id));
        const visibleStats = showBaselines
          ? modelStats
          : modelStats.filter(m => !BASELINE_IDS.includes(m.id));
        return (
      <>
      <div className="card" style={{ marginBottom: 20, padding: '18px 24px 22px' }}>
        <div className="head" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <h3>Accuracy by format</h3>
            <p className="sub">
              {showBaselines ? 'all models' : 'models only'} · score per question format · higher is better
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowBaselines(v => !v)}
            style={{
              font: '500 11px var(--lb-font-sans)',
              padding: '6px 12px',
              border: '1px solid var(--lb-border)',
              borderRadius: 4,
              background: showBaselines ? 'var(--lb-bg-2, #f5f5f5)' : 'var(--lb-green-500)',
              color: showBaselines ? 'var(--lb-fg-1)' : '#fff',
              cursor: 'pointer',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              flexShrink: 0,
            }}
            title="Toggle baseline visibility"
          >
            {showBaselines ? 'Hide baselines' : 'Show baselines'}
          </button>
        </div>
        <GroupedBarChart matrix={matrix} models={visibleModels} formats={formats} />
      </div>

      {/* Per-model cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${Math.min(visibleStats.length, 4)}, 1fr)`,
        gap: 14,
      }}>
        {visibleStats.map(m => (
          <ModelCard
            key={m.id}
            model={m}
            formatScores={m.formatScores}
            formats={formats}
            avgScore={m.avgScore}
            nCorrect={m.nCorrect}
            nTotal={m.nTotal}
          />
        ))}
      </div>
      </>
        );
      })()}
    </>
  );
};

Object.assign(window, { CompareView });
