import { useEffect, useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Plus, FolderOpen, Sparkles, Settings2, Video, Play } from 'lucide-react';
import { useEffect as ReactUseEffect, useRef as ReactUseRef } from 'react';

type Health = { status: string };

export default function App() {
  const [health, setHealth] = useState<string>('checking…');
  const [initStatus, setInitStatus] = useState<string>('');
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [scenes, setScenes] = useState<{ scene_id: string; title: string }[]>([]);
  const [isAddSceneOpen, setIsAddSceneOpen] = useState<boolean>(false);
  const [newSceneTitle, setNewSceneTitle] = useState<string>('New Scene');
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [sceneDetail, setSceneDetail] = useState<any | null>(null);
  const [isGenOpen, setIsGenOpen] = useState<boolean>(false);
  const [genPrompt, setGenPrompt] = useState<string>('a cinematic shot of waves at sunset');
  const [currentVideoUrl, setCurrentVideoUrl] = useState<string | null>(null);
  const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(null);
  const [media, setMedia] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [settings, setSettings] = useState<any>({});
  const [isContPrevFrame, setIsContPrevFrame] = useState<boolean>(false);
  const [playIdx, setPlayIdx] = useState<number>(-1);
  const [provider, setProvider] = useState<'replicate' | 'vertex'>('replicate');
  const [nowPlaying, setNowPlaying] = useState<string>('');
  const [playError, setPlayError] = useState<string>('');
  const [headInfo, setHeadInfo] = useState<{ status?: number; type?: string; length?: string }>({});
  const videoRef = ReactUseRef<HTMLVideoElement | null>(null);
  // Vertex inputs and generation state
  const [vxUsePrevLast, setVxUsePrevLast] = useState<boolean>(false);
  const [vxStartImageId, setVxStartImageId] = useState<string | null>(null);
  const [vxEndImageId, setVxEndImageId] = useState<string | null>(null);
  const [vxRefImageIds, setVxRefImageIds] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [vxEndFromVideoId, setVxEndFromVideoId] = useState<string | null>(null);
  const [vxEndFramePath, setVxEndFramePath] = useState<string | null>(null);
  const [vxImageMode, setVxImageMode] = useState<'none' | 'start_end' | 'reference'>('none');
  function ProjectPicker({ projectId, onSwitch }: { projectId: string; onSwitch: (pid: string) => void }) {
    const [projects, setProjects] = useState<string[]>([]);
    const [newId, setNewId] = useState<string>(projectId);
    useEffect(() => {
      fetch('http://127.0.0.1:8000/storage/projects')
        .then((r) => r.json())
        .then((d) => setProjects(d.projects ?? []))
        .catch(() => setProjects([]));
    }, []);
    return (
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-neutral-400 mb-1">Existing</label>
          <div className="flex flex-wrap gap-2">
            {projects.length === 0 ? <div className="text-xs text-neutral-500">No projects yet.</div> : null}
            {projects.map((p) => (
              <button key={p} className="button text-xs" onClick={() => onSwitch(p)}>
                {p}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs text-neutral-400 mb-1">New project id</label>
          <input className="field" value={newId} onChange={(e) => setNewId(e.target.value)} />
          <div className="mt-2 flex gap-2">
            <button className="button" onClick={() => onSwitch(newId)}>Switch</button>
            <button
              className="button-primary"
              onClick={async () => {
                await fetch(`http://127.0.0.1:8000/storage/init-project/${newId}`, { method: 'POST' });
                onSwitch(newId);
              }}
            >
              Create
            </button>
          </div>
        </div>
      </div>
    );
  }
  const [projectId, setProjectId] = useState<string>(() => {
    const stored = localStorage.getItem('projectId');
    const initial = stored || 'vampyre';
    localStorage.setItem('projectId', initial);
    return initial;
  });
  const [selectedMediaId, setSelectedMediaId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      // Wait for backend to be up to avoid connection refused spam
      let ok = false;
      for (let i = 0; i < 40; i++) {
        try {
          const r = await fetch('http://127.0.0.1:8000/health');
          if (r.ok) {
            const j = (await r.json()) as Health;
            setHealth(j.status ?? 'ok');
            ok = true;
            break;
          }
        } catch (_) {
          // ignore
        }
        await new Promise((res) => setTimeout(res, 500));
      }
      if (!ok) {
        setHealth('offline');
        return;
      }
      if (cancelled) return;
      // Prefer 'vampyre' automatically if it exists
      try {
        const projs = await fetch('http://127.0.0.1:8000/storage/projects').then((r) => r.json());
        if (!cancelled && Array.isArray(projs?.projects) && projs.projects.includes('vampyre') && projectId !== 'vampyre') {
          localStorage.setItem('projectId', 'vampyre');
          setProjectId('vampyre');
          return;
        }
      } catch (_) {}
      // Ensure project exists before listing
      try {
        await fetch(`http://127.0.0.1:8000/storage/init-project/${projectId}`, { method: 'POST' });
      } catch (_) {}
      // Load global settings on launch
      try {
        const s = await fetch('http://127.0.0.1:8000/settings').then((r) => r.json());
        if (!cancelled) setSettings(s.settings ?? {});
      } catch (_) {}
      // Auto-scan media on boot
      try {
        await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/scan`, { method: 'POST' });
      } catch (_) {}
      // Load scenes for project
      try {
        const data = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`).then((r) => r.json());
        const list = data.scenes ?? [];
        if (!cancelled) {
          setScenes(list);
          if (!selectedSceneId && list.length > 0) {
            setSelectedSceneId(list[0].scene_id);
          }
        }
      } catch (_) {
        if (!cancelled) setScenes([]);
      }
      // Load media after scan
      try {
        const m = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`).then((r) => r.json());
        if (!cancelled) setMedia(m.media ?? []);
      } catch (_) {}
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    async function loadDetail() {
      if (!selectedSceneId) return;
      const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
      setSceneDetail(d.scene ?? null);
    }
    loadDetail();
  }, [selectedSceneId, projectId]);

  async function refreshMedia() {
    const m = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`).then((r) => r.json());
    setMedia(m.media ?? []);
  }

  async function debugHead(url: string) {
    try {
      const res = await fetch(url, { method: 'HEAD' });
      setHeadInfo({
        status: res.status,
        type: res.headers.get('Content-Type') || undefined,
        length: res.headers.get('Content-Length') || undefined
      });
      console.log('HEAD', url, res.status, res.headers.get('Content-Type'), res.headers.get('Content-Length'));
    } catch (e: any) {
      setHeadInfo({ status: undefined, type: undefined, length: undefined });
      console.warn('HEAD failed', url, e?.message || e);
    }
  }

  function selectMediaForPlayback(m: any) {
    if (m.type === 'video' || m.type === 'audio') {
      const url = `http://127.0.0.1:8000${m.url}`;
      setCurrentImageUrl(null);
      setCurrentVideoUrl(url);
      setNowPlaying(url);
      setPlayError('');
      debugHead(url);
    } else {
      const url = `http://127.0.0.1:8000${m.url}`;
      setCurrentVideoUrl(null);
      setCurrentImageUrl(url);
      setNowPlaying(url);
      setPlayError('');
      debugHead(url);
    }
  }

  useEffect(() => {
    refreshMedia().catch(() => {});
  }, [projectId]);

  async function initProject() {
    setIsCreating(true);
    setInitStatus('');
    try {
      const res = await fetch(`http://127.0.0.1:8000/storage/init-project/${projectId}`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setInitStatus(`Project created: ${data.project_dir}`);
        localStorage.setItem('projectId', projectId);
        // refresh scenes
        const s = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`).then((r) => r.json());
        setScenes(s.scenes ?? []);
        if (!selectedSceneId && s.scenes?.length) {
          setSelectedSceneId(s.scenes[0].scene_id);
        }
      } else {
        setInitStatus('Failed to create project');
      }
    } catch (e) {
      setInitStatus('Error creating project');
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="h-screen grid grid-cols-[280px_1fr_360px] grid-rows-[64px_1fr] gap-3 p-3">
      {/* Top bar */}
          <div className="col-span-3 row-span-1 border border-neutral-800 px-4 flex items-center justify-between bg-neutral-900/60 backdrop-blur rounded-xl">
        <div className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-md bg-violet-500/20 border border-violet-500/30 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-violet-300" />
          </div>
          <div className="font-semibold tracking-tight">OpenFilmAI</div>
          <span className="ml-3 text-[11px] px-2 py-0.5 rounded-full bg-neutral-800 border border-neutral-700 text-neutral-300">
            Preview
          </span>
          {/* Project menu */}
          <Dialog.Root>
            <Dialog.Trigger asChild>
              <button className="button text-xs">Project: {projectId}</button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 bg-black/60" />
              <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] card p-5">
                <Dialog.Title className="text-sm font-semibold mb-2">Projects</Dialog.Title>
                <Dialog.Description className="text-xs text-neutral-400 mb-3">
                  Create or switch projects. Projects are stored in project_data/.
                </Dialog.Description>
                <ProjectPicker projectId={projectId} onSwitch={(pid) => { setProjectId(pid); localStorage.setItem('projectId', pid); }} />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-neutral-400">Backend: {health}</div>
          <Dialog.Root open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
            <Dialog.Trigger asChild>
              <button className="button">
                <Settings2 className="w-4 h-4" />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 bg-black/60" />
              <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] card p-5">
                <Dialog.Title className="text-sm font-semibold mb-2">Settings</Dialog.Title>
                <Dialog.Description className="text-xs text-neutral-400 mb-4">
                  API keys and credentials (stored locally).
                </Dialog.Description>
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs text-neutral-400 mb-1">Replicate API Token</label>
                    <input className="field" value={settings.replicate_api_token ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, replicate_api_token: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs text-neutral-400 mb-1">ElevenLabs API Key</label>
                    <input className="field" value={settings.elevenlabs_api_key ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, elevenlabs_api_key: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs text-neutral-400 mb-1">Wavespeed API Key</label>
                    <input className="field" value={settings.wavespeed_api_key ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, wavespeed_api_key: e.target.value }))} />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs text-neutral-400 mb-1">Vertex Service Account JSON Path</label>
                    <input className="field" value={settings.vertex_service_account_path ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, vertex_service_account_path: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs text-neutral-400 mb-1">Vertex Project ID</label>
                    <input className="field" value={settings.vertex_project_id ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, vertex_project_id: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs text-neutral-400 mb-1">Vertex Location</label>
                    <input className="field" value={settings.vertex_location ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, vertex_location: e.target.value }))} />
                  </div>
                </div>
                <div className="mt-4 flex justify-end gap-2">
                  <Dialog.Close asChild>
                    <button className="button">Close</button>
                  </Dialog.Close>
                  <button
                    className="button-primary"
                    onClick={async () => {
                      await fetch('http://127.0.0.1:8000/settings', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(settings)
                      });
                      setIsSettingsOpen(false);
                    }}
                  >
                    Save
                  </button>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
      </div>

      {/* Left: Media & Character Library */}
      <aside className="border border-neutral-800 p-4 overflow-y-auto bg-neutral-900/60 rounded-xl">
        <h2 className="text-sm font-semibold mb-3">Library</h2>

        <div className="flex items-center justify-between mb-2">
          <div className="text-xs uppercase tracking-wide text-neutral-400">Scenes</div>
          <Dialog.Root open={isAddSceneOpen} onOpenChange={setIsAddSceneOpen}>
            <Dialog.Trigger asChild>
              <button className="button text-xs px-2 py-1">
                <Plus className="w-3 h-3" />
                Add
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 bg-black/60" />
              <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] card p-5 shadow-lg">
                <Dialog.Title className="text-sm font-semibold mb-3">Add Scene</Dialog.Title>
                <Dialog.Description className="text-xs text-neutral-400 mb-2">
                  Create a scene to hold shots on the timeline.
                </Dialog.Description>
                <label className="block text-xs text-neutral-400 mb-1">Title</label>
                <input
                  className="field"
                  value={newSceneTitle}
                  onChange={(e) => setNewSceneTitle(e.target.value)}
                />
                <div className="mt-4 flex justify-end gap-2">
                  <Dialog.Close asChild>
                    <button className="button">Cancel</button>
                  </Dialog.Close>
                  <button
                    onClick={async () => {
                      const sceneId = `scene_${String(scenes.length + 1).padStart(3, '0')}`;
                      const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ scene_id: sceneId, title: newSceneTitle })
                      });
                      const data = await res.json();
                      if (data.status === 'ok') {
                        const s = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`).then((r) => r.json());
                        setScenes(s.scenes ?? []);
                        setIsAddSceneOpen(false);
                      }
                    }}
                    className="button-primary"
                  >
                    Save
                  </button>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>

        <div className="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
          {scenes.length === 0 ? (
            <div className="text-xs text-neutral-500 card p-3">No scenes yet.</div>
          ) : (
            scenes.map((s) => (
              <button
                key={s.scene_id}
                onClick={() => setSelectedSceneId(s.scene_id)}
                className={`w-full text-left p-3 rounded-xl border bg-neutral-900/40 ${selectedSceneId === s.scene_id ? 'border-violet-600' : 'border-neutral-800 hover:border-neutral-700'}`}
              >
                <div className="text-sm font-semibold">{s.title}</div>
                <div className="text-[11px] text-neutral-500 mt-0.5">{s.scene_id}</div>
              </button>
            ))
          )}
        </div>

        <div className="mt-6 text-xs uppercase tracking-wide text-neutral-400 mb-2">Media</div>
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-semibold">Files</div>
          <div className="flex items-center gap-2">
              <button className="button text-xs px-2 py-1 disabled:opacity-50" disabled={health !== 'ok'} onClick={() => fileInputRef.current?.click()}>
              Import
            </button>
            <button
              className="button text-xs px-2 py-1"
              onClick={async () => {
                await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/scan`, { method: 'POST' });
                await refreshMedia();
              }}
            >
              Scan
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="video/*,audio/*,image/*"
              className="hidden"
              onChange={async (e) => {
                // Capture the input element before any await
                const inputEl = e.currentTarget;
                const files = Array.from(inputEl.files || []);
                if (files.length === 0) return;
                for (const f of files) {
                  const form = new FormData();
                  form.append('file', f);
                  try {
                    const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`, { method: 'POST', body: form });
                    // If backend is down, this will throw and we break out to show alert once
                    const data = await res.json();
                    if (data.status !== 'ok') {
                      throw new Error('Upload failed');
                    }
                  } catch (err) {
                    alert('Upload failed. Is the backend running? Try: source .venv/bin/activate && pip install -r requirements.txt && npm run dev');
                    break;
                  }
                }
                await refreshMedia();
                if (inputEl) inputEl.value = '';
              }}
            />
          </div>
        </div>
        <div
          className="space-y-2 max-h-[28vh] overflow-y-auto pr-1 rounded-md border border-neutral-800"
          onDragOver={(e) => {
            e.preventDefault();
          }}
          onDrop={async (e) => {
            e.preventDefault();
            const files = Array.from(e.dataTransfer.files || []);
            for (const f of files) {
              const form = new FormData();
              form.append('file', f);
              await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`, { method: 'POST', body: form }).catch(() => {});
            }
            await refreshMedia();
          }}
        >
          {media.length === 0 ? (
            <div className="text-xs text-neutral-500">No files yet.</div>
          ) : (
            media.map((m) => (
              <button
                key={m.id}
                className={`w-full text-left text-sm text-neutral-300 inline-flex items-center gap-2 hover:underline ${selectedMediaId === m.id ? 'text-violet-300' : ''}`}
                onClick={() => {
                  setSelectedMediaId(m.id);
                  selectMediaForPlayback(m);
                }}
              >
                <FolderOpen className="w-4 h-4" /> {m.id}
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Center: Timeline & Preview */}
      <main className="overflow-hidden">
        <div className="h-full card p-5 bg-grid-dots bg-grid-dots">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">Timeline & Preview</h2>
            <div className="flex items-center gap-2">
              <Dialog.Root
                open={isGenOpen}
                onOpenChange={async (open) => {
                  setIsGenOpen(open);
                  if (open) {
                    const s = await fetch('http://127.0.0.1:8000/settings').then((r) => r.json()).catch(() => ({ settings: {} }));
                    setSettings(s.settings ?? {});
                  }
                }}
              >
                <Dialog.Trigger asChild>
                  <button className="button disabled:opacity-50" disabled={health !== 'ok'}>
                    <Video className="w-4 h-4" /> Generate Shot
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/60" />
                  <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[640px] max-h-[85vh] overflow-y-auto card p-5">
                    <Dialog.Title className="text-sm font-semibold mb-3">Generate Shot</Dialog.Title>
                    <Dialog.Description className="text-xs text-neutral-400 mb-3">
                      Generate a shot (choose provider). Continuity option uses the last frame of the previous shot.
                    </Dialog.Description>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">Provider</label>
                        <select className="field" value={provider} onChange={(e) => setProvider(e.target.value as any)}>
                          <option value="replicate">Replicate (Veo)</option>
                          <option value="vertex">Vertex (Veo 3.1)</option>
                        </select>
                      </div>
                    </div>
                    {provider === 'vertex' ? (
                      <div className="space-y-3 mb-3">
                        <div className="flex items-center gap-4">
                          <label className="inline-flex items-center gap-2 text-xs text-neutral-300">
                            <input
                              type="radio"
                              name="vxImageMode"
                              checked={vxImageMode === 'none'}
                              onChange={() => {
                                setVxImageMode('none');
                                setVxUsePrevLast(false);
                                setVxStartImageId(null);
                                setVxEndImageId(null);
                                setVxRefImageIds([]);
                                setVxEndFromVideoId(null);
                                setVxEndFramePath(null);
                              }}
                            />
                            No provided images
                          </label>
                          <label className="inline-flex items-center gap-2 text-xs text-neutral-300">
                            <input
                              type="radio"
                              name="vxImageMode"
                              checked={vxImageMode === 'start_end'}
                              onChange={() => {
                                setVxImageMode('start_end');
                                setVxRefImageIds([]);
                              }}
                            />
                            Start/End frames
                          </label>
                          <label className="inline-flex items-center gap-2 text-xs text-neutral-300">
                            <input
                              type="radio"
                              name="vxImageMode"
                              checked={vxImageMode === 'reference'}
                              onChange={() => {
                                setVxImageMode('reference');
                                setVxUsePrevLast(false);
                                setVxStartImageId(null);
                                setVxEndImageId(null);
                                setVxEndFromVideoId(null);
                                setVxEndFramePath(null);
                              }}
                            />
                            Reference images
                          </label>
                        </div>
                        <label className="inline-flex items-center gap-2 text-xs text-neutral-300">
                          <input
                            type="checkbox"
                            checked={vxUsePrevLast && vxImageMode === 'start_end'}
                            onChange={(e) => {
                              setVxImageMode('start_end');
                              setVxUsePrevLast(e.target.checked);
                              if (e.target.checked) {
                                setVxStartImageId(null);
                                setVxRefImageIds([]);
                              }
                            }}
                          />
                          Use previous shot's last frame as start
                        </label>
                        {vxImageMode === 'start_end' ? (
                        <>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">Start frame (image)</label>
                            <select
                              className="field"
                              disabled={vxUsePrevLast}
                              value={vxStartImageId ?? ''}
                              onChange={(e) => setVxStartImageId(e.target.value || null)}
                            >
                              <option value="">None</option>
                              {media.filter((m) => m.type === 'image').map((m) => (
                                <option key={m.id} value={m.id}>{m.id}</option>
                              ))}
                            </select>
                            {/* Preview */}
                            {vxStartImageId ? (
                              <div className="mt-2">
                                <img
                                  src={`http://127.0.0.1:8000${media.find(m => m.id === vxStartImageId)?.url ?? ''}`}
                                  className="w-full h-24 object-cover rounded border border-neutral-800"
                                />
                              </div>
                            ) : null}
                          </div>
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">End frame (image)</label>
                            <select
                              className="field"
                              disabled={false}
                              value={vxEndImageId ?? ''}
                              onChange={(e) => setVxEndImageId(e.target.value || null)}
                            >
                              <option value="">None</option>
                              {media.filter((m) => m.type === 'image').map((m) => (
                                <option key={m.id} value={m.id}>{m.id}</option>
                              ))}
                            </select>
                            {vxEndImageId ? (
                              <div className="mt-2">
                                <img
                                  src={`http://127.0.0.1:8000${media.find(m => m.id === vxEndImageId)?.url ?? ''}`}
                                  className="w-full h-24 object-cover rounded border border-neutral-800"
                                />
                              </div>
                            ) : null}
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">End frame from video</label>
                            <select
                              className="field"
                              value={vxEndFromVideoId ?? ''}
                              onChange={(e) => setVxEndFromVideoId(e.target.value || null)}
                            >
                              <option value="">None</option>
                              {media.filter((m) => m.type === 'video').map((m) => (
                                <option key={m.id} value={m.id}>{m.id}</option>
                              ))}
                            </select>
                            <button
                              className="button text-[11px] px-2 py-1 mt-2"
                              disabled={!vxEndFromVideoId}
                              onClick={async () => {
                                const vid = media.find(m => m.id === vxEndFromVideoId);
                                if (!vid) return;
                                const r = await fetch('http://127.0.0.1:8000/frames/last', {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ project_id: projectId, video_path: vid.path })
                                });
                                const d = await r.json();
                                if (d.status === 'ok') {
                                  setVxEndFramePath(d.image_path);
                                  setVxImageMode('start_end');
                                } else {
                                  alert(d.detail || 'Failed to extract last frame');
                                }
                              }}
                            >
                              Extract last frame
                            </button>
                          </div>
                          <div>
                            {vxEndFramePath ? (
                              <div className="mt-6">
                                <div className="text-[11px] text-neutral-400 mb-1">Extracted end frame</div>
                                <img
                                  src={`http://127.0.0.1:8000/files/${vxEndFramePath.replace('project_data/', '')}`}
                                  className="w-full h-24 object-cover rounded border border-neutral-800"
                                />
                              </div>
                            ) : null}
                          </div>
                        </div>
                        </>
                        ) : null}
                        <div>
                          <label className="block text-xs text-neutral-400 mb-1">Reference images (mutually exclusive with start/end)</label>
                          <div className="flex flex-wrap gap-2">
                            {media.filter((m) => m.type === 'image').map((m) => {
                              const selected = vxRefImageIds.includes(m.id);
                              return (
                                <button
                                  key={m.id}
                                  disabled={vxImageMode !== 'reference'}
                                  className={`button text-[11px] px-2 py-1 ${selected ? 'border-violet-500' : ''}`}
                                  onClick={() => {
                                    setVxRefImageIds((prev) =>
                                      selected ? prev.filter((id) => id !== m.id) : [...prev, m.id]
                                    );
                                  }}
                                >
                                  {selected ? '✓ ' : ''}{m.id}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    ) : null}
                    <label className="block text-xs text-neutral-400 mb-1">Prompt</label>
                    <textarea
                      className="field h-28"
                      value={genPrompt}
                      onChange={(e) => setGenPrompt(e.target.value)}
                    />
                    <label className="mt-3 inline-flex items-center gap-2 text-sm text-neutral-300">
                      <input type="checkbox" checked={isContPrevFrame} onChange={(e) => setIsContPrevFrame(e.target.checked)} />
                      Use last frame of previous shot as reference
                    </label>
                    <div className="mt-4 flex justify-end gap-2">
                      <Dialog.Close asChild>
                        <button className="button">Cancel</button>
                      </Dialog.Close>
                      <button
                        onClick={async () => {
                          if (!selectedSceneId) return;
                          let reference_frame: string | undefined = undefined;
                          if (isContPrevFrame && (sceneDetail?.shots?.length ?? 0) > 0) {
                            const last = sceneDetail!.shots[sceneDetail!.shots.length - 1];
                            const ref = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${last.shot_id}/last-frame`).then((r) => r.json());
                            if (ref.status === 'ok') {
                              reference_frame = ref.path;
                            }
                          }
                          setIsGenerating(true);
                          const startFramePath =
                            provider === 'vertex'
                              ? (vxUsePrevLast ? reference_frame : (vxStartImageId ? media.find(m => m.id === vxStartImageId)?.path : undefined))
                              : reference_frame;
                        const endFramePath =
                          provider === 'vertex'
                            ? (vxEndFramePath ?? (vxEndImageId ? media.find(m => m.id === vxEndImageId)?.path : undefined))
                            : undefined;
                          const refImages =
                            provider === 'vertex' ? vxRefImageIds.map(id => media.find(m => m.id === id)?.path!).filter(Boolean) : undefined;
                          const res = await fetch('http://127.0.0.1:8000/ai/generate-shot', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              project_id: projectId,
                              scene_id: selectedSceneId,
                              prompt: genPrompt,
                              provider,
                              model: provider === 'replicate' ? 'google/veo-3.1' : 'veo-3.1-generate-preview',
                              duration: 8,
                              resolution: '1080p',
                              aspect_ratio: '16:9',
                              reference_frame: provider === 'replicate' ? reference_frame : undefined,
                              start_frame_path: startFramePath,
                              end_frame_path: endFramePath,
                              reference_images: refImages
                            })
                          });
                          const data = await res.json();
                          if (data.status === 'ok') {
                            const url = `http://127.0.0.1:8000${data.file_url}`;
                            setCurrentVideoUrl(url);
                            setNowPlaying(url);
                            setPlayError('');
                            // refresh detail
                            const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                            setSceneDetail(d.scene ?? null);
                            setIsGenOpen(false);
                          } else {
                            alert(data.detail || 'Generation failed');
                          }
                          setIsGenerating(false);
                        }}
                        className="button-primary"
                      >
                        {isGenerating ? 'Generating…' : 'Generate'}
                      </button>
                    </div>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <button
                className="button"
                onClick={() => {
                  if (!sceneDetail?.shots?.length) return;
                  setPlayIdx(0);
                  const first = sceneDetail.shots[0];
                  const videoRel = first.file_path?.replace('project_data/', '');
                  const vidUrl = videoRel?.startsWith('project_data') ? `http://127.0.0.1:8000/files/${videoRel.replace('project_data/', '')}` : `http://127.0.0.1:8000/files/${videoRel ?? ''}`;
                  setCurrentImageUrl(null);
                  setCurrentVideoUrl(vidUrl);
                }}
              >
                <Play className="w-4 h-4" /> Play Scene
              </button>
              <button
                className="button disabled:opacity-50"
                disabled={!selectedMediaId}
                onClick={async () => {
                  if (!selectedSceneId) {
                    // auto-create first scene
                    const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ scene_id: 'scene_001', title: 'Scene 001' })
                    });
                    const d = await res.json();
                    if (d.status === 'ok') setSelectedSceneId('scene_001');
                    const s = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`).then((r) => r.json());
                    setScenes(s.scenes ?? []);
                  }
                  const mediaItem = media.find((m) => m.id === selectedMediaId);
                  if (!mediaItem) return;
                  const shotId = `import_${Date.now()}`;
                  await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId || 'scene_001'}/shots`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      shot_id: shotId,
                      file_path: mediaItem.path,
                      duration: 8
                    })
                  });
                  const d2 = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId || 'scene_001'}`).then((r) => r.json());
                  setSceneDetail(d2.scene ?? null);
                }}
              >
                + Add to Timeline
              </button>
            </div>
          </div>

          <div className="rounded-xl overflow-hidden border border-neutral-800 bg-black/40 aspect-video">
            {currentImageUrl ? (
              <img src={currentImageUrl} className="w-full h-full object-contain bg-black" />
            ) : currentVideoUrl ? (
              <video
                key={currentVideoUrl}
                ref={videoRef}
                src={currentVideoUrl}
                controls
                playsInline
                preload="metadata"
                crossOrigin="anonymous"
                style={{ width: '100%', height: '100%', background: 'black' }}
                onLoadedMetadata={() => {
                  const dur = videoRef.current?.duration;
                  console.log('Loaded metadata, duration=', dur);
                }}
                onCanPlay={() => {
                  console.log('Video can play');
                }}
                onError={(e) => {
                  const el = videoRef.current;
                  // @ts-ignore
                  const err = el?.error;
                  console.error('Native video error', err);
                  setPlayError(`Video error code=${err?.code ?? 'n/a'}`);
                }}
                onEnded={() => {
                  if (playIdx >= 0 && sceneDetail?.shots?.length) {
                    const next = playIdx + 1;
                    if (next < sceneDetail.shots.length) {
                      setPlayIdx(next);
                      const sh = sceneDetail.shots[next];
                      const videoRel = sh.file_path?.replace('project_data/', '');
                      const vidUrl = videoRel?.startsWith('project_data') ? `http://127.0.0.1:8000/files/${videoRel.replace('project_data/', '')}` : `http://127.0.0.1:8000/files/${videoRel ?? ''}`;
                      setCurrentImageUrl(null);
                      setCurrentVideoUrl(vidUrl);
                      setNowPlaying(vidUrl);
                      debugHead(vidUrl);
                    } else {
                      setPlayIdx(-1);
                    }
                  }
                }}
              />
            ) : (
              <div className="w-full h-full grid place-items-center text-sm text-neutral-500">
                No video selected.
              </div>
            )}
          </div>
          <div className="mt-2 text-xs text-neutral-400">
            {nowPlaying ? (
              <>
                Now playing: <a className="underline" href={nowPlaying} target="_blank" rel="noreferrer">{nowPlaying}</a>
                {headInfo?.status ? (
                  <span className="ml-2">
                    [HEAD {headInfo.status} {headInfo.type || ''} {headInfo.length ? `${headInfo.length}B` : ''}]
                  </span>
                ) : null}
                {/* Copy URL button removed per user preference */}
              </>
            ) : null}
            {playError ? <div className="text-red-400 mt-1">{playError}</div> : null}
          </div>

          {/* Shots row with basic edit controls */}
          <div className="mt-4">
            <div className="text-xs uppercase tracking-wide text-neutral-400 mb-2">Shots</div>
            <div className="flex gap-2 overflow-x-auto pr-1 items-center">
              {(sceneDetail?.shots || []).map((sh: any) => {
                const thumbPath = sh.first_frame_path?.replace('project_data/', '');
                const thumbUrl = thumbPath ? `http://127.0.0.1:8000/files/${thumbPath}` : null;
                const videoRel = sh.file_path?.replace('project_data/', '');
                const vidUrl = videoRel?.startsWith('project_data') ? `http://127.0.0.1:8000/files/${videoRel.replace('project_data/', '')}` : `http://127.0.0.1:8000/files/${videoRel ?? ''}`;
                const duration = Math.max(0.5, (sh.duration ?? 8) - (sh.start_offset ?? 0) - (sh.end_offset ?? 0));
                const widthPx = Math.max(120, duration * 40);
                return (
                  <div key={sh.shot_id} className="rounded-lg overflow-hidden border border-neutral-800 bg-neutral-900/50" style={{ width: `${widthPx}px` }}>
                    <button onClick={() => setCurrentVideoUrl(vidUrl)} className="w-full text-left">
                      <div className="aspect-video bg-black/60">
                        {thumbUrl ? <img src={thumbUrl} className="w-full h-full object-cover" /> : null}
                      </div>
                    </button>
                    <div className="p-2 text-left space-y-2">
                      <div className="text-xs text-neutral-300 break-all">{sh.shot_id}</div>
                      <div className="flex items-center gap-2">
                        <button
                          className="button text-[11px] px-2 py-1"
                          onClick={async () => {
                            const newStart = Math.max(0, (sh.start_offset ?? 0) + 0.5);
                            await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${sh.shot_id}`, {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ start_offset: newStart })
                            });
                            const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                            setSceneDetail(d.scene ?? null);
                          }}
                        >
                          Trim L +
                        </button>
                        <button
                          className="button text-[11px] px-2 py-1"
                          onClick={async () => {
                            const newEnd = Math.max(0, (sh.end_offset ?? 0) + 0.5);
                            await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${sh.shot_id}`, {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ end_offset: newEnd })
                            });
                            const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                            setSceneDetail(d.scene ?? null);
                          }}
                        >
                          Trim R +
                        </button>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          defaultValue={sh.volume ?? 1}
                          onChange={async (e) => {
                            const v = parseFloat(e.currentTarget.value);
                            await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${sh.shot_id}`, {
                              method: 'PUT',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ volume: v })
                            });
                          }}
                        />
                        <button
                          className="button text-[11px] px-2 py-1"
                          onClick={async () => {
                            await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${sh.shot_id}`, {
                              method: 'DELETE'
                            });
                            const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                            setSceneDetail(d.scene ?? null);
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          {initStatus && (
            <div className="mt-3 text-xs text-neutral-300">{initStatus}</div>
          )}
        </div>
      </main>

      {/* Right: Inspector */}
      <aside className="border border-neutral-800 p-4 overflow-y-auto bg-neutral-900/60 rounded-xl">
        <h2 className="text-sm font-semibold mb-2">Inspector</h2>
        <div className="text-sm text-neutral-400">Shot/Scene/Character details, prompts, continuity, frames.</div>
      </aside>
    </div>
  );
}


