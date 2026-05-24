// Sidebar — reordered: Trust → Compare → Live runs → Tasks → Datasets → Settings.
// Brand shows team (SD hackers) + product (LongevityBench).

const Sidebar = ({ view, setView, runsCount, liveCount }) => {
  const item = (id, icon, label, count, isLive) => (
    <div className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => setView(id)}>
      <Icon name={icon} className="ico" />
      <span>{label}</span>
      {isLive && count > 0 && (
        <span className="count" style={{ color: 'var(--lb-green-700)', background: 'var(--lb-green-50)', padding: '1px 6px', borderRadius: 3 }}>
          <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: 'var(--lb-green-500)', marginRight: 4, animation: 'pulse 1.4s ease-in-out infinite' }} />
          {count} live
        </span>
      )}
      {!isLive && count != null && <span className="count">{count}</span>}
    </div>
  );

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="sym">LB</div>
        <div className="word">
          <span className="a">LongevityBench</span>
          <span className="b">SD hackers · Track 01</span>
        </div>
      </div>

      <div className="nav-section">
        <p className="heading">Evaluate</p>
        {item('matrix',  'table',  'Eval matrix')}
        {item('compare', 'chart',  'Compare models')}
        {item('answers', 'table',  'Answers')}
        {item('gap',     'chart',  'Gap analysis')}
        {item('runs',    'play',   'Live runs', liveCount, true)}
        {item('trust',   'target', 'Trust & reasoning')}
      </div>

      <div className="nav-section">
        <p className="heading">Library</p>
        {item('tasks',   'flask',  'Tasks', 6)}
        {item('models',  'layers', 'Models', 4)}
        {item('senescence', 'flask', 'Senescence', '298')}
        {item('lipidomics', 'flask', 'Lipidomics', '285')}
      </div>

      <div className="nav-section">
        <p className="heading">System</p>
        {item('settings', 'settings', 'Settings')}
      </div>

      <div className="footer">
        Caltech Longevity Hackathon · Track 01
        <div className="sponsor">
          <span style={{ color: 'var(--lb-fg-3)' }}>Sponsor</span>
          <img src="../../assets/insilico-medicine-logo.svg" alt="Insilico Medicine" />
        </div>
      </div>
    </aside>
  );
};

Object.assign(window, { Sidebar });
