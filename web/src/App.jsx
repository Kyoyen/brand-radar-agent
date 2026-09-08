import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, ArrowUp, ArrowUpRight, BookOpen, Check, ChevronDown, ChevronRight, CircleAlert, Clock3, Download, FileText, Focus, FolderOpen, LayoutGrid, LoaderCircle, MessageCircle, MoreHorizontal, PanelLeftClose, Pencil, Plus, Radio, RotateCcw, Settings2, Square, X } from 'lucide-react';
import Canvas, { KIND, SourceContext } from './Canvas';
import { BrandModal, Drawer, EditCardModal, HistoryModal, Modal, NewTaskModal, SettingsModal, SourcesModal } from './Panels';
import { api, dateLabel, visibleActivity } from './api';

function RadarLogo({ small = false }) {
  return <svg className={`radar-logo ${small ? 'small' : ''}`} viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="18" /><circle cx="22" cy="22" r="10" /><path d="M22 22 35 7" /><circle className="radar-center" cx="22" cy="22" r="2.6" /><circle className="radar-signal" cx="31.7" cy="29.2" r="2.7" /></svg>;
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [cases, setCases] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [task, setTask] = useState(null);
  const [brand, setBrand] = useState('');
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState(null);
  const [editCard, setEditCard] = useState(null);
  const [drawer, setDrawer] = useState(null);
  const [drawerCard, setDrawerCard] = useState(null);
  const [selected, setSelected] = useState([]);
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  const [composer, setComposer] = useState('');
  const [toast, setToast] = useState(null);
  const [showArchived, setShowArchived] = useState(false);
  const [exportMenu, setExportMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState('');
  const [saveState, setSaveState] = useState('saved');
  const composerRef = useRef(null);
  const currentRef = useRef(null);
  const viewTimer = useRef(null);
  const toastTimer = useRef(null);
  const focusRef = useRef(null);
  const loadingId = useRef(null);
  const lastPollError = useRef('');
  currentRef.current = task;

  const notify = useCallback((message, type = 'error') => {
    setToast({ message, type });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), type === 'error' ? 8500 : 3500);
  }, []);

  const syncSummary = useCallback(data => {
    if (!data?.id) return;
    setTasks(previous => [{ id: data.id, title: data.title, status: data.status, updated_at: data.updated_at, card_count: data.cards?.filter(c => c.status !== 'archived').length || 0 }, ...previous.filter(item => item.id !== data.id)].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))));
  }, []);

  const acceptTask = useCallback((data, restoreView = false) => {
    setTask(data);
    currentRef.current = data;
    syncSummary(data);
    if (restoreView) {
      clearTimeout(viewTimer.current);
      setViewport(data.viewport || { x: 0, y: 0, zoom: 1 });
      setSelected([]); setDrawer(null); setDrawerCard(null); setComposer(''); setShowArchived(false); setRenaming(false); setSaveState('saved');
      try { localStorage.setItem('brand-radar:last-task', data.id); } catch { /* Storage can be disabled. */ }
    }
  }, [syncSummary]);

  const openTask = useCallback(async id => {
    loadingId.current = id;
    setLoading(true);
    try {
      const data = await api(`/tasks/${encodeURIComponent(id)}`);
      if (loadingId.current === id) { acceptTask(data, true); setModal(null); }
    } catch (error) { notify(error.message); }
    finally { if (loadingId.current === id) setLoading(false); }
  }, [acceptTask, notify]);

  const bootstrap = useCallback(async () => {
    setLoading(true); setConnectionError('');
    try {
      const [statusData, caseData, taskData, brandData] = await Promise.all([api('/status'), api('/cases'), api('/tasks'), api('/brand')]);
      setStatus(statusData); setCases(caseData.cases || []); setTasks(taskData.tasks || []); setBrand(brandData.content || '');
      let lastId;
      try { lastId = localStorage.getItem('brand-radar:last-task'); } catch { /* Optional preference. */ }
      const latest = (taskData.tasks || []).find(item => item.id === lastId) || taskData.tasks?.[0];
      if (latest) { const data = await api(`/tasks/${encodeURIComponent(latest.id)}`); acceptTask(data, true); }
    } catch (error) { setConnectionError(error.message); }
    finally { setLoading(false); }
  }, [acceptTask]);

  useEffect(() => { bootstrap(); return () => { clearTimeout(viewTimer.current); clearTimeout(toastTimer.current); }; }, [bootstrap]);

  useEffect(() => {
    if (!task?.id || task.status !== 'running') return;
    let cancelled = false, fetching = false;
    const id = task.id;
    const poll = async () => {
      if (fetching) return;
      fetching = true;
      try {
        const data = await api(`/tasks/${encodeURIComponent(id)}`);
        if (!cancelled && currentRef.current?.id === id) { acceptTask(data); lastPollError.current = ''; }
      } catch (error) {
        if (!cancelled && lastPollError.current !== error.message) { notify(error.message); lastPollError.current = error.message; }
      } finally { fetching = false; }
    };
    const timer = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [task?.id, task?.status, acceptTask, notify]);

  useEffect(() => {
    if (!tasks.some(item => item.status === 'running' && item.id !== task?.id)) return;
    const timer = setInterval(async () => {
      try { const data = await api('/tasks'); setTasks(data.tasks || []); } catch { /* Current task surfaces connection errors. */ }
    }, 5000);
    return () => clearInterval(timer);
  }, [tasks.some(item => item.status === 'running' && item.id !== task?.id), task?.id]);

  const saveViewport = useCallback((value, persist = true) => {
    setViewport(value);
    if (!persist || !currentRef.current?.id) return;
    clearTimeout(viewTimer.current);
    const id = currentRef.current.id;
    setSaveState('saving');
    viewTimer.current = setTimeout(async () => {
      try { await api(`/tasks/${encodeURIComponent(id)}`, { method: 'PATCH', body: { viewport: value } }); setSaveState('saved'); }
      catch (error) { setSaveState('error'); notify(error.message); }
    }, 550);
  }, [notify]);

  const patchTask = useCallback(async changes => {
    const current = currentRef.current;
    if (!current) return;
    const optimistic = { ...current, ...changes, cards: changes.cards ? current.cards.map(card => ({ ...card, ...changes.cards.find(change => change.id === card.id) })) : current.cards };
    setTask(optimistic); currentRef.current = optimistic; setSaveState('saving');
    try {
      const data = await api(`/tasks/${encodeURIComponent(current.id)}`, { method: 'PATCH', body: changes });
      if (currentRef.current?.id === current.id) acceptTask(data);
      setSaveState('saved');
      return data;
    } catch (error) {
      setSaveState('error');
      if (currentRef.current?.id === current.id) {
        try { acceptTask(await api(`/tasks/${encodeURIComponent(current.id)}`)); } catch { /* Keep the visible last known state with an explicit save error. */ }
      }
      throw error;
    }
  }, [acceptTask]);

  async function sendMessage(content, selectedIds = selected, target = task) {
    if (!target || !content.trim() || busy || target.status === 'running') return;
    if (!status?.configured) { setModal('settings'); return; }
    setBusy(true);
    try {
      await api(`/tasks/${encodeURIComponent(target.id)}/messages`, { method: 'POST', body: { content: content.trim(), selected_card_ids: selectedIds } });
      const data = await api(`/tasks/${encodeURIComponent(target.id)}`);
      acceptTask(data);
      setComposer(''); setSelected([]); setDrawer('conversation'); setShowArchived(false);
    } catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  async function createTask(body, start) {
    if (busy) return;
    setBusy(true);
    try {
      const data = await api('/tasks', { method: 'POST', body });
      acceptTask(data, true); setModal(null);
      if (start) {
        await api(`/tasks/${encodeURIComponent(data.id)}/messages`, { method: 'POST', body: { content: body.question, selected_card_ids: [] } });
        acceptTask(await api(`/tasks/${encodeURIComponent(data.id)}`));
        setDrawer('conversation');
      } else notify('桌面已准备好，材料和想法可以慢慢补。', 'success');
    } catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  async function addSource(body) {
    if (!task || busy) return;
    setBusy(true);
    try {
      const data = await api(`/tasks/${encodeURIComponent(task.id)}/sources`, { method: 'POST', body });
      acceptTask(data); setModal(null); setDrawer('sources'); notify('材料已放上桌。', 'success');
    } catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  async function saveBrand(content) {
    setBusy(true);
    try { const data = await api('/brand', { method: 'PUT', body: { content } }); setBrand(data.content ?? content); setModal(null); notify('品牌档案已保存。', 'success'); }
    catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  async function stopTask() {
    if (!task || busy) return;
    setBusy(true);
    try { await api(`/tasks/${encodeURIComponent(task.id)}/stop`, { method: 'POST' }); acceptTask(await api(`/tasks/${encodeURIComponent(task.id)}`)); }
    catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  const selectCard = useCallback((id, multi = false) => {
    if (!id) { setSelected([]); return; }
    setSelected(previous => multi ? previous.includes(id) ? previous.filter(item => item !== id) : [...previous, id] : [id]);
  }, []);

  const openCard = useCallback(id => { setDrawerCard(id); setDrawer('card'); setSelected([id]); }, []);
  const askCard = useCallback(id => { setSelected([id]); composerRef.current?.focus(); }, []);
  const savePositions = useCallback(cards => { patchTask({ cards }).catch(error => notify(error.message)); }, [patchTask, notify]);

  async function changeCardStatus(card, newStatus) {
    try {
      await patchTask({ cards: [{ id: card.id, status: newStatus }] });
      if (newStatus === 'archived') { setSelected(previous => previous.filter(id => id !== card.id)); notify('先放下了，需要时可以从「已放下」找回来。', 'success'); }
    } catch (error) { notify(error.message); }
  }

  async function saveCard(changes) {
    setBusy(true);
    try { await patchTask({ cards: [changes] }); setEditCard(null); notify('已保存你的修改。', 'success'); }
    catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  async function renameTask() {
    if (!renaming) return;
    setRenaming(false);
    if (!draftTitle.trim() || draftTitle.trim() === task.title) return;
    try { await patchTask({ title: draftTitle.trim() }); } catch (error) { notify(error.message); }
  }

  async function refreshStatus() {
    setBusy(true);
    try { setStatus(await api('/status')); notify('配置状态已更新。', 'success'); }
    catch (error) { notify(error.message); }
    finally { setBusy(false); }
  }

  const running = task?.status === 'running';
  const activeCards = task?.cards?.filter(card => card.status !== 'archived') || [];
  const archivedCount = task?.cards?.filter(card => card.status === 'archived').length || 0;
  const chosenCards = (task?.cards || []).filter(card => selected.includes(card.id));
  const latestActivity = visibleActivity(task).at(-1);
  const replay = task?.sources?.some(source => source.origin === 'replay');

  return <SourceContext.Provider value={task?.sources || []}><div className="app-shell">
    <aside className="sidebar"><button className="brand-lockup" onClick={() => { if (!task) setModal('new'); else focusRef.current?.fit(); }} aria-label="Brand Radar，回到桌面内容"><RadarLogo /><span><strong>BRAND RADAR</strong><small>你的营销企划桌面</small></span></button>
      <button className="new-radar-button" onClick={() => setModal('new')} disabled={!!connectionError}><span className="plus-circle"><Plus size={14} /></span><span>新建 Radar</span><span className="new-shortcut"><ArrowUpRight size={15} /></span></button>
      <nav className="primary-nav" aria-label="主导航"><button onClick={() => setModal('history')} className={modal === 'history' ? 'active' : ''}><Clock3 size={18} /><span>历史桌面</span><span className="nav-count">{tasks.length || ''}</span></button><button onClick={() => setModal('brand')} disabled={!!connectionError}><BookOpen size={18} /><span>品牌档案</span></button><button onClick={() => setModal('settings')}><Settings2 size={18} /><span>设置</span></button></nav>
      <div className="recent-tasks"><div className="sidebar-section-heading"><span>最近的桌面</span><button className="icon-button" title="查看所有历史" aria-label="查看所有历史" onClick={() => setModal('history')}><MoreHorizontal size={15} /></button></div>{tasks.slice(0, 6).map(item => <button className={`recent-task ${task?.id === item.id ? 'current' : ''}`} key={item.id} onClick={() => openTask(item.id)} title={item.title}><span className={`task-marker ${item.status}`} /><span>{item.title}</span>{item.status === 'running' && <LoaderCircle size={12} className="spinning" />}</button>)}{!tasks.length && <p className="sidebar-empty">好问题值得<br />一张自己的桌面。</p>}</div>
      <div className="sidebar-bottom"><button className="brand-profile-card" onClick={() => setModal('brand')} disabled={!!connectionError}><span className="brand-avatar"><BookOpen size={18} /></span><span><strong>品牌是判断的起点</strong><small>记录取舍，也收藏好例子</small></span><ChevronRight size={14} /></button><button className="connection-status" onClick={() => setModal('settings')}><span className={`status-dot ${status?.configured ? 'ready' : ''}`} /><span>{connectionError ? '本地服务未连接' : !status ? '正在连接桌面' : status.configured ? `${status.provider || '模型'} · 已配置` : '模型尚未配置'}</span><Settings2 size={12} /></button><div className="sidebar-signoff">A place for your next good idea.</div></div>
    </aside>

    <main className="workspace"><header className="workspace-header"><div className="workspace-title"><div className="workspace-breadcrumb"><span>企划桌面</span>{task && <><ChevronRight size={11} /><span>{replay ? 'Replay 材料' : task.brand || '本次调查'}</span></>}</div>{task ? <div className="title-row">{renaming ? <input className="rename-input" aria-label="桌面名称" value={draftTitle} autoFocus onChange={event => setDraftTitle(event.target.value)} onBlur={renameTask} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') { setRenaming(false); } }} maxLength={100} /> : <button className="title-button" title="修改桌面名称" onClick={() => { setDraftTitle(task.title); setRenaming(true); }}><h1>{task.title}</h1><Pencil size={13} /></button>}<span className={`save-state ${saveState}`}>{saveState === 'saving' ? '保存中' : saveState === 'error' ? '未保存' : <><Check size={11} />已保存</>}</span></div> : <h1 className="home-title">欢迎回到你的企划桌面</h1>}</div>
      <div className="header-actions">{task && <><button className={`secondary-button compact ${drawer === 'sources' ? 'active' : ''}`} onClick={() => setModal('sources')}><Plus size={15} /><span>补材料</span></button><button className={`header-icon-button ${drawer === 'conversation' ? 'active' : ''}`} title="对话与调查记录" aria-label="对话与调查记录" onClick={() => setDrawer(drawer === 'conversation' ? null : 'conversation')}><MessageCircle size={18} />{running && <span className="button-running-dot" />}</button><div className="export-menu-anchor"><button className="header-icon-button" title="导出这份工作" aria-label="导出这份工作" aria-expanded={exportMenu} onClick={() => setExportMenu(!exportMenu)}><Download size={18} /></button>{exportMenu && <><button className="menu-dismiss" aria-label="关闭导出菜单" onClick={() => setExportMenu(false)} /><div className="export-menu"><span>带走这份工作</span><a href={`/api/tasks/${encodeURIComponent(task.id)}/export?format=html`} download onClick={() => setExportMenu(false)}><FileText size={15} />网页 · HTML</a><a href={`/api/tasks/${encodeURIComponent(task.id)}/export?format=md`} download onClick={() => setExportMenu(false)}><ArrowDownToLine size={15} />文稿 · Markdown</a></div></>}</div></>}<span className="workspace-avatar" title="本机工作空间">B<span /></span></div>
    </header>

    {task && <div className="desk-toolbar"><div className="desk-tabs"><button className={!showArchived ? 'active' : ''} onClick={() => { setShowArchived(false); setSelected([]); }}><LayoutGrid size={13} />桌面<span>{activeCards.length}</span></button><button className={showArchived ? 'active' : ''} onClick={() => { setShowArchived(true); setSelected([]); }}><ArrowDownToLine size={13} />已放下{archivedCount > 0 && <span>{archivedCount}</span>}</button></div><div className="desk-tools"><button onClick={() => setDrawer(drawer === 'sources' ? null : 'sources')}><BookOpen size={13} />{task.sources.length} 份材料</button><span className="toolbar-divider" /><button onClick={() => focusRef.current?.arrange()}><LayoutGrid size={13} />整理</button><button onClick={() => focusRef.current?.fit()}><Focus size={13} />回到内容</button></div></div>}

    {!status?.configured && status && !connectionError && <div className="key-notice"><Radio size={14} /><span>可以先准备材料。配置模型 API Key 后，开始真实调查。</span><button onClick={() => setModal('settings')}>查看设置<ArrowUpRight size={12} /></button></div>}
    {connectionError && <div className="connection-error"><CircleAlert size={17} /><p>{connectionError}</p><button className="secondary-button small" onClick={bootstrap}><RotateCcw size={14} />重新连接</button></div>}
    <div className={`desk-layout ${drawer && task ? 'with-drawer' : ''}`}><div className="desk-main"><Canvas task={task} viewport={viewport} onViewport={saveViewport} selected={selected} onSelect={selectCard} onPositions={savePositions} onOpen={openCard} onEdit={setEditCard} onStatus={changeCardStatus} onAsk={askCard} onStart={() => sendMessage(task?.question || '请从现有材料开始，寻找值得继续讨论的品牌观察与企划方向。', [])} onAddSources={() => setModal('sources')} onNew={() => setModal('new')} running={running} configured={status?.configured} busy={busy} focusRef={focusRef} showArchived={showArchived} />

      {loading && <div className="workspace-loading"><LoaderCircle className="spinning" size={22} /><span>正在打开桌面…</span></div>}

      {task && <div className="composer-dock">{task.error && <div className="task-error-banner"><CircleAlert size={16} /><div><strong>这次调查暂时停下了</strong><p>{typeof task.error === 'string' ? task.error : task.error.message || '模型调用未完成，请稍后重试。'}</p></div><button className="icon-button" title="打开调查记录" aria-label="打开调查记录" onClick={() => setDrawer('conversation')}><ChevronRight size={17} /></button></div>}
        {running && <button className="working-strip" onClick={() => setDrawer('conversation')}><span className="working-spinner"><RadarLogo small /></span><span><strong>{latestActivity?.label || '已收到，等待本轮调查开始'}</strong>{latestActivity?.detail && <small>{latestActivity.detail}</small>}</span><span className="working-more">查看进展 <ChevronRight size={13} /></span></button>}
        {task.status === 'stopped' && <div className="stopped-note"><Square size={11} />已停止这轮调查，已完成的内容仍在桌面上。</div>}
        <form className={`composer ${selected.length ? 'has-selection' : ''}`} onSubmit={event => { event.preventDefault(); sendMessage(composer); }}>
          {chosenCards.length > 0 && <div className="composer-selection"><span>围绕</span>{chosenCards.slice(0, 3).map(card => <span className={`selection-chip paper-${card.color || (KIND[card.kind] || KIND.note).color}`} key={card.id}><span>{card.title}</span><button type="button" aria-label={`取消选择${card.title}`} onClick={() => setSelected(previous => previous.filter(id => id !== card.id))}><X size={11} /></button></span>)}{chosenCards.length > 3 && <span>等 {chosenCards.length} 张卡片</span>}<button className="clear-selection" type="button" title="取消全部选择" aria-label="取消全部选择" onClick={() => setSelected([])}><X size={13} /></button></div>}
          <div className="composer-main"><button className="composer-attach" type="button" title="补充材料" aria-label="补充材料" onClick={() => setModal('sources')}><Plus size={19} /></button><textarea ref={composerRef} rows={1} aria-label="给 Agent 的消息" value={composer} onChange={event => { setComposer(event.target.value); event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 144)}px`; }} onKeyDown={event => { if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); sendMessage(composer); } }} placeholder={running ? '先写下你的想法，等这轮完成后继续…' : selected.length ? '这个角度不错，但…' : '问 Agent、补充想法，或选中卡片继续推敲…'} />{running ? <button type="button" className="send-button stop-button" title="停止这轮调查" aria-label="停止这轮调查" disabled={busy} onClick={stopTask}><Square size={14} fill="currentColor" /></button> : <button type="submit" className="send-button" title={status?.configured ? '发送 · ⌘ / Ctrl + Enter' : '请先配置模型'} aria-label="发送消息" disabled={busy || !composer.trim() || !status?.configured}>{busy ? <LoaderCircle size={18} className="spinning" /> : <ArrowUp size={20} />}</button>}</div>
          <div className="composer-foot"><span><span className={`tiny-status-dot ${running ? 'working' : ''}`} />{running ? '调查中 · 可随时停止' : selected.length ? '你的选择会一起交给 Agent' : '一个问题，一起推敲'}</span><span>⌘ / Ctrl ↵ 发送</span></div>
        </form>
      </div>}
    </div>{drawer && task && <Drawer task={task} mode={drawer} cardId={drawerCard} onMode={setDrawer} onClose={() => setDrawer(null)} onEdit={setEditCard} onStatus={changeCardStatus} onAsk={askCard} onAddSources={() => setModal('sources')} onFocus={id => { setSelected([id]); focusRef.current?.fit([id]); }} />}</div>
    </main>

    {toast && <div className={`toast ${toast.type}`} role={toast.type === 'error' ? 'alert' : 'status'}>{toast.type === 'error' ? <CircleAlert size={17} /> : <Check size={17} />}<span>{toast.message}</span><button aria-label="关闭提示" onClick={() => setToast(null)}><X size={15} /></button></div>}
    {modal === 'new' && <NewTaskModal cases={cases} configured={status?.configured} busy={busy} onCreate={createTask} onClose={() => setModal(null)} />}
    {modal === 'sources' && task && <SourcesModal busy={busy} onAdd={addSource} onClose={() => setModal(null)} />}
    {modal === 'brand' && <BrandModal content={brand} busy={busy} onSave={saveBrand} onClose={() => setModal(null)} />}
    {modal === 'settings' && <SettingsModal status={status} busy={busy} onRefresh={refreshStatus} onClose={() => setModal(null)} />}
    {modal === 'history' && <HistoryModal tasks={tasks} currentId={task?.id} onSelect={openTask} onClose={() => setModal(null)} />}
    {editCard && <EditCardModal key={editCard.id} card={editCard} busy={busy} onSave={saveCard} onClose={() => setEditCard(null)} />}
  </div></SourceContext.Provider>;
}
