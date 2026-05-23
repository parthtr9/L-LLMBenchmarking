// TopBar — breadcrumb, global search, action buttons.

const TopBar = ({ crumbs = [], onNewRun, onRefresh }) => (
  <header className="topbar">
    <div className="crumb">
      {crumbs.map((c, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="sep">/</span>}
          <span className={`${i === crumbs.length - 1 ? 'here' : ''} ${c.mono ? 'id' : ''}`}>{c.label}</span>
        </React.Fragment>
      ))}
    </div>
    <div className="search">
      <Icon name="search" className="ico" />
      <input placeholder="Search runs, task IDs, gene symbols…" />
      <span className="kbd">⌘K</span>
    </div>
    <div className="right">
      <Button variant="ghost" size="small" icon="refresh" onClick={onRefresh}>Refresh</Button>
      <Button variant="primary" icon="plus" onClick={onNewRun}>New run</Button>
      <div className="profile">PR</div>
    </div>
  </header>
);

Object.assign(window, { TopBar });
