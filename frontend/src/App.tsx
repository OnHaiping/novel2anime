import {FormEvent, useEffect, useRef, useState} from 'react';
import {api, jsonInit} from './api';
import type {AssetJob, Character, Job, ModelStatus, Motion, NovelContent, NovelSelection, Project, Shot} from './types';

type View = 'projects' | 'motions' | 'models' | 'system';
type Runner = (fn: () => Promise<void>) => void;
type TaskNotice = {id:string; label:string; detail?:string};

function Status({value}: {value: string}) {
  return <span className={`status status-${value}`}>{value}</span>;
}

export function App() {
  const [view, setView] = useState<View>('projects');
  const [selected, setSelected] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [taskPanel, setTaskPanel] = useState(false);
  const [taskNotice, setTaskNotice] = useState<TaskNotice | null>(null);
  const [renderJobs, setRenderJobs] = useState<Job[]>([]);
  const [assetJobs, setAssetJobs] = useState<AssetJob[]>([]);
  const run: Runner = async fn => {
    setError(''); setNotice('');
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const title = selected ? '项目工作台' : ({projects:'项目', motions:'动作库', models:'模型下载', system:'系统诊断'} as const)[view];
  const loadTasks=()=>Promise.all([api<Job[]>('/renders/jobs'),api<AssetJob[]>('/assets/jobs')]).then(([renders,assets])=>{setRenderJobs(renders);setAssetJobs(assets)}).catch(()=>{});
  useEffect(()=>{void loadTasks();const timer=setInterval(loadTasks,4000);return()=>clearInterval(timer)},[]);
  const queueTask=(task:TaskNotice)=>{setTaskNotice(task);setTaskPanel(true);void loadTasks()};

  return <div className="shell">
    <aside>
      <div className="brand"><span>N2A</span><div>Novel2Anime<small>小说动漫生产台</small></div></div>
      <nav>
        <button className={view === 'projects' ? 'active' : ''} onClick={() => {setView('projects'); setSelected(null)}}>项目</button>
        <button className={view === 'motions' ? 'active' : ''} onClick={() => setView('motions')}>动作库</button>
        <button className={view === 'models' ? 'active' : ''} onClick={() => setView('models')}>模型下载</button>
        <button className={view === 'system' ? 'active' : ''} onClick={() => setView('system')}>系统诊断</button>
      </nav>
      <footer>ComfyUI orchestration · v0.2</footer>
    </aside>
    <main>
      <header><div><h1>{title}</h1><p>长篇解析、资产生成与双 GPU 镜头渲染</p></div><div className="live"><i /> 服务监控中</div></header>
      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert ok">{notice}</div>}
      {view === 'projects' && !selected && <Projects onSelect={setSelected} run={run} />}
      {view === 'projects' && selected && <ProjectWorkspace id={selected} back={() => setSelected(null)} run={run} notify={setNotice} queueTask={queueTask} />}
      {view === 'motions' && <Motions run={run} notify={setNotice} queueTask={queueTask} />}
      {view === 'models' && <Models run={run} notify={setNotice} queueTask={queueTask} />}
      {view === 'system' && <System />}
    </main>
    <TaskBubble count={[...renderJobs,...assetJobs].filter(job=>job.status==='queued'||job.status==='running'||job.status==='rendering').length} onClick={()=>setTaskPanel(true)}/>
    {taskPanel&&<TaskCenter renders={renderJobs} assets={assetJobs} onClose={()=>setTaskPanel(false)} refresh={loadTasks}/>}
    {taskNotice&&<TaskQueuedModal task={taskNotice} onClose={()=>setTaskNotice(null)} onOpen={()=>{setTaskNotice(null);setTaskPanel(true)}}/>}
  </div>;
}

function TaskBubble({count,onClick}:{count:number;onClick:()=>void}) {
  return <button className="task-bubble" onClick={onClick} aria-label="打开任务中心"><span>任务</span>{count>0&&<b>{count>99?'99+':count}</b>}</button>;
}

function TaskCenter({renders,assets,onClose,refresh}:{renders:Job[];assets:AssetJob[];onClose:()=>void;refresh:()=>void}) {
  const active=[...assets,...renders].filter(job=>job.status==='queued'||job.status==='running'||job.status==='rendering').length;
  return <div className="task-overlay" role="dialog" aria-modal="true"><section className="task-center"><div className="section-title"><div><h3>任务中心</h3><p className="muted">进行中 {active} 项，自动每 4 秒刷新。</p></div><div className="form-row"><button onClick={refresh}>刷新</button><button onClick={onClose}>关闭</button></div></div><div className="task-scroll"><h4>资产、模型与动作任务</h4>{assets.length?<div className="task-list">{assets.map(job=><div className="task-row" key={job.id}><div><strong>{job.job_type}</strong><small>{job.id.slice(0,8)} · {new Date(job.created_at).toLocaleString()}</small></div><div><Status value={job.status}/><small>{job.worker_name??'等待分配'}</small></div>{job.error_message&&<p className="danger">{job.error_message.slice(0,280)}</p>}</div>)}</div>:<div className="empty">暂无资产任务</div>}<h4>镜头渲染任务</h4>{renders.length?<div className="task-list">{renders.map(job=><div className="task-row" key={job.id}><div><strong>镜头 {job.shot_id.slice(0,8)}</strong><small>{job.id.slice(0,8)} · 尝试 #{job.attempt}</small></div><div><Status value={job.status}/><small>{job.worker_name??'等待分配'}</small></div>{job.error_message&&<p className="danger">{job.error_message.slice(0,280)}</p>}</div>)}</div>:<div className="empty">暂无镜头任务</div>}</div></section></div>;
}

function TaskQueuedModal({task,onClose,onOpen}:{task:TaskNotice;onClose:()=>void;onOpen:()=>void}) {
  return <div className="task-overlay" role="dialog" aria-modal="true"><section className="queued-modal"><span className="eyebrow">TASK ACCEPTED</span><h3>{task.label}</h3><p>{task.detail??'任务已进入队列。可在悬浮任务球中随时查看状态、Worker 分配和错误信息。'}</p><small>任务 ID：{task.id}</small><div className="form-row"><button className="primary" onClick={onOpen}>查看任务中心</button><button onClick={onClose}>继续编辑</button></div></section></div>;
}

function ReferencePreview({url,name,onClose}:{url:string;name:string;onClose:()=>void}) {
  return <div className="task-overlay reference-modal" role="dialog" aria-modal="true" onClick={onClose}><section onClick={event=>event.stopPropagation()}><div className="section-title"><h3>{name} 的参考图</h3><button onClick={onClose}>关闭</button></div><img src={url} alt={`${name} 参考图预览`}/></section></div>;
}

function Projects({onSelect, run}: {onSelect:(id:string)=>void; run:Runner}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('');
  const load = () => api<Project[]>('/projects').then(setProjects);
  useEffect(() => { void load(); }, []);
  const create = (e: FormEvent) => { e.preventDefault(); run(async () => { await api('/projects', jsonInit('POST', {name})); setName(''); await load(); }); };
  return <>
    <section className="hero"><div><span className="eyebrow">PIPELINE</span><h2>从小说人工选段到可追踪的动漫镜头</h2><p>原文保持原样显示。人工划线记录制作范围，只有选中的记录才交给大模型。</p></div><form onSubmit={create}><input value={name} onChange={e=>setName(e.target.value)} placeholder="项目名称" required/><button className="primary">新建项目</button></form></section>
    <section><div className="section-title"><h3>最近项目</h3><button onClick={() => void load()}>刷新</button></div><div className="cards">
      {projects.map(p => <button className="project-card" key={p.id} onClick={() => onSelect(p.id)}><div><strong>{p.name}</strong><Status value={p.status}/></div><p>{p.source_filename ?? '尚未上传小说'}</p><small>{new Date(p.updated_at).toLocaleString()}</small></button>)}
      {!projects.length && <div className="empty">还没有项目。</div>}
    </div></section>
  </>;
}

function ProjectWorkspace({id, back, run, notify, queueTask}: {id:string; back:()=>void; run:Runner; notify:(s:string)=>void; queueTask:(task:TaskNotice)=>void}) {
  const [project, setProject] = useState<Project | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selections, setSelections] = useState<NovelSelection[]>([]);
  const [content, setContent] = useState<NovelContent>({novel_type:'long',text:'',length:0,max_selection_chars:12000});
  const [shots, setShots] = useState<Shot[]>([]);
  const [novel, setNovel] = useState<File | null>(null);
  const [novelType, setNovelType] = useState<'long'|'short'>('long');
  const [selectionTitle, setSelectionTitle] = useState('');
  const [range, setRange] = useState({start:0,end:0});
  const novelRef = useRef<HTMLTextAreaElement>(null);
  const [maxShots, setMaxShots] = useState(30);
  const [useLlm, setUseLlm] = useState(true);
  const [appendTimeline, setAppendTimeline] = useState(false);
  const [planDraft, setPlanDraft] = useState('');
  const [llmModel, setLlmModel] = useState('');
  const [llmBaseUrl, setLlmBaseUrl] = useState('');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmProtocol, setLlmProtocol] = useState<'openai'|'anthropic'>('openai');
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [llmListError, setLlmListError] = useState('');
  const [portraitPending, setPortraitPending] = useState(false);
  const load = async () => {
    const [p,c,n,x,s] = await Promise.all([
      api<Project>(`/projects/${id}`), api<Character[]>(`/projects/${id}/characters`),
      api<NovelContent>(`/projects/${id}/novel-content`), api<NovelSelection[]>(`/projects/${id}/selections`), api<Shot[]>(`/projects/${id}/shots`),
    ]);
    setProject(p); setCharacters(c); setContent(n); setNovelType(n.novel_type); setSelections(x); setShots(s);
  };
  useEffect(() => { void load(); }, [id]);
  useEffect(() => { api<{draft:unknown}>(`/projects/${id}/plan-draft`).then(r=>setPlanDraft(JSON.stringify(r.draft,null,2))).catch(()=>setPlanDraft('')); }, [id]);
  useEffect(()=>{setLlmApiKey(sessionStorage.getItem(`n2a:llm-token:${id}`)??'');api<{base_url:string;model:string;protocol:'openai'|'anthropic'}>(`/projects/${id}/llm-config`).then(r=>{setLlmBaseUrl(r.base_url);setLlmModel(r.model);setLlmProtocol(r.protocol)}).catch(()=>{})},[id]);
  useEffect(()=>{if(!portraitPending)return;const poll=async()=>{try{const jobs=await api<AssetJob[]>('/assets/jobs');const active=jobs.some(job=>job.project_id===id&&job.job_type==='portrait'&&(job.status==='queued'||job.status==='running'));if(!active){setPortraitPending(false);await load()}}catch{/* keep the current card visible and retry */}};void poll();const timer=setInterval(()=>void poll(),4000);return()=>clearInterval(timer)},[portraitPending,id]);
  const refreshLlmModels=async()=>{const base_url=llmBaseUrl.trim();if(!base_url)throw new Error('请先填写 API 地址');setLlmListError('');try{const r=await api<{base_url:string;default_model:string|null;models:string[]}>('/system/llm/models',jsonInit('POST',{base_url,model:llmModel.trim()||'manual-model',api_key:llmApiKey.trim()||null,protocol:llmProtocol}));setLlmModels(r.models);setLlmBaseUrl(r.base_url);setLlmModel(current=>current||r.default_model||r.models[0]||'')}catch(e){setLlmListError(e instanceof Error?e.message:String(e))}};
  const uploadNovel = () => run(async()=>{ if(!novel) throw new Error('请选择 TXT 或 Markdown'); const f=new FormData(); f.append('file',novel); f.append('novel_type',novelType); await api(`/projects/${id}/novel`,{method:'POST',body:f}); notify('小说已上传，请在原文中划线并记录选段'); await load(); });
  const updateRange = () => {const el=novelRef.current;if(el)setRange({start:el.selectionStart,end:el.selectionEnd})};
  const recordSelection = () => run(async()=>{const el=novelRef.current;if(!el||el.selectionEnd<=el.selectionStart)throw new Error('请先在原文框中拖动划线选取文字');const length=el.selectionEnd-el.selectionStart;if(length>content.max_selection_chars)throw new Error(`单个选段不能超过 ${content.max_selection_chars.toLocaleString()} 字，请缩小范围`);await api(`/projects/${id}/selections`,jsonInit('POST',{title:selectionTitle.trim()||`选段 ${selections.length+1}`,char_start:el.selectionStart,char_end:el.selectionEnd}));setSelectionTitle('');notify(`已记录 ${length.toLocaleString()} 字，后续可勾选处理`);await load();});
  const llmPayload=()=>{const base_url=llmBaseUrl.trim(), llm_model=llmModel.trim(), llm_api_key=llmApiKey.trim();if(!base_url||!llm_model)throw new Error('请填写 API 地址和模型名称');return {base_url,llm_model,llm_api_key:llm_api_key||null,llm_protocol:llmProtocol}};
  const persistLlmConfig=async()=>{const config=llmPayload();await api(`/projects/${id}/llm-config`,jsonInit('PUT',{base_url:config.base_url,model:config.llm_model,api_key:null,protocol:config.llm_protocol}));if(config.llm_api_key)sessionStorage.setItem(`n2a:llm-token:${id}`,config.llm_api_key);else sessionStorage.removeItem(`n2a:llm-token:${id}`);return config};
  const saveLlmConfig=()=>run(async()=>{const config=await persistLlmConfig();notify(`项目 LLM 配置已保存：${config.llm_model}`);await load()});
  const generateDraft = () => run(async()=>{ const selection_ids=selections.filter(c=>c.selected).map(c=>c.id); const config=useLlm?await persistLlmConfig():null; const r=await api<{draft:unknown;selections_used:number}>(`/projects/${id}/plan-draft`,jsonInit('POST',{use_llm:useLlm,llm_model:config?.llm_model??null,llm_base_url:config?.base_url??null,llm_api_key:config?.llm_api_key??null,llm_protocol:config?.llm_protocol??null,max_shots:maxShots,target_shot_seconds:2,selection_ids}));setPlanDraft(JSON.stringify(r.draft,null,2));notify(`已使用 ${r.selections_used} 条选段生成 JSON 草案，请检查和编辑后再应用`);await load(); });
  const saveDraft = async()=>{let draft:unknown;try{draft=JSON.parse(planDraft)}catch{throw new Error('JSON 语法无效，请先修正')};const r=await api<{draft:unknown}>(`/projects/${id}/plan-draft`,jsonInit('PUT',{draft}));setPlanDraft(JSON.stringify(r.draft,null,2));return r.draft};
  const saveDraftAction=()=>run(async()=>{await saveDraft();notify('JSON 草案已校验并保存')});
  const generatePrompts=()=>run(async()=>{const config=await persistLlmConfig();await saveDraft();const r=await api<{draft:unknown}>(`/projects/${id}/plan-draft/prompts`,jsonInit('POST',{llm_model:config.llm_model,llm_base_url:config.base_url,llm_api_key:config.llm_api_key,llm_protocol:config.llm_protocol}));setPlanDraft(JSON.stringify(r.draft,null,2));notify(`大模型 ${llmModel.trim()} 已根据原文摘录和微调后的 JSON 生成每个镜头的提示词`)});
  const applyDraft=()=>run(async()=>{await saveDraft();const r=await api<{shots:number}>(`/projects/${id}/plan-draft/apply`,jsonInit('POST',{append_to_timeline:appendTimeline,max_shots:maxShots,target_shot_seconds:2}));notify(`JSON 已${appendTimeline?'追加':'应用'}到时间线，共生成 ${r.shots} 个镜头`);await load()});
  const toggleSelection = (selection: NovelSelection) => run(async()=>{ await api(`/projects/${id}/selections/${selection.id}`,jsonInit('PATCH',{selected:!selection.selected})); await load(); });
  const deleteSelection = (selection: NovelSelection) => run(async()=>{ await api(`/projects/${id}/selections/${selection.id}`,{method:'DELETE'}); await load(); });
  const locateSelection = (selection: NovelSelection) => {const el=novelRef.current;if(!el)return;el.focus();el.setSelectionRange(selection.char_start,selection.char_end);setRange({start:selection.char_start,end:selection.char_end});el.scrollTop=Math.max(0,(selection.char_start/Math.max(1,content.length))*el.scrollHeight-el.clientHeight/3)};
  const renderAll = () => run(async()=>{ const r=await api<{queued:number;job_ids:string[]}>(`/renders/projects/${id}`,jsonInit('POST',{force:false})); notify(`已提交 ${r.queued} 个镜头`); if(r.job_ids[0])queueTask({id:r.job_ids[0],label:`已提交 ${r.queued} 个镜头渲染任务`}); await load(); });
  const assemble = () => run(async()=>{ await api(`/renders/projects/${id}/assemble`,jsonInit('POST',{width:1024,height:576,fps:24,crf:18})); notify('成片合成任务已提交'); await load(); });
  const addCharacter = () => run(async()=>{ await api(`/projects/${id}/characters`,jsonInit('POST',{name:'新角色',age:25,positive_prompt:'adult anime character, consistent appearance'})); await load(); });
  if(!project) return <div className="empty">加载中…</div>;
  return <>
    <button className="back" onClick={back}>← 返回项目</button>
    <section className="project-head"><div><span className="eyebrow">{project.id.slice(0,8)}</span><h2>{project.name}</h2><Status value={project.status}/><p className="muted">成片：{project.assembly_status}{project.final_output ? ` · ${project.final_output}` : ''}</p>{project.final_output&&<a href={`/api/renders/projects/${id}/final`}>下载最终 MP4</a>}</div><div className="actions"><button onClick={assemble}>合成成片</button><button className="primary" onClick={renderAll}>渲染全部待办</button></div></section>
    <section className="panel"><h3>小说导入</h3><p className="muted">{project.source_filename ?? '未上传'} · {content.length.toLocaleString()} 字 · {content.novel_type==='long'?'长篇小说':'短篇小说'}</p><div className="form-row"><select value={novelType} onChange={e=>setNovelType(e.target.value as 'long'|'short')}><option value="long">长篇小说</option><option value="short">短篇小说</option></select><input type="file" accept=".txt,.md" onChange={e=>setNovel(e.target.files?.[0]??null)}/><button onClick={uploadNovel}>上传并显示原文</button></div></section>
    {content.text&&<section className="panel novel-reader"><h3>原文划线选取</h3><p className="muted">在下面原文中拖动选择文字，再点击“记录当前选区”。每条最多 {content.max_selection_chars.toLocaleString()} 字；系统不会自动识别章节或自动切块。</p><textarea ref={novelRef} className="novel-source" readOnly value={content.text} onSelect={updateRange}/><div className="form-row"><input value={selectionTitle} onChange={e=>setSelectionTitle(e.target.value)} placeholder={`选段标题（默认：选段 ${selections.length+1}）`}/><span className="range-info">当前选区：{range.start.toLocaleString()}–{range.end.toLocaleString()}（{Math.max(0,range.end-range.start).toLocaleString()} 字）</span><button className="primary" onClick={recordSelection}>记录当前选区</button></div></section>}
    <section><div className="section-title"><h3>已记录选段 · 启用 {selections.filter(c=>c.selected).length}/{selections.length}</h3></div><div className="selection-list">{selections.map(c=><div key={c.id} className={`selection-card ${c.selected?'selected':''}`}><button className="selection-toggle" onClick={()=>toggleSelection(c)}><strong>{c.sequence}. {c.title}</strong><small>字符 {c.char_start.toLocaleString()}–{c.char_end.toLocaleString()} · {c.source_text.length.toLocaleString()} 字 · 已处理 {c.process_count} 次</small><p>{c.source_text.slice(0,220)}</p><span>{c.selected?'将参与处理':'已停用'}{c.last_processed_at?` · 最近 ${new Date(c.last_processed_at).toLocaleString()}`:''}</span></button><div className="selection-actions"><button onClick={()=>locateSelection(c)}>定位原文</button><button className="danger-button" onClick={()=>deleteSelection(c)}>删除记录</button></div></div>)}{!selections.length&&<div className="empty">尚未记录选段。请先在上方原文中划线选择。</div>}</div><div className="panel"><h3>大模型连接</h3><p className="muted">地址和模型名按项目保存；令牌仅保存在当前浏览器会话，不写入数据库。多数服务使用 OpenAI-compatible；Claude 原生地址请选择 Anthropic Messages。</p><div className="form-row"><select value={llmProtocol} onChange={e=>setLlmProtocol(e.target.value as 'openai'|'anthropic')}><option value="openai">OpenAI-compatible</option><option value="anthropic">Anthropic Messages</option></select><input value={llmBaseUrl} onChange={e=>setLlmBaseUrl(e.target.value)} placeholder={llmProtocol==='anthropic'?'https://api.anthropic.com/v1':'API 地址，例如 https://api.example.com/v1'}/><input list="llm-model-options" value={llmModel} onChange={e=>setLlmModel(e.target.value)} placeholder="模型名称"/><datalist id="llm-model-options">{llmModels.map(model=><option key={model} value={model}/>)}</datalist><input type="password" value={llmApiKey} onChange={e=>setLlmApiKey(e.target.value)} placeholder="API Token（可留空）"/></div><div className="form-row"><button onClick={()=>run(refreshLlmModels)}>刷新该地址的模型列表</button><button onClick={saveLlmConfig}>保存项目连接</button></div>{llmListError&&<p className="danger">{llmListError}</p>}<div className="form-row"><label><input type="checkbox" checked={useLlm} onChange={e=>setUseLlm(e.target.checked)}/> 使用大模型</label><label><input type="checkbox" checked={appendTimeline} onChange={e=>setAppendTimeline(e.target.checked)}/> 应用时追加到现有时间线</label><input type="number" min="1" max="300" value={maxShots} onChange={e=>setMaxShots(Number(e.target.value))}/><button className="primary" onClick={generateDraft}>生成可编辑 JSON 草案</button></div>{!useLlm&&<p className="danger">当前关闭了大模型，将使用按句拆分测试模式，不适合正式制作。</p>}</div></section>
    {planDraft&&<section className="panel plan-editor"><div className="section-title"><div><h3>分镜 JSON 草案</h3><p className="muted">先人工修改角色、场景、动作和镜头，再让大模型基于最终结构生成 positive_prompt / negative_prompt。</p></div><a href={`/api/projects/${id}/plan-draft?download=true`}>下载 JSON</a></div><textarea value={planDraft} onChange={e=>setPlanDraft(e.target.value)} spellCheck={false}/><div className="form-row"><button onClick={saveDraftAction}>校验并保存 JSON</button><button onClick={generatePrompts}>大模型生成镜头提示词</button><button className="primary" onClick={applyDraft}>{appendTimeline?'追加':'应用并替换'}到镜头时间线</button></div></section>}
    <section><div className="section-title"><h3>角色资产</h3><button onClick={addCharacter}>添加角色</button></div><div className="grid two">{characters.map(c=><CharacterItem key={c.id} character={c} projectId={id} reload={load} run={run} notify={notify} queueTask={queueTask} onPortraitQueued={()=>setPortraitPending(true)}/>) }{!characters.length&&<div className="empty">规划后自动创建角色，也可先手工定义。</div>}</div></section>
    <section><div className="section-title"><h3>镜头 · {shots.length}</h3><button onClick={() => void load()}>刷新</button></div><div className="shot-list">{shots.map(s=><ShotRow key={s.id} shot={s} run={run} reload={load} queueTask={queueTask}/>) }{!shots.length&&<div className="empty">记录并启用选段后生成分镜。</div>}</div></section>
  </>;
}

function CharacterItem({character,projectId,reload,run,notify,queueTask,onPortraitQueued}:{character:Character;projectId:string;reload:()=>Promise<void>;run:Runner;notify:(s:string)=>void;queueTask:(task:TaskNotice)=>void;onPortraitQueued:()=>void}) {
  const [file,setFile]=useState<File|null>(null);
  const [preview,setPreview]=useState(false);
  const [name,setName]=useState(character.name); const [age,setAge]=useState(character.age??25);
  const [description,setDescription]=useState(character.description); const [positive,setPositive]=useState(character.positive_prompt);
  useEffect(()=>{setName(character.name);setAge(character.age??25);setDescription(character.description);setPositive(character.positive_prompt)},[character]);
  const save=()=>run(async()=>{await api(`/projects/${projectId}/characters/${character.id}`,jsonInit('PATCH',{name,age,description,positive_prompt:positive}));notify('角色设定已保存，后续镜头提示词会引用它');await reload();});
  const upload=()=>run(async()=>{if(!file)throw new Error('请选择角色参考图');const f=new FormData();f.append('file',file);await api(`/projects/${projectId}/characters/${character.id}/reference`,{method:'POST',body:f});notify('角色参考图已更新');await reload();});
  const generate=()=>run(async()=>{const job=await api<AssetJob>(`/assets/projects/${projectId}/characters/${character.id}/portrait`,jsonInit('POST',{extra_prompt:'character design sheet, solo, full body, simple background',seed:Math.floor(Math.random()*2147483647),width:512,height:768}));onPortraitQueued();notify('角色立绘任务已提交');queueTask({id:job.id,label:`${character.name} 的参考图生成任务已提交`,detail:'完成后会自动绑定到此角色，可在这里预览或替换。'});});
  const referenceUrl=character.reference_image?`/api/projects/${projectId}/characters/${character.id}/reference?v=${encodeURIComponent(character.reference_image)}`:'';
  return <div className="panel character-editor"><div className="form-row"><input value={name} onChange={e=>setName(e.target.value)} placeholder="角色名"/><input type="number" min="18" value={age} onChange={e=>setAge(Number(e.target.value))}/></div>{referenceUrl?<div className="reference-card"><button className="reference-thumb" onClick={()=>setPreview(true)}><img src={referenceUrl} alt={`${character.name} 参考图`}/><span>点击预览</span></button><div><strong>已绑定参考图</strong><p className="muted">{character.reference_image}</p><button onClick={()=>setPreview(true)}>放大预览</button></div></div>:<div className="reference-empty">尚未绑定参考图。可生成角色立绘或上传本地图片。</div>}<textarea value={description} onChange={e=>setDescription(e.target.value)} placeholder="中文角色设定：外貌、发型、服装、性格"/><textarea value={positive} onChange={e=>setPositive(e.target.value)} placeholder="英文生成提示词"/><div className="form-row"><button onClick={save}>保存设定</button><button className="primary" onClick={generate}>{character.reference_image?'重新生成参考图':'AI 生成参考图'}</button><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>setFile(e.target.files?.[0]??null)}/><button onClick={upload}>{character.reference_image?'替换参考图':'上传参考图'}</button></div>{preview&&<ReferencePreview url={referenceUrl} name={character.name} onClose={()=>setPreview(false)}/>}</div>;
}

function ShotRow({shot,run,reload,queueTask}:{shot:Shot;run:Runner;reload:()=>Promise<void>;queueTask:(task:TaskNotice)=>void}) {
  const [result,setResult]=useState<{filename:string;media_type:string;size:number;worker_name:string|null;comfy_prompt_id:string|null;completed_at:string|null;preview_url:string;download_url:string}|null>(null);
  const [preview,setPreview]=useState(false);
  const render=()=>run(async()=>{const job=await api<Job>(`/renders/shots/${shot.id}`,jsonInit('POST',{force:shot.status==='completed'}));queueTask({id:job.id,label:`${shot.code} 镜头渲染已提交`});await reload();});
  const togglePreview=()=>run(async()=>{if(preview){setPreview(false);return}try{const data=await api<typeof result>(`/renders/shots/${shot.id}/result`);setResult(data);setPreview(true)}catch(error){if(error instanceof Error&&error.message==='Not Found')throw new Error('后端仍是旧版本，尚未提供镜头预览接口。请重新构建并强制重建 backend 容器。');throw error}});
  const isImage=result?.media_type.startsWith('image/');
  return <div className="shot-entry"><div className="shot"><div className="shot-code">{shot.code}<small>WF {shot.workflow_key}</small></div><div className="shot-main"><strong>{shot.action||'未描述动作'}</strong><p>{shot.shot_type} · {shot.motion_mode}</p></div><Status value={shot.status}/><div className="shot-actions">{shot.status==='completed'&&<button onClick={togglePreview}>{preview?'收起':'预览'}</button>}<button onClick={render}>{shot.status==='completed'?'重新生成':'加入队列'}</button></div></div>{preview&&result&&<div className="shot-preview">{isImage?<img src={result.preview_url} alt={`${shot.code} 输出`}/>:<video src={result.preview_url} controls preload="metadata"/>}<div className="preview-meta"><strong>{result.filename}</strong><span>{(result.size/1024/1024).toFixed(2)} MB · {result.media_type}</span><span>Worker：{result.worker_name??'未知'} · Prompt：{result.comfy_prompt_id??'未知'}</span><span>完成时间：{result.completed_at?new Date(result.completed_at).toLocaleString():'未知'}</span><a href={result.download_url}>下载原始输出</a></div></div>}</div>;
}

function Motions({run,notify,queueTask}:{run:Runner;notify:(s:string)=>void;queueTask:(task:TaskNotice)=>void}) {
  const [items,setItems]=useState<Motion[]>([]); const [file,setFile]=useState<File|null>(null);
  const [action,setAction]=useState('walk'); const [motionId,setMotionId]=useState('walk_slow_side_01'); const [prompt,setPrompt]=useState('walking slowly from left to right, natural arm swing');
  const load=()=>api<Motion[]>('/motions').then(setItems); useEffect(()=>{void load()},[]);
  const upload=()=>run(async()=>{if(!file)throw new Error('请选择视频');const f=new FormData();f.append('file',file);f.append('metadata',JSON.stringify({motion_id:motionId,name:motionId,action,speed:'normal',direction:'any',shot_type:'full body',camera:'static',source_type:'uploaded',tags:[action]}));await api('/motions/upload',{method:'POST',body:f});await load();});
  const generate=()=>run(async()=>{const job=await api<AssetJob>('/motions/generate',jsonInit('POST',{motion_id:motionId,name:motionId,action,prompt,speed:'normal',direction:'any',shot_type:'full body',camera:'static',seed:Math.floor(Math.random()*2147483647),tags:[action]}));notify('动作生成任务已提交');queueTask({id:job.id,label:`动作草稿 ${motionId} 已提交`});});
  return <><section className="panel"><h3>添加或生成动作</h3><div className="form-row"><input value={motionId} onChange={e=>setMotionId(e.target.value)} placeholder="motion_id"/><input value={action} onChange={e=>setAction(e.target.value)} placeholder="action"/></div><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder="动作生成提示词"/><div className="form-row"><button className="primary" onClick={generate}>AI 生成动作草稿</button><input type="file" accept="video/*" onChange={e=>setFile(e.target.files?.[0]??null)}/><button onClick={upload}>上传并标准化</button></div></section><div className="cards">{items.map(m=><div className="motion-card" key={m.id}><span className="eyebrow">{m.action}</span><strong>{m.name}</strong><p>{m.speed} · {m.direction}</p><small>{m.source_file}</small></div>)}</div></>;
}

function Jobs(){
  const [renders,setRenders]=useState<Job[]>([]); const [assets,setAssets]=useState<AssetJob[]>([]);
  const load=()=>Promise.all([api<Job[]>('/renders/jobs'),api<AssetJob[]>('/assets/jobs')]).then(([r,a])=>{setRenders(r);setAssets(a)});
  useEffect(()=>{void load();const t=setInterval(load,4000);return()=>clearInterval(t)},[]);
  return <><h3>资产与下载任务</h3><div className="table"><div className="tr head"><span>任务</span><span>类型</span><span>Worker</span><span>状态</span></div>{assets.map(j=><div className="tr" key={j.id}><span>{j.id.slice(0,8)}<small>{new Date(j.created_at).toLocaleString()}</small></span><span>{j.job_type}</span><span>{j.worker_name??'等待分配'}</span><span><Status value={j.status}/>{j.error_message&&<small className="danger">{j.error_message.slice(0,180)}</small>}</span></div>)}</div><div className="section-title"><h3>镜头渲染任务</h3></div><div className="table"><div className="tr head"><span>任务</span><span>Worker</span><span>尝试</span><span>状态</span></div>{renders.map(j=><div className="tr" key={j.id}><span>{j.id.slice(0,8)}<small>{j.shot_id.slice(0,8)}</small></span><span>{j.worker_name??'等待分配'}</span><span>#{j.attempt}</span><span><Status value={j.status}/>{j.error_message&&<small className="danger">{j.error_message.slice(0,180)}</small>}</span></div>)}</div></>;
}

function Models({run,notify,queueTask}:{run:Runner;notify:(s:string)=>void;queueTask:(task:TaskNotice)=>void}) {
  const [items,setItems]=useState<ModelStatus[]>([]); const load=()=>api<ModelStatus[]>('/system/models').then(setItems); useEffect(()=>{void load()},[]);
  const download=(key:string)=>run(async()=>{const r=await api<{status:string;job_id?:string}>(`/system/models/${key}/download`,{method:'POST'});notify(`模型任务状态：${r.status}`);if(r.job_id)queueTask({id:r.job_id,label:`模型 ${key} 下载已提交`});await load();});
  return <><div className="section-title"><h3>允许下载的开放模型</h3><button onClick={()=>void load()}>刷新</button></div><div className="cards">{items.map(m=><div className="motion-card" key={m.key}><Status value={m.exists?'completed':'pending'}/><strong>{m.name}</strong><p>{m.target}</p><small>{m.exists?`${(m.size/1024/1024).toFixed(1)} MB`:'尚未下载'}</small><button disabled={m.exists} onClick={()=>download(m.key)}>{m.exists?'已安装':'使用 curl 下载'}</button></div>)}</div><div className="alert ok">基础 Checkpoint 因许可不同不自动下载，请手工放入 checkpoints 目录。</div></>;
}

function System(){const [data,setData]=useState<any>(null);const [err,setErr]=useState('');const load=()=>api<any>('/system/diagnostics').then(setData).catch(e=>setErr(String(e)));useEffect(()=>{void load();const t=setInterval(load,10000);return()=>clearInterval(t)},[]);return <><div className="section-title"><h3>ComfyUI 与模型检查</h3><button onClick={load}>立即检查</button></div>{err&&<div className="alert error">{err}</div>}{!data?<div className="empty">诊断中…</div>:<><div className="metric-row"><div><small>总体</small><strong>{data.ok?'正常':'需要处理'}</strong></div><div><small>缺失模型</small><strong>{data.summary.missing_models.length}</strong></div><div><small>离线 Worker</small><strong>{data.summary.offline_workers.length}</strong></div></div><div className="grid two"><section className="panel"><h3>Workers</h3>{Object.entries(data.workers).map(([k,v]:any)=><div className="diag" key={k}><strong>{k}</strong><Status value={v.online?'online':'offline'}/><small>{v.url}</small>{v.missing_nodes?.length>0&&<p className="danger">缺少节点：{v.missing_nodes.join(', ')}</p>}</div>)}</section><section className="panel"><h3>模型</h3>{Object.entries(data.filesystem.models).map(([k,v]:any)=><div className="diag" key={k}><strong>{k}</strong><Status value={v.exists?'online':'failed'}/><small>{v.path}</small></div>)}</section></div><section className="panel logs"><h3>日志尾部</h3>{Object.entries(data.logs).map(([k,v]:any)=><details key={k}><summary>{k}</summary><pre>{v.join('')}</pre></details>)}</section></>}</>}
