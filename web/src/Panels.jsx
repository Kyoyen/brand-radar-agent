import React, { useContext, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen, Check, ChevronRight, CircleHelp, Clock3, Copy, Download, ExternalLink, FileText, FolderOpen, Image, Link, LoaderCircle, MessageCircle, Pencil, Plus, Radio, RotateCcw, Search, Settings2, Upload, X } from 'lucide-react';
import { KIND, RichText, SourceContext, readableText } from './Canvas';
import { dateLabel, safeUrl, siteName, visibleActivity } from './api';

export function Modal({ title, subtitle, children, onClose, wide = false, className = '' }) {
  const dialog = useRef(null);
  useEffect(() => {
    const before = document.activeElement;
    const element = dialog.current;
    (element?.querySelector('textarea, input:not([type="file"])') || element?.querySelector('button'))?.focus();
    const keydown = event => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Tab') {
        const focusable = [...element.querySelectorAll('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]')].filter(item => item.offsetParent !== null);
        const first = focusable[0], last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    window.addEventListener('keydown', keydown);
    return () => { window.removeEventListener('keydown', keydown); before?.focus?.(); };
  }, []);
  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className={`modal ${wide ? 'modal-wide' : ''} ${className}`} role="dialog" aria-modal="true" aria-label={title} ref={dialog}><header className="modal-header"><div><span className="overline">BRAND RADAR</span><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" aria-label="关闭" onClick={onClose}><X size={19} /></button></header>{children}</section></div>;
}

export function NewTaskModal({ cases, configured, busy, onCreate, onClose }) {
  const [caseId, setCaseId] = useState('');
  const [question, setQuestion] = useState('');
  const [title, setTitle] = useState('');
  function choose(item) { setCaseId(item.id); setQuestion(item.question || ''); setTitle(item.title || ''); }
  return <Modal title="这次，想弄清楚什么？" subtitle="从一个好问题开始，材料可以在桌面上慢慢补。" onClose={onClose} wide><form onSubmit={event => { event.preventDefault(); onCreate({ question: question.trim(), title: title.trim() || undefined, case_id: caseId || undefined }, configured); }}>
    <div className="modal-body"><label className="field-label" htmlFor="new-question">这次的企划问题</label><textarea id="new-question" className="question-input" rows={4} value={question} onChange={event => setQuestion(event.target.value)} placeholder="例如：下周上海门店想做一件小事，不上新品、不打折。有哪些值得试的方向？" required />
      <div className="title-field"><label htmlFor="new-title">给桌面起个名字<span>可选</span></label><input id="new-title" value={title} onChange={event => setTitle(event.target.value)} placeholder="例如：下周咖啡企划" maxLength={100} /></div>
      {cases.length > 0 && <div className="case-picker"><div className="section-heading"><span>也可以从现有材料开始</span><small>公开研究材料</small></div><div className="case-list">{cases.map(item => <button type="button" key={item.id} className={`case-option ${caseId === item.id ? 'selected' : ''}`} onClick={() => choose(item)}><span className="case-icon"><FolderOpen size={19} /></span><span><strong>{item.title}</strong><small>{item.description}</small></span><span className="case-check">{caseId === item.id ? <Check size={15} /> : <ArrowUpRight size={16} />}</span></button>)}</div>{caseId && <button type="button" className="text-button clear-case" onClick={() => setCaseId('')}>移除示例材料，只用我的问题</button>}<p className="field-help">材料保留原始出处与日期。历史路线和活动用于研究参考，不代表当前仍在进行。</p></div>}
      {!configured && <div className="inline-notice"><Radio size={16} /><span>模型还没有配置。可以先建桌面、放材料，配置 API Key 后再开始调查。</span></div>}
    </div><footer className="modal-footer"><span>每个问题都有自己的桌面</span><div><button type="button" className="secondary-button" disabled={busy || !question.trim()} onClick={() => onCreate({ question: question.trim(), title: title.trim() || undefined, case_id: caseId || undefined }, false)}>先准备桌面</button>{configured && <button type="submit" className="primary-button" disabled={busy || !question.trim()}>{busy ? <LoaderCircle size={16} className="spinning" /> : <ArrowUpRight size={16} />}开始调查</button>}</div></footer>
  </form></Modal>;
}

export function SourcesModal({ busy, onAdd, onClose }) {
  const [mode, setMode] = useState('url');
  const [value, setValue] = useState('');
  const [title, setTitle] = useState('');
  const [fileName, setFileName] = useState('');
  const [fileError, setFileError] = useState('');
  const fileRef = useRef(null);
  async function readFile(file) {
    setFileError('');
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { setFileError('这份文件超过 2 MB，请先摘取本次相关的内容。'); return; }
    if (!/\.(txt|md|csv|json|html?)$/i.test(file.name)) { setFileError('目前支持 TXT、Markdown、CSV、JSON 和 HTML 文本文件。'); return; }
    try { const text = await file.text(); setValue(text); setTitle(file.name); setFileName(file.name); setMode('text'); } catch { setFileError('无法读取这份文件，请重试或直接粘贴内容。'); }
  }
  const urlValid = mode !== 'url' || !!safeUrl(value.trim());
  return <Modal title="把材料放上桌" subtitle="一个公开链接、一段观察，或者一份文本。保留原始出处，会让判断更有根。" onClose={onClose}><form onSubmit={event => { event.preventDefault(); onAdd({ ...(mode === 'url' ? { url: value.trim() } : { text: value.trim() }), title: title.trim() || undefined }); }}>
    <div className="modal-body"><div className="segmented-control"><button type="button" className={mode === 'url' ? 'active' : ''} onClick={() => { setMode('url'); setValue(''); }}><Link size={15} />公开链接</button><button type="button" className={mode === 'text' ? 'active' : ''} onClick={() => { setMode('text'); setValue(''); }}><FileText size={15} />粘贴内容</button><button type="button" onClick={() => fileRef.current?.click()}><Upload size={15} />文本文件</button></div>
      <input ref={fileRef} type="file" accept=".txt,.md,.csv,.json,.html,.htm" className="visually-hidden" onChange={event => readFile(event.target.files?.[0])} />
      <label className="field-label" htmlFor="source-title">材料标题<span>可选</span></label><input id="source-title" value={title} onChange={event => setTitle(event.target.value)} placeholder="它是什么，或为什么值得看" maxLength={200} />
      <label className="field-label" htmlFor="source-value">{mode === 'url' ? '公开网页地址' : '材料内容'}{fileName && mode === 'text' && <span>{fileName}</span>}</label>
      {mode === 'url' ? <input id="source-value" type="url" value={value} onChange={event => setValue(event.target.value)} placeholder="https://…" autoComplete="off" required /> : <textarea id="source-value" value={value} onChange={event => setValue(event.target.value)} rows={9} placeholder="粘贴原文或你的现场观察；如果知道出处和日期，也一起写下。" required />}
      <div className="file-drop" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); readFile(event.dataTransfer.files?.[0]); }} onClick={() => fileRef.current?.click()} role="button" tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') fileRef.current?.click(); }}><Upload size={16} />也可以将文本文件拖到这里</div>
      {fileError && <p className="field-error">{fileError}</p>}<p className="field-help">网页无法读取时会明确提示，可改为粘贴原文。不会绕过登录或访问限制。</p>
    </div><footer className="modal-footer"><span>材料会留在本次桌面</span><button className="primary-button" type="submit" disabled={busy || !value.trim() || !urlValid}>{busy ? <LoaderCircle className="spinning" size={16} /> : <Plus size={16} />}放上桌</button></footer>
  </form></Modal>;
}

export function BrandModal({ content, busy, onSave, onClose }) {
  const [draft, setDraft] = useState(content);
  return <Modal title="让它认识你的品牌" subtitle="记录值得坚持的取舍，也放进你欣赏和不喜欢的真实例子。" onClose={onClose} wide className="brand-modal"><form onSubmit={event => { event.preventDefault(); onSave(draft); }}><div className="modal-body"><div className="brand-writing-note"><BookOpen size={18} /><p>比“年轻、有活力”更有用的是：<strong>什么值得我们做，什么热闹我们不必跟。</strong><br />可以直接编辑，暂时不清楚的地方也可以留白。</p></div><label className="visually-hidden" htmlFor="brand-content">品牌档案正文</label><textarea id="brand-content" className="brand-editor" value={draft} onChange={event => setDraft(event.target.value)} spellCheck="false" /><p className="field-help">品牌档案保存在本机，从下一次调查或改稿开始使用。桌面上已有的作品不会自动重写。</p></div><footer className="modal-footer"><span>品牌的样子，可以慢慢变清楚</span><button type="submit" className="primary-button" disabled={busy || draft === content}>{busy ? <LoaderCircle className="spinning" size={16} /> : <Check size={16} />}保存品牌档案</button></footer></form></Modal>;
}

export function SettingsModal({ status, busy, onRefresh, onClose }) {
  return <Modal title="桌面设置" subtitle="模型留在幕后，工作留在这里。" onClose={onClose}><div className="modal-body"><div className={`connection-card ${status?.configured ? 'connected' : ''}`}><span className="connection-icon"><Radio size={22} /></span><div><strong>{status?.configured ? '模型 API Key 已配置' : '还没有配置模型 API Key'}</strong><p>{status?.configured ? '调查使用真实模型，调用失败会明确提示。' : '你仍然可以创建桌面、补充材料和编辑品牌档案。'}</p></div></div><dl className="settings-list"><div><dt>模型服务</dt><dd>{status?.provider || '未配置'}</dd></div><div><dt>使用模型</dt><dd>{status?.model || '未配置'}</dd></div><div><dt>工作保存</dt><dd>本机文件</dd></div></dl>{!status?.configured && <div className="settings-instructions"><h3>连接你的模型</h3><p>在项目的 <code>.env</code> 文件中填写服务商与 API Key，然后重新启动 Brand Radar 服务。</p><p>可以参考项目中的 <code>.env.example</code>。页面不会显示或保存密钥。</p></div>}<div className="keyboard-guide"><h3>桌面上的小习惯</h3><p><kbd>拖动空白处</kbd><span>移动桌面</span></p><p><kbd>⌘ / Ctrl + 滚轮</kbd><span>放大与缩小</span></p><p><kbd>Shift + 点击</kbd><span>选择多张卡片</span></p><p><kbd>双击卡片正文</kbd><span>直接修改</span></p><p><kbd>⌘ / Ctrl + Enter</kbd><span>发送给 Agent</span></p></div></div><footer className="modal-footer"><span>密钥只在本机环境中使用</span><button className="secondary-button" disabled={busy} onClick={onRefresh}><RotateCcw size={15} className={busy ? 'spinning' : ''} />重新检查配置</button></footer></Modal>;
}

export function HistoryModal({ tasks, currentId, onSelect, onClose }) {
  const [query, setQuery] = useState('');
  const list = tasks.filter(task => task.title.toLowerCase().includes(query.toLowerCase()));
  const states = { running: '调查中', error: '需要留意', stopped: '已停止', idle: '已保存' };
  return <Modal title="接着上次的想法" subtitle="问题、材料和你的修改，都留在各自的桌面上。" onClose={onClose} wide><div className="modal-body"><div className="search-field"><Search size={16} /><input aria-label="搜索历史桌面" value={query} onChange={event => setQuery(event.target.value)} placeholder="找一个桌面…" /></div><div className="history-list">{list.length ? list.map(task => <button key={task.id} className={`history-item ${task.id === currentId ? 'current' : ''}`} onClick={() => onSelect(task.id)}><span className="history-item-icon"><FolderOpen size={21} /></span><span className="history-item-main"><strong>{task.title}</strong><small>{dateLabel(task.updated_at, true)} · {task.card_count || 0} 张卡片</small></span><span className={`history-status ${task.status}`}><i />{states[task.status] || '已保存'}</span><ChevronRight size={17} /></button>) : <div className="list-empty"><Clock3 size={26} /><p>{query ? '没有找到这个名字的桌面' : '你的第一张桌面，还在等一个问题。'}</p></div>}</div></div></Modal>;
}

export function EditCardModal({ card, busy, onSave, onClose }) {
  const sources = useContext(SourceContext);
  const [title, setTitle] = useState(card.title);
  const [body, setBody] = useState(readableText(card.body, sources));
  return <Modal title="把这个想法改成你的" subtitle="直接修改卡片，之后可以让 Agent 沿着你的版本继续。" onClose={onClose} wide><form onSubmit={event => { event.preventDefault(); onSave({ id: card.id, title: title.trim(), body }); }}><div className="modal-body"><label className="field-label" htmlFor="card-title">标题</label><input id="card-title" value={title} onChange={event => setTitle(event.target.value)} required maxLength={300} /><label className="field-label" htmlFor="card-body">正文</label><textarea id="card-body" className="card-editor" value={body} onChange={event => setBody(event.target.value)} rows={12} /></div><footer className="modal-footer"><span>引用的材料与卡片位置会保留</span><button className="primary-button" disabled={busy || !title.trim()}>{busy ? <LoaderCircle className="spinning" size={16} /> : <Check size={16} />}保存修改</button></footer></form></Modal>;
}

function SourceDetail({ source }) {
  const [expanded, setExpanded] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const url = safeUrl(source.url), imageUrl = safeUrl(source.image_url);
  return <article className="source-detail"><div className="source-detail-top"><span className={`source-origin ${source.origin}`}>{source.origin === 'replay' ? 'Replay 材料' : source.origin === 'manual' ? '人工材料' : '公开来源'}</span><span>{dateLabel(source.published_at || source.accessed_at)}</span></div>{imageUrl && !imageFailed && <img className="drawer-source-image" src={imageUrl} alt={source.title} loading="lazy" referrerPolicy="no-referrer" onError={() => setImageFailed(true)} />}<h4>{source.title}</h4>{url && <a className="source-url" href={url} target="_blank" rel="noreferrer"><span>打开原始页面 · {siteName(url)}</span><ArrowUpRight size={14} /></a>}<RichText text={expanded ? source.text || source.excerpt : source.excerpt || source.text} className={expanded ? '' : 'source-excerpt'} />{(source.text || source.excerpt) && <button className="text-button" onClick={() => setExpanded(!expanded)}>{expanded ? '收起材料' : '展开材料'}<ChevronRight size={13} className={expanded ? 'rotate-down' : ''} /></button>}</article>;
}

export function Drawer({ task, mode, cardId, onMode, onClose, onEdit, onStatus, onAsk, onAddSources, onFocus }) {
  const endRef = useRef(null);
  const [sourceQuery, setSourceQuery] = useState('');
  const card = task.cards.find(item => item.id === cardId);
  const related = card ? (card.source_ids || []).map(id => task.sources.find(source => source.id === id)).filter(Boolean) : [];
  const meta = KIND[card?.kind] || KIND.note;
  const activity = visibleActivity(task);
  useEffect(() => { if (mode === 'conversation') endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [mode, task.messages?.length, task.activity?.length]);
  const sourceList = task.sources.filter(source => `${source.title} ${source.excerpt || ''}`.toLowerCase().includes(sourceQuery.toLowerCase()));
  return <aside className="detail-drawer" aria-label="桌面详情"><header className="drawer-header"><div className="drawer-tabs"><button className={mode === 'conversation' ? 'active' : ''} onClick={() => onMode('conversation')}><MessageCircle size={15} />对话</button><button className={mode === 'sources' ? 'active' : ''} onClick={() => onMode('sources')}><BookOpen size={15} />材料<span>{task.sources.length}</span></button>{card && <button className={mode === 'card' ? 'active' : ''} onClick={() => onMode('card')}>卡片</button>}</div><button className="icon-button" onClick={onClose} aria-label="收起详情"><X size={18} /></button></header>
    <div className="drawer-scroll">{mode === 'conversation' && <><div className="conversation-intro"><span className="overline">THE QUESTION WE’RE WORKING ON</span><p>{task.question}</p></div>{!task.messages.length && <div className="conversation-empty"><MessageCircle size={26} strokeWidth={1.3} /><p>一起读材料、看线索、修改想法。<br />从桌面下方说一句话开始。</p></div>}{task.messages.map(message => <div className={`message ${message.role}`} key={message.id}><div className="message-author"><span>{message.role === 'user' ? '你' : 'Brand Radar'}</span><time>{dateLabel(message.created_at, true)}</time></div>{message.selected_card_ids?.length > 0 && <div className="message-references">{message.selected_card_ids.map(id => { const referenced = task.cards.find(item => item.id === id); return <button key={id} onClick={() => onFocus(id)}><StickyCardIcon />{referenced?.title || '选中的卡片'}</button>; })}</div>}<RichText text={message.content} /></div>)}{activity.length > 0 && <div className="activity-section"><div className="section-heading"><span>{task.status === 'running' ? '正在工作' : '调查记录'}</span><small>{activity.length} 条</small></div>{activity.map((item, index) => <div className={`activity-item ${task.status === 'running' && index === activity.length - 1 ? 'current' : ''} ${item.state || ''}`} key={item.id || index}><span className="activity-dot">{task.status === 'running' && index === activity.length - 1 ? <LoaderCircle size={12} className="spinning" /> : <Check size={11} />}</span><div><strong>{item.label}</strong>{item.detail && <p>{item.detail}</p>}</div></div>)}</div>}<div ref={endRef} /></>}
      {mode === 'sources' && <><div className="drawer-section-title"><div><span className="overline">ON THE DESK</span><h3>本次材料</h3></div><button className="secondary-button small" onClick={onAddSources}><Plus size={14} />补材料</button></div>{task.sources.length > 3 && <div className="search-field compact"><Search size={15} /><input value={sourceQuery} onChange={event => setSourceQuery(event.target.value)} placeholder="在材料中找一找" aria-label="搜索材料" /></div>}{sourceList.length ? sourceList.map(source => <SourceDetail key={source.id} source={source} />) : <div className="list-empty"><FileText size={26} /><p>{sourceQuery ? '没有匹配的材料' : '还没有材料，放一个公开链接或一段文字进来。'}</p></div>}</>}
      {mode === 'card' && card && <><div className={`drawer-card-heading paper-${card.color || meta.color}`}><span className="overline">{meta.label}</span><h2>{card.title}</h2><div className="drawer-card-actions"><button className="text-button" onClick={() => onEdit(card)}><Pencil size={14} />直接改</button><button className="text-button" onClick={() => onStatus(card, card.status === 'kept' ? 'draft' : 'kept')}><Check size={14} />{card.status === 'kept' ? '已保留' : '保留'}</button><button className="text-button" onClick={() => onStatus(card, card.status === 'archived' ? 'draft' : 'archived')}><ArrowDownToLine size={14} />{card.status === 'archived' ? '放回桌面' : '先放下'}</button></div></div><RichText text={card.body} className="drawer-card-body" /><RevisionHistory card={card} /><button className="continue-card-button" onClick={() => onAsk(card.id)}><MessageCircle size={16} />围绕这张卡片继续推敲<ArrowRight size={15} /></button><div className="section-heading related-sources-heading"><span>这张卡片的依据</span><small>{related.length} 份材料</small></div>{related.length ? related.map(source => <SourceDetail key={source.id} source={source} />) : <p className="field-help">这张卡片没有关联来源。它可能是案头笔记、待回答的问题或创意假说，不能据此确认外部事实。</p>}</>}
    </div>
  </aside>;
}

function StickyCardIcon() { return <FileText size={11} />; }

function RevisionHistory({ card }) {
  if (!card.revisions?.length) return null;
  return <details className="revision-history"><summary><Clock3 size={13} />之前的稿子 <span>{card.revisions.length}</span><ChevronDownIcon /></summary><div>{[...card.revisions].reverse().map((revision, index) => <article key={`${revision.updated_at}-${index}`}><time>{dateLabel(revision.updated_at, true)}</time><h4>{revision.title}</h4><RichText text={revision.body} /></article>)}</div></details>;
}

function ChevronDownIcon() { return <ChevronRight size={13} className="revision-chevron" />; }
