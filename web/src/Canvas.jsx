import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowUpRight, Bookmark, Check, ChevronRight, CircleHelp, Focus, Grip, Hand, LayoutGrid, Lightbulb, Maximize, MessageCircle, Minus, MoreHorizontal, Pencil, Plus, Search, StickyNote, X } from 'lucide-react';
import { dateLabel, safeUrl, siteName } from './api';

export const KIND = {
  observation: { label: '观察', eyebrow: 'AN OBSERVATION', icon: Search, color: 'sage' },
  idea: { label: '创意假说', eyebrow: 'AN IDEA TO EXPLORE', icon: Lightbulb, color: 'rose' },
  source: { label: '来源材料', eyebrow: 'FROM THE SOURCE', icon: ArrowUpRight, color: 'cream' },
  question: { label: '还想弄清楚', eyebrow: 'AN OPEN QUESTION', icon: CircleHelp, color: 'sand' },
  note: { label: '案头笔记', eyebrow: 'A WORKING NOTE', icon: StickyNote, color: 'lavender' },
  calendar: { label: '时间与节点', eyebrow: 'ON THE CALENDAR', icon: Bookmark, color: 'sand' },
};
export const SourceContext = createContext([]);

export function readableText(text, sources = []) {
  return String(text || '').replace(/src_[A-Za-z0-9_-]+/g, id => sources.find(source => source.id === id)?.title || '关联来源');
}

function inline(text) {
  return String(text).split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>;
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link && safeUrl(link[2])) return <a key={index} href={safeUrl(link[2])} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>{link[1]}</a>;
    return part;
  });
}

export function RichText({ text, className = '' }) {
  const sources = useContext(SourceContext);
  const lines = readableText(text, sources).split('\n');
  return <div className={`rich-text ${className}`}>{lines.map((line, i) => {
    if (!line.trim()) return <div className="text-gap" key={i} />;
    if (/^#{1,4}\s/.test(line)) return <h4 key={i}>{inline(line.replace(/^#{1,4}\s+/, ''))}</h4>;
    if (/^\s*[-*•]\s/.test(line)) return <p className="text-bullet" key={i}>{inline(line.replace(/^\s*[-*•]\s+/, ''))}</p>;
    return <p key={i}>{inline(line)}</p>;
  })}</div>;
}

function SourceImage({ source }) {
  const [failed, setFailed] = useState(false);
  const url = safeUrl(source?.image_url);
  useEffect(() => setFailed(false), [url]);
  if (!url || failed) return null;
  return <figure className="source-image"><img src={url} alt={source.title || '来源图像'} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /><figcaption><ArrowUpRight size={11} /> 来源图片 · {siteName(source.url)}</figcaption></figure>;
}

function DeskCard({ card, sources, selected, dragging, onSelect, onDrag, onOpen, onEdit, onStatus, onAsk, register }) {
  const meta = KIND[card.kind] || KIND.note;
  const Icon = meta.icon;
  const related = (card.source_ids || []).map(id => sources.find(source => source.id === id)).filter(Boolean);
  const source = related.find(item => item.image_url) || related[0];
  const draftQuote = card.kind === 'idea' ? String(card.body || '').split(/\n\s*\n/).find(paragraph => /^[“「"]/.test(paragraph.trim())) : null;
  const [menu, setMenu] = useState(false);
  return <article
    ref={element => register(card.id, element)}
    className={`desk-card ${card.kind || 'note'} paper-${card.kind === 'idea' && card.color === 'cream' ? 'rose' : card.color || meta.color} ${selected ? 'selected' : ''} ${dragging ? 'dragging' : ''} ${card.status === 'kept' ? 'is-kept' : ''}`}
    style={{ width: card.width || 320, transform: `translate(${card.x ?? 32}px, ${card.y ?? 64}px)`, zIndex: dragging ? 30 : selected ? 20 : 2 }}
    data-card-id={card.id}
    onClick={event => { event.stopPropagation(); onSelect(card.id, event.shiftKey); }}
    aria-label={`${meta.label}：${card.title}`}
    tabIndex={0}
    onKeyDown={event => { if (event.key === 'Enter') onOpen(card.id); }}
  >
    {(card.kind === 'observation' || card.kind === 'question') && <div className="paper-tape" aria-hidden="true" />}
    <div className="card-grip" onPointerDown={event => onDrag(event, card)} title="拖动卡片">
      <span className="card-kind"><Icon size={13} strokeWidth={1.8} />{meta.label}</span>
      <span className="card-heading-actions">{card.status === 'kept' && <Bookmark size={13} fill="currentColor" aria-label="已保留" />}<Grip size={14} className="grip-icon" /></span>
    </div>
    {card.kind === 'source' && <SourceImage source={source} />}
    <div className="card-content" onDoubleClick={event => { event.stopPropagation(); onEdit(card); }}>
      <span className="card-eyebrow">{meta.eyebrow}</span>
      <h3>{card.title}</h3>
      {draftQuote && <blockquote className="idea-draft-quote"><span>正文草稿</span><RichText text={draftQuote} /></blockquote>}
      <RichText text={draftQuote ? card.body.replace(draftQuote, '').trim() : card.body} className={`card-body ${draftQuote ? 'with-draft-quote' : ''}`} />
      {card.kind === 'idea' && <span className="idea-caption">一个可继续推敲的方向</span>}
    </div>
    <div className="card-footer">
      <button className="source-link" onClick={event => { event.stopPropagation(); onOpen(card.id); }}><span>{card.kind === 'source' && source ? (source.origin === 'replay' ? 'Replay 材料' : siteName(source.url)) : related.length ? `${related.length} 份依据` : '展开笔记'}</span><ChevronRight size={13} /></button>
      <div className="card-quick-actions">
        <button className={`icon-button tiny ${card.status === 'kept' ? 'active' : ''}`} title={card.status === 'kept' ? '取消保留' : '保留这个方向'} aria-label={card.status === 'kept' ? '取消保留' : '保留这个方向'} onClick={event => { event.stopPropagation(); onStatus(card, card.status === 'kept' ? 'draft' : 'kept'); }}><Bookmark size={14} fill={card.status === 'kept' ? 'currentColor' : 'none'} /></button>
        <div className="card-menu-anchor">
          <button className="icon-button tiny" aria-label="卡片操作" aria-expanded={menu} onClick={event => { event.stopPropagation(); setMenu(!menu); }}><MoreHorizontal size={16} /></button>
          {menu && <><button className="menu-dismiss" aria-label="关闭卡片菜单" onClick={event => { event.stopPropagation(); setMenu(false); }} /><div className="card-menu" onClick={e => e.stopPropagation()}>
            <button onClick={() => { setMenu(false); onAsk(card.id); }}><MessageCircle size={14} />围绕这张继续</button>
            <button onClick={() => { setMenu(false); onEdit(card); }}><Pencil size={14} />直接修改</button>
            <button onClick={() => { setMenu(false); onStatus(card, 'archived'); }}><ArrowDownToLine size={14} />先放下</button>
          </div></>}
        </div>
      </div>
    </div>
  </article>;
}

export default function Canvas({ task, viewport, onViewport, selected, onSelect, onPositions, onOpen, onEdit, onStatus, onAsk, onStart, onAddSources, onNew, running, configured, busy, focusRef, showArchived }) {
  const rootRef = useRef(null);
  const nodes = useRef(new Map());
  const dragRef = useRef(null);
  const viewportRef = useRef(viewport);
  const [draggingId, setDraggingId] = useState(null);
  const [panning, setPanning] = useState(false);
  const [space, setSpace] = useState(false);
  const [localPositions, setLocalPositions] = useState({});
  const visible = (task?.cards || []).filter(card => showArchived ? card.status === 'archived' : card.status !== 'archived');
  viewportRef.current = viewport;
  const register = useCallback((id, element) => { if (element) nodes.current.set(id, element); else nodes.current.delete(id); }, []);

  const changeZoom = useCallback((zoom, clientX, clientY) => {
    const bounds = rootRef.current?.getBoundingClientRect();
    if (!bounds) return;
    const old = viewportRef.current;
    const next = Math.min(2, Math.max(0.25, zoom));
    const px = (clientX ?? bounds.left + bounds.width / 2) - bounds.left;
    const py = (clientY ?? bounds.top + bounds.height / 2) - bounds.top;
    onViewport({ x: px - (px - old.x) / old.zoom * next, y: py - (py - old.y) / old.zoom * next, zoom: next });
  }, [onViewport]);

  useEffect(() => {
    const element = rootRef.current;
    const wheel = event => {
      if (event.target.closest('button, input, textarea, .welcome-card, .canvas-empty, .canvas-controls')) return;
      event.preventDefault();
      if (event.ctrlKey || event.metaKey) changeZoom(viewportRef.current.zoom * Math.exp(-event.deltaY * 0.008), event.clientX, event.clientY);
      else onViewport({ ...viewportRef.current, x: viewportRef.current.x - event.deltaX, y: viewportRef.current.y - event.deltaY });
    };
    element?.addEventListener('wheel', wheel, { passive: false });
    return () => element?.removeEventListener('wheel', wheel);
  }, [changeZoom, onViewport]);

  useEffect(() => {
    const down = event => {
      if (event.target.closest('input, textarea, button, a, [role="dialog"], [contenteditable="true"]')) return;
      if (event.code === 'Space') { event.preventDefault(); setSpace(true); }
      if (event.key === 'Escape') onSelect(null);
    };
    const up = event => { if (event.code === 'Space') setSpace(false); };
    const blur = () => setSpace(false);
    window.addEventListener('keydown', down); window.addEventListener('keyup', up); window.addEventListener('blur', blur);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('blur', blur); };
  }, [onSelect]);

  useEffect(() => { setLocalPositions({}); }, [task?.id, task?.updated_at]);

  function startPan(event) {
    if (event.button !== 0 && event.button !== 1) return;
    if (event.target.closest('button, input, textarea, .canvas-empty, .welcome-card, .canvas-controls')) return;
    if (event.target.closest('.desk-card') && !space && event.button !== 1 && !event.altKey) return;
    event.preventDefault();
    rootRef.current.setPointerCapture(event.pointerId);
    dragRef.current = { mode: 'pan', startX: event.clientX, startY: event.clientY, viewport: { ...viewportRef.current }, moved: false };
    setPanning(true);
  }

  function startCardDrag(event, card) {
    event.stopPropagation();
    if (space || event.button === 1 || event.altKey) { startPan(event); return; }
    if (event.button !== 0) return;
    event.preventDefault();
    rootRef.current.setPointerCapture(event.pointerId);
    const ids = selected.includes(card.id) ? selected : [card.id];
    if (!selected.includes(card.id)) onSelect(card.id, event.shiftKey);
    const positions = visible.filter(item => ids.includes(item.id)).map(item => ({ id: item.id, x: item.x || 0, y: item.y || 0 }));
    dragRef.current = { mode: 'card', startX: event.clientX, startY: event.clientY, positions, moved: false };
    setDraggingId(card.id);
  }

  function move(event) {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = event.clientX - drag.startX, dy = event.clientY - drag.startY;
    drag.moved = drag.moved || Math.abs(dx) + Math.abs(dy) > 3;
    if (drag.mode === 'pan') onViewport({ ...drag.viewport, x: drag.viewport.x + dx, y: drag.viewport.y + dy }, false);
    else setLocalPositions(Object.fromEntries(drag.positions.map(item => [item.id, { x: Math.round(item.x + dx / viewportRef.current.zoom), y: Math.round(item.y + dy / viewportRef.current.zoom) }])));
  }

  function end(event) {
    const drag = dragRef.current;
    if (!drag) return;
    if (drag.mode === 'card' && drag.moved) {
      const dx = (event.clientX - drag.startX) / viewportRef.current.zoom;
      const dy = (event.clientY - drag.startY) / viewportRef.current.zoom;
      onPositions(drag.positions.map(item => ({ id: item.id, x: Math.round(item.x + dx), y: Math.round(item.y + dy) })));
    }
    if (drag.mode === 'pan') {
      onViewport(viewportRef.current);
      if (!drag.moved) onSelect(null);
    }
    if (rootRef.current.hasPointerCapture(event.pointerId)) rootRef.current.releasePointerCapture(event.pointerId);
    dragRef.current = null; setDraggingId(null); setPanning(false);
  }

  function fit(ids) {
    const cards = ids?.length ? visible.filter(item => ids.includes(item.id)) : visible;
    if (!cards.length || !rootRef.current) { onViewport({ x: 0, y: 0, zoom: 1 }); return; }
    const bounds = rootRef.current.getBoundingClientRect();
    const left = Math.min(...cards.map(c => c.x || 0));
    const top = Math.min(...cards.map(c => c.y || 0));
    const right = Math.max(...cards.map(c => (c.x || 0) + (c.width || 320)));
    const bottom = Math.max(...cards.map(c => (c.y || 0) + (nodes.current.get(c.id)?.offsetHeight || 330)));
    const availableHeight = Math.max(260, bounds.height - 170);
    const zoom = Math.min(1.1, Math.max(0.25, Math.min((bounds.width - 96) / (right - left), (availableHeight - 64) / (bottom - top))));
    onViewport({ x: (bounds.width - (right - left) * zoom) / 2 - left * zoom, y: 35 + (availableHeight - (bottom - top) * zoom) / 2 - top * zoom, zoom });
  }

  function arrange() {
    const positions = [];
    const heights = [64, 64, 64];
    const columns = { observation: 0, note: 0, source: 1, idea: 2, question: 0, calendar: 0 };
    const hasImage = card => (card.source_ids || []).some(id => task.sources.find(source => source.id === id)?.image_url);
    const ordered = [...visible].sort((a, b) => {
      if (a.kind === 'source' && b.kind === 'source') return Number(hasImage(b)) - Number(hasImage(a));
      if (a.kind === 'question' || a.kind === 'calendar') return 1;
      if (b.kind === 'question' || b.kind === 'calendar') return -1;
      return 0;
    });
    for (const card of ordered) {
      const column = columns[card.kind] ?? 0;
      positions.push({ id: card.id, x: 32 + column * 360, y: heights[column], width: 320 });
      heights[column] += (nodes.current.get(card.id)?.offsetHeight || 330) + 32;
    }
    onPositions(positions);
    onViewport({ x: 16, y: 8, zoom: Math.max(.5, Math.min(1, ((rootRef.current?.clientWidth || 1200) - 64) / 1072)) });
  }

  if (focusRef) focusRef.current = { fit, arrange };

  return <div ref={rootRef} className={`canvas ${panning || space ? 'is-panning' : ''}`} onPointerDown={startPan} onPointerMove={move} onPointerUp={end} onPointerCancel={end} style={{ backgroundPosition: `${viewport.x}px ${viewport.y}px`, backgroundSize: `${28 * viewport.zoom}px ${28 * viewport.zoom}px` }} aria-label="可拖动缩放的企划桌面">
    <div className="canvas-world" style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}>
      {visible.length > 0 && <div className="desk-section-labels" aria-hidden="true"><span style={{ left: 32 }}>值得留意的观察</span><span style={{ left: 392 }}>素材与出处</span><span style={{ left: 752 }}>让想法长出来</span></div>}
      {visible.map(card => <DeskCard key={card.id} card={{ ...card, ...localPositions[card.id] }} sources={task?.sources || []} selected={selected.includes(card.id)} dragging={draggingId === card.id} onSelect={onSelect} onDrag={startCardDrag} onOpen={onOpen} onEdit={onEdit} onStatus={onStatus} onAsk={onAsk} register={register} />)}
    </div>

    {!task && <div className="welcome-scene"><div className="welcome-intro"><span className="overline">A LITTLE SIGNAL. A NEW DIRECTION.</span><h1>把线索摆上桌，<br />让好想法有处生长。</h1><p>带来一个问题，或几份还没理清的材料。<br />一起看看，哪些值得成为品牌的下一步。</p><button className="primary-button welcome-cta" onClick={onNew}><Plus size={18} /> 开始一次 Radar <ArrowUpRight size={17} /></button><div className="welcome-footnote">从真实材料开始，每一步都可以接着改。</div></div><div className="welcome-paper-stack" aria-hidden="true"><div className="welcome-paper paper-back"><span>从哪一个问题开始？</span><div className="hand-drawn-line" /></div><div className="welcome-paper paper-front"><span className="overline">YOUR NEXT GOOD QUESTION</span><span className="paper-number">01</span><h2>这和我们的品牌，<br />有什么关系？</h2><div className="paper-rule" /><p>观察 · 材料 · 创意</p><div className="paper-corner" /></div><div className="welcome-stamp"><Lightbulb size={22} strokeWidth={1.3} /><span>给想法留一点空间</span></div></div></div>}

    {task && visible.length === 0 && <div className="canvas-empty"><div className="empty-mark"><Search size={26} strokeWidth={1.4} /></div><span className="overline">{showArchived ? 'SET ASIDE, NOT FORGOTTEN' : 'YOUR DESK IS READY'}</span><h2>{showArchived ? '还没有放下的卡片' : running ? '正在从材料里寻找线索' : '桌面准备好了'}</h2><p>{showArchived ? '暂时不合适的方向可以放在这里，以后再回来。' : running ? '调查动作和新卡片会出现在这里，你也可以展开对话查看进展。' : task.sources?.length ? `已有 ${task.sources.length} 份材料。说说想解决什么，我们就从这里开始。` : '先放几份材料，或者直接告诉 Agent 你想调查什么。'}</p>{!showArchived && !running && <div className="empty-actions"><button className="secondary-button" onClick={onAddSources}><Plus size={16} />补充材料</button><button className="primary-button" disabled={!configured || busy} onClick={onStart}>开始调查 <ArrowUpRight size={16} /></button></div>}{!showArchived && !configured && <p className="empty-key-note">模型尚未连接，配置后即可开始真实调查。</p>}</div>}

    {task && visible.length > 0 && !task.messages?.length && !running && !showArchived && <div className="start-investigation"><span><span className="little-dot" />材料已上桌</span><p>从你的问题开始，让 Agent 找出值得聊的线索。</p><button onClick={onStart} disabled={!configured || busy}>开始调查 <ArrowUpRight size={14} /></button></div>}

    {task && <div className="canvas-controls"><div className="zoom-controls"><button className="icon-button" title="缩小" aria-label="缩小" onClick={() => changeZoom(viewport.zoom / 1.2)}><Minus size={15} /></button><button className="zoom-value" title="恢复 100%" onClick={() => changeZoom(1)}>{Math.round(viewport.zoom * 100)}%</button><button className="icon-button" title="放大" aria-label="放大" onClick={() => changeZoom(viewport.zoom * 1.2)}><Plus size={15} /></button></div><div className="control-divider" /><button className="icon-button" title="回到全部内容" aria-label="回到全部内容" onClick={() => fit()}><Maximize size={16} /></button><button className="icon-button" title="聚焦选中卡片" aria-label="聚焦选中卡片" disabled={!selected.length} onClick={() => fit(selected)}><Focus size={16} /></button><button className="icon-button" title="整理桌面" aria-label="整理桌面" onClick={arrange} disabled={!visible.length}><LayoutGrid size={16} /></button></div>}
    {task && <span className="canvas-instruction"><Hand size={12} />拖动空白处移动 · ⌘ / Ctrl + 滚轮缩放 · Shift 多选</span>}
  </div>;
}
