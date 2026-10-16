import {FormEvent, useEffect, useState} from 'react';
import {api, jsonInit} from './api';
import type {Character, Job, Motion, Project, Shot} from './types';

type View = 'projects' | 'motions' | 'jobs' | 'system';

function Status({value}: {value: string}) { return <span className={`status status-${value}`}>{value}</span>; }

export function App() {
  const [view, setView] = useState<View>('projects');
  const [selected, setSelected] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const run = async (fn: () => Promise<void>) => { setError(''); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } };

  return <div className="shell">
    <aside>
      <div className="brand"><span>N2A</span><div>Novel2Anime<small>小说动漫生产台</small></div></div>
      <nav>
        <button className={view === 'projects' ? 'active' : ''} onClick={() => {setView('projects'); setSelected(null)}}>项目</button>
        <button className={view === 'motions' ? 'active' : ''} onClick={() => setView('motions')}>动作库</button>
        <button className={view === 'jobs' ? 'active' : ''} onClick={() => setView('jobs')}>渲染队列</button>
        <button className={view === 'system' ? 'active' : ''} onClick={() => setView('system')}>系统诊断</button>
      </nav>
      <footer>ComfyUI orchestration · v0.1</footer>
    </aside>
    <main>
      <header><div><h1>{selected ? '项目工作台' : ({projects:'项目', motions:'动作库', jobs:'渲染队列', system:'系统诊断'} as const)[view]}</h1><p>从小说结构化到双 GPU 镜头渲染</p></div><div className="live"><i /> 服务监控中</div></header>
      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert ok">{notice}</div>}
      {view === 'projects' && !selected && <Projects onSelect={setSelected} run={run} />}
      {view === 'projects' && selected && <ProjectWorkspace id={selected} back={() => setSelected(null)} run={run} notify={setNotice} />}
      {view === 'motions' && <Motions run={run} />}
      {view === 'jobs' && <Jobs />}
      {view === 'system' && <System />}
    </main>
  </div>;
}

function Projects({onSelect, run}: {onSelect:(id:string)=>void; run:(fn:()=>Promise<void>)=>void}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('');
  const load = () => api<Project[]>('/projects').then(setProjects);
  useEffect(() => { void load(); }, []);
  const create = (e: FormEvent) => {e.preventDefault(); run(async () => {await api('/projects', jsonInit('POST', {name})); setName(''); await load();});};
  return <>
    <section className="hero"><div><span className="eyebrow">PIPELINE</span><h2>把故事拆成可控制、可重试的镜头</h2><p>项目保存小说、角色资产、分镜、动作匹配和所有渲染记录。</p></div><form onSubmit={create}><input value={name} onChange={e=>setName(e.target.value)} placeholder="项目名称" required/><button className="primary">新建项目</button></form></section>
    <section><div className="section-title"><h3>最近项目</h3><button onClick={() => void load()}>刷新</button></div><div className="cards">
      {projects.map(p => <button className="project-card" key={p.id} onClick={() => onSelect(p.id)}><div><strong>{p.name}</strong><Status value={p.status}/></div><p>{p.source_filename ?? '尚未上传小说'}</p><small>{new Date(p.updated_at).toLocaleString()}</small></button>)}
      {!projects.length && <div className="empty">还没有项目。先建立一个 30～60 秒的样片项目。</div>}
    </div></section>
  </>;
}

function ProjectWorkspace({id, back, run, notify}: {id:string; back:()=>void; run:(fn:()=>Promise<void>)=>void; notify:(s:string)=>void}) {
  const [project, setProject] = useState<Project | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [shots, setShots] = useState<Shot[]>([]);
  const [novel, setNovel] = useState<File | null>(null);
  const load = async () => {const [p,c,s]=await Promise.all([api<Project>(`/projects/${id}`),api<Character[]>(`/projects/${id}/characters`),api<Shot[]>(`/projects/${id}/shots`)]);setProject(p);setCharacters(c);setShots(s);};
  useEffect(() => {void load();}, [id]);
  const uploadNovel = () => run(async()=>{if(!novel) throw new Error('请选择 TXT 或 Markdown');const f=new FormData();f.append('file',novel);await api(`/projects/${id}/novel`,{method:'POST',body:f});notify('小说已上传');await load();});
  const plan = () => run(async()=>{await api(`/projects/${id}/plan`,jsonInit('POST',{use_llm:true,max_shots:30,target_shot_seconds:2}));notify('分镜已生成');await load();});
  const renderAll = () => run(async()=>{const r=await api<{queued:number}>(`/renders/projects/${id}`,jsonInit('POST',{force:false}));notify(`已提交 ${r.queued} 个镜头`);await load();});
  const assemble = () => run(async()=>{await api(`/renders/projects/${id}/assemble`,jsonInit('POST',{width:1024,height:576,fps:24,crf:18}));notify('成片合成任务已提交');await load();});
  const addCharacter = () => run(async()=>{await api(`/projects/${id}/characters`,jsonInit('POST',{name:'主角',age:25,positive_prompt:'adult character, consistent appearance'}));await load();});
  if(!project) return <div className="empty">加载中…</div>;
  return <>
    <button className="back" onClick={back}>← 返回项目</button>
    <section className="project-head"><div><span className="eyebrow">{project.id.slice(0,8)}</span><h2>{project.name}</h2><Status value={project.status}/><p className="muted">成片：{project.assembly_status}{project.final_output ? ` · ${project.final_output}` : ''}</p>{project.final_output&&<a href={`/api/renders/projects/${id}/final`}>下载最终 MP4</a>}{project.assembly_error&&<p className="danger">{project.assembly_error.slice(0,240)}</p>}</div><div className="actions"><button onClick={plan}>生成/重建分镜</button><button onClick={assemble}>合成成片</button><button className="primary" onClick={renderAll}>渲染全部待办</button></div></section>
    <div className="grid two">
      <section className="panel"><h3>小说</h3><p>{project.source_filename ?? '未上传'}</p><input type="file" accept=".txt,.md" onChange={e=>setNovel(e.target.files?.[0]??null)}/><button onClick={uploadNovel}>上传小说</button></section>
      <section className="panel"><div className="section-title"><h3>角色资产</h3><button onClick={addCharacter}>添加主角</button></div>{characters.map(c=><CharacterItem key={c.id} character={c} projectId={id} reload={load} run={run}/>) }{!characters.length&&<p className="muted">分镜规划后会自动创建角色，也可先手工添加。</p>}</section>
    </div>
    <section><div className="section-title"><h3>镜头 · {shots.length}</h3><button onClick={() => void load()}>刷新</button></div><div className="shot-list">{shots.map(s=><ShotRow key={s.id} shot={s} run={run} reload={load}/>) }{!shots.length&&<div className="empty">上传小说后生成分镜。</div>}</div></section>
  </>;
}

function CharacterItem({character,projectId,reload,run}:{character:Character;projectId:string;reload:()=>Promise<void>;run:(fn:()=>Promise<void>)=>void}) {
  const [file,setFile]=useState<File|null>(null);
  const upload=()=>run(async()=>{if(!file)throw new Error('请选择角色参考图');const f=new FormData();f.append('file',file);await api(`/projects/${projectId}/characters/${character.id}/reference`,{method:'POST',body:f});await reload();});
  return <div className="character"><div><strong>{character.name}</strong><small>{character.age ? `${character.age} 岁` : '年龄待确认'}</small><p>{character.reference_image ?? '缺少参考图'}</p></div><div><input type="file" accept="image/*" onChange={e=>setFile(e.target.files?.[0]??null)}/><button onClick={upload}>上传参考图</button></div></div>;
}

function ShotRow({shot,run,reload}:{shot:Shot;run:(fn:()=>Promise<void>)=>void;reload:()=>Promise<void>}) {
  const render=()=>run(async()=>{await api(`/renders/shots/${shot.id}`,jsonInit('POST',{force:shot.status==='completed'}));await reload();});
  return <div className="shot"><div className="shot-code">{shot.code}<small>WF {shot.workflow_key}</small></div><div className="shot-main"><strong>{shot.action||'未描述动作'}</strong><p>{shot.shot_type} · {shot.motion_mode}</p></div><Status value={shot.status}/><button onClick={render}>{shot.status==='completed'?'重新生成':'加入队列'}</button></div>;
}

function Motions({run}:{run:(fn:()=>Promise<void>)=>void}) {
  const [items,setItems]=useState<Motion[]>([]);const [file,setFile]=useState<File|null>(null);const [action,setAction]=useState('walk');const [motionId,setMotionId]=useState('walk_slow_side_01');
  const load=()=>api<Motion[]>('/motions').then(setItems);useEffect(()=>{void load()},[]);
  const upload=()=>run(async()=>{if(!file)throw new Error('请选择视频');const f=new FormData();f.append('file',file);f.append('metadata',JSON.stringify({motion_id:motionId,name:motionId,action,speed:'normal',direction:'any',shot_type:'full body',camera:'static',source_type:'uploaded',tags:[action]}));await api('/motions/upload',{method:'POST',body:f});await load();});
  return <><section className="panel upload"><h3>添加动作</h3><input value={motionId} onChange={e=>setMotionId(e.target.value)} placeholder="motion_id"/><input value={action} onChange={e=>setAction(e.target.value)} placeholder="action"/><input type="file" accept="video/*" onChange={e=>setFile(e.target.files?.[0]??null)}/><button className="primary" onClick={upload}>上传并标准化</button></section><div className="cards">{items.map(m=><div className="motion-card" key={m.id}><span className="eyebrow">{m.action}</span><strong>{m.name}</strong><p>{m.speed} · {m.direction}</p><small>{m.source_file}</small></div>)}</div></>;
}

function Jobs(){const [items,setItems]=useState<Job[]>([]);const load=()=>api<Job[]>('/renders/jobs').then(setItems);useEffect(()=>{void load();const t=setInterval(load,4000);return()=>clearInterval(t)},[]);return <div className="table"><div className="tr head"><span>任务</span><span>Worker</span><span>尝试</span><span>状态</span></div>{items.map(j=><div className="tr" key={j.id}><span>{j.id.slice(0,8)}<small>{j.shot_id.slice(0,8)}</small></span><span>{j.worker_name??'等待分配'}</span><span>#{j.attempt}</span><span><Status value={j.status}/>{j.error_message&&<small className="danger">{j.error_message.slice(0,120)}</small>}</span></div>)}</div>}

function System(){const [data,setData]=useState<any>(null);const [err,setErr]=useState('');const load=()=>api<any>('/system/diagnostics').then(setData).catch(e=>setErr(String(e)));useEffect(()=>{void load();const t=setInterval(load,10000);return()=>clearInterval(t)},[]);return <><div className="section-title"><h3>ComfyUI 与模型检查</h3><button onClick={load}>立即检查</button></div>{err&&<div className="alert error">{err}</div>}{!data?<div className="empty">诊断中…</div>:<><div className="metric-row"><div><small>总体</small><strong>{data.ok?'正常':'需要处理'}</strong></div><div><small>缺失模型</small><strong>{data.summary.missing_models.length}</strong></div><div><small>离线 Worker</small><strong>{data.summary.offline_workers.length}</strong></div></div><div className="grid two"><section className="panel"><h3>Workers</h3>{Object.entries(data.workers).map(([k,v]:any)=><div className="diag" key={k}><strong>{k}</strong><Status value={v.online?'online':'offline'}/><small>{v.url}</small>{v.missing_nodes?.length>0&&<p className="danger">缺少节点：{v.missing_nodes.join(', ')}</p>}</div>)}</section><section className="panel"><h3>模型</h3>{Object.entries(data.filesystem.models).map(([k,v]:any)=><div className="diag" key={k}><strong>{k}</strong><Status value={v.exists?'online':'failed'}/><small>{v.path}</small></div>)}</section></div><section className="panel logs"><h3>日志尾部</h3>{Object.entries(data.logs).map(([k,v]:any)=><details key={k}><summary>{k}</summary><pre>{v.join('')}</pre></details>)}</section></>}</>}

