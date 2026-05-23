// Primitives + tiny components — Icon, Button, Badge, Pill, MetricCard
// All globals are exported to window at end so other Babel scripts can use them.

const Icon = ({ name, size = 16, stroke = 1.5, className = '', style = {} }) => {
  const paths = {
    play: <polygon points="6 4 20 12 6 20 6 4" />,
    pause: <g><rect x="6" y="5" width="4" height="14" /><rect x="14" y="5" width="4" height="14" /></g>,
    stop: <rect x="6" y="6" width="12" height="12" rx="1" />,
    search: <g><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></g>,
    check: <polyline points="20 6 9 17 4 12" />,
    close: <g><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></g>,
    plus: <g><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></g>,
    chev: <polyline points="6 9 12 15 18 9" />,
    chevR: <polyline points="9 6 15 12 9 18" />,
    download: <g><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></g>,
    upload: <g><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></g>,
    file: <g><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></g>,
    flask: <g><path d="M9 3v6L4 19a2 2 0 0 0 1.7 3h12.6A2 2 0 0 0 20 19L15 9V3" /><line x1="9" y1="3" x2="15" y2="3" /></g>,
    chart: <g><path d="M3 3v18h18" /><polyline points="7 14 11 10 15 13 20 7" /></g>,
    table: <g><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="9" x2="9" y2="21" /></g>,
    layers: <g><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></g>,
    box: <g><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></g>,
    settings: <g><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.65 1.65 0 0 0-1.8-.3 1.65 1.65 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.65 1.65 0 0 0-1-1.5 1.65 1.65 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.65 1.65 0 0 0 .3-1.8 1.65 1.65 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.65 1.65 0 0 0 1.5-1 1.65 1.65 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.65 1.65 0 0 0 1.8.3h0a1.65 1.65 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.65 1.65 0 0 0 1 1.5h0a1.65 1.65 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.65 1.65 0 0 0-.3 1.8v0a1.65 1.65 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.65 1.65 0 0 0-1.5 1z" /></g>,
    refresh: <g><polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" /><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" /></g>,
    bookOpen: <g><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></g>,
    history: <g><path d="M3 3v5h5" /><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" /><polyline points="12 7 12 12 16 14" /></g>,
    info: <g><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></g>,
    alert: <g><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></g>,
    target: <g><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></g>,
    dot: <circle cx="12" cy="12" r="3" />,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      {paths[name] || null}
    </svg>
  );
};

const Button = ({ children, variant = 'secondary', size, icon, onClick, disabled, className = '' }) => (
  <button
    className={`btn ${variant} ${size === 'small' ? 'small' : ''} ${className}`}
    onClick={onClick} disabled={disabled}
  >
    {icon && <Icon name={icon} className="ico" />}
    {children}
  </button>
);

const Badge = ({ kind = 'neutral', pulse, children }) => (
  <span className={`badge ${kind} ${pulse ? 'dot-pulse' : ''}`}>{children}</span>
);

const Pill = ({ brand, children }) => (
  <span className={`pill ${brand ? 'brand' : ''}`}>{children}</span>
);

const Delta = ({ value, suffix = '' }) => {
  const positive = value > 0;
  const sign = positive ? '+' : (value < 0 ? '−' : '');
  return (
    <span className={`delta ${positive ? 'up' : 'down'}`}>
      {sign}{Math.abs(value)}{suffix}
    </span>
  );
};

const MetricCard = ({ label, value, sub, delta, deltaSuffix }) => (
  <div className="metric">
    <div className="lbl">{label}</div>
    <div className="val">
      {value}
      {delta != null && <Delta value={delta} suffix={deltaSuffix} />}
    </div>
    {sub && <div className="sub">{sub}</div>}
  </div>
);

Object.assign(window, { Icon, Button, Badge, Pill, Delta, MetricCard });
