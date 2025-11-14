import React, { useEffect, useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Plus, FolderOpen, Sparkles, Settings2, Video, Play } from 'lucide-react';

type Health = { status: string };
type Character = {
  character_id: string;
  name: string;
  voice_id?: string;
  style_tokens?: string;
  reference_image_ids?: string[];
};

type Job = { id: string; label: string; status: 'running' | 'done' | 'error'; detail?: string };

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
  const [genAudio, setGenAudio] = useState<boolean>(false);
  const [isVoiceOpen, setIsVoiceOpen] = useState<boolean>(false);
  const [voiceText, setVoiceText] = useState<string>('');
  const [voiceId, setVoiceId] = useState<string>('');
  const [voiceMode, setVoiceMode] = useState<'tts' | 'v2v'>('tts');
  const [voiceCharacterId, setVoiceCharacterId] = useState<string>('');
  const [selectedAudioId, setSelectedAudioId] = useState<string | null>(null);
  const recordingRef = useRef<MediaRecorder | null>(null);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordedAudioUrl, setRecordedAudioUrl] = useState<string | null>(null);
  const [recordedMediaPath, setRecordedMediaPath] = useState<string | null>(null);
  const [voiceOutputName, setVoiceOutputName] = useState<string>('');
  const [isLipOpen, setIsLipOpen] = useState<boolean>(false);
  const [lipMode, setLipMode] = useState<'video' | 'image'>('video');
  const [lipVideoId, setLipVideoId] = useState<string | null>(null);
  const [lipImageId, setLipImageId] = useState<string | null>(null);
  const [lipAudioId, setLipAudioId] = useState<string | null>(null);
  const [lipPrompt, setLipPrompt] = useState<string>('');
  const [lipOutputName, setLipOutputName] = useState<string>('');
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
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [previewHeight, setPreviewHeight] = useState<number>(400);
  const [draggedShotId, setDraggedShotId] = useState<string | null>(null);
  const [mediaFilter, setMediaFilter] = useState<'all' | 'image' | 'video' | 'audio'>('all');
  // Prompt history for each generation type
  const [shotPromptHistory, setShotPromptHistory] = useState<string[]>([]);
  const [shotPromptHistoryIndex, setShotPromptHistoryIndex] = useState<number>(-1);
  const [voiceTTSHistory, setVoiceTTSHistory] = useState<string[]>([]);
  const [voiceTTSHistoryIndex, setVoiceTTSHistoryIndex] = useState<number>(-1);
  const [lipSyncPromptHistory, setLipSyncPromptHistory] = useState<string[]>([]);
  const [lipSyncPromptHistoryIndex, setLipSyncPromptHistoryIndex] = useState<number>(-1);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null);
  const [isCharacterModalOpen, setIsCharacterModalOpen] = useState<boolean>(false);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  const [newCharacterName, setNewCharacterName] = useState<string>('New Character');
  const [newCharacterVoice, setNewCharacterVoice] = useState<string>('');
  const [newCharacterStyle, setNewCharacterStyle] = useState<string>('');
  const [newCharacterImages, setNewCharacterImages] = useState<string[]>([]);
  // Vertex inputs and generation state
  const [vxUsePrevLast, setVxUsePrevLast] = useState<boolean>(false);
  const [vxStartImageId, setVxStartImageId] = useState<string | null>(null);
  const [vxEndImageId, setVxEndImageId] = useState<string | null>(null);
  const [vxRefImageIds, setVxRefImageIds] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [vxStartFromVideoId, setVxStartFromVideoId] = useState<string | null>(null);
  const [vxStartFramePath, setVxStartFramePath] = useState<string | null>(null);
  const [vxEndFromVideoId, setVxEndFromVideoId] = useState<string | null>(null);
  const [vxEndFramePath, setVxEndFramePath] = useState<string | null>(null);
  const [vxImageMode, setVxImageMode] = useState<'none' | 'start_end' | 'reference'>('none');
  const imageMedia = media.filter((m) => m.type === 'image');
  const audioMedia = media.filter((m) => m.type === 'audio');
  const videoMedia = media.filter((m) => m.type === 'video');
  const selectedCharacter = selectedCharacterId ? characters.find((c) => c.character_id === selectedCharacterId) : null;
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  const [showInspector, setShowInspector] = useState<boolean>(false);
  const [continuitySettings, setContinuitySettings] = useState<Record<string, { useLastFrame: boolean; applyOpticalFlow: boolean }>>({});
  
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
            setSelectedSceneId(list[list.length - 1].scene_id);
          }
          // If no scenes exist, create a default scene and select it
          if (list.length === 0) {
            const defaultId = 'scene_001';
            try {
              const cres = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scene_id: defaultId, title: 'Scene 001' })
              });
              if (cres.ok) {
                const d2 = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`).then((r) => r.json());
                setScenes(d2.scenes ?? []);
                setSelectedSceneId(defaultId);
              }
            } catch (_) {}
          }
        }
      } catch (_) {
        if (!cancelled) setScenes([]);
      }
      // Load characters
      try {
        const data = await fetch(`http://127.0.0.1:8000/storage/${projectId}/characters`).then((r) => r.json());
        const list = data.characters ?? [];
        if (!cancelled) {
          setCharacters(list);
          if (!selectedCharacterId && list.length > 0) setSelectedCharacterId(list[0].character_id);
        }
      } catch (_) {
        if (!cancelled) setCharacters([]);
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

  async function refreshCharacters() {
    const data = await fetch(`http://127.0.0.1:8000/storage/${projectId}/characters`).then((r) => r.json());
    const list = data.characters ?? [];
    setCharacters(list);
    if (!selectedCharacterId && list.length > 0) {
      setSelectedCharacterId(list[0].character_id);
    } else if (selectedCharacterId && !list.find((c: Character) => c.character_id === selectedCharacterId)) {
      setSelectedCharacterId(list.length ? list[0].character_id : null);
    }
  }

  function startJob(label: string): string {
    const id = `job_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    setJobs((jobs) => [...jobs, { id, label, status: 'running' }]);
    return id;
  }

  function finishJob(id: string, status: 'done' | 'error', detail?: string) {
    setJobs((jobs) =>
      jobs.map((job) => (job.id === id ? { ...job, status, detail } : job))
    );
    setTimeout(() => {
      setJobs((jobs) => jobs.filter((job) => job.id !== id));
    }, 4000);
  }

  function openCharacterModal(char?: Character) {
    if (char) {
      setEditingCharacter(char);
      setNewCharacterName(char.name);
      setNewCharacterVoice(char.voice_id ?? '');
      setNewCharacterStyle(char.style_tokens ?? '');
      setNewCharacterImages(char.reference_image_ids ?? []);
    } else {
      setEditingCharacter(null);
      setNewCharacterName('New Character');
      setNewCharacterVoice('');
      setNewCharacterStyle('');
      setNewCharacterImages([]);
    }
    setIsCharacterModalOpen(true);
  }

  function MediaPreviewCard({
    item,
    selected,
    onSelect,
  }: {
    item: any;
    selected: boolean;
    onSelect: () => void;
  }) {
    const url = `http://127.0.0.1:8000${item.url}`;
    return (
      <button
        className={`rounded-lg border p-1 w-24 h-28 flex flex-col items-center justify-center text-[10px] ${
          selected ? 'border-violet-500 text-violet-200' : 'border-neutral-700 text-neutral-300'
        }`}
        onClick={onSelect}
      >
        {item.type === 'image' ? (
          <img src={url} className="w-full h-16 object-cover rounded" />
        ) : item.type === 'video' ? (
          <video src={url} className="w-full h-16 object-cover rounded" muted playsInline />
        ) : (
          <div className="w-full h-16 bg-neutral-900/60 rounded flex items-center justify-center text-[12px]">
            Audio
          </div>
        )}
        <span className="mt-1 truncate w-full">{item.id}</span>
        {selected ? <span className="text-violet-300">✓</span> : null}
      </button>
    );
  }

  async function handleSaveCharacter() {
    const payload = {
      character_id: editingCharacter?.character_id ?? `char_${Date.now()}`,
      name: newCharacterName || editingCharacter?.name || 'Untitled',
      voice_id: newCharacterVoice || undefined,
      style_tokens: newCharacterStyle || undefined,
      reference_image_ids: newCharacterImages
    };
    const method = editingCharacter ? 'PUT' : 'POST';
    const url = editingCharacter
      ? `http://127.0.0.1:8000/storage/${projectId}/characters/${editingCharacter.character_id}`
      : `http://127.0.0.1:8000/storage/${projectId}/characters`;
    await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    await refreshCharacters();
    setIsCharacterModalOpen(false);
    setEditingCharacter(null);
  }

  async function handleDeleteCharacter(id: string) {
    if (!confirm('Delete this character?')) return;
    await fetch(`http://127.0.0.1:8000/storage/${projectId}/characters/${id}`, { method: 'DELETE' });
    await refreshCharacters();
    if (selectedCharacterId === id) {
      setSelectedCharacterId(null);
    }
  }

  async function startRecording() {
    try {
      // Stop existing recording if any
      if (recordingRef.current) {
        recordingRef.current.stop();
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.push(ev.data);
      };
      recorder.onstop = async () => {
        setIsRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks, { type: 'audio/webm' });
        setRecordedAudioUrl(URL.createObjectURL(blob));
        const file = new File([blob], `recording_${Date.now()}.webm`, { type: blob.type });
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`, {
          method: 'POST',
          body: form
        });
        const data = await res.json();
        if (data.status === 'ok') {
          setRecordedMediaPath(data.item?.path ?? null);
          await refreshMedia();
        } else {
          alert(data.detail || 'Failed to upload recording');
        }
      };
      recorder.start();
      recordingRef.current = recorder;
      setIsRecording(true);
      setRecordedMediaPath(null);
    } catch (err: any) {
      console.error(err);
      alert(err?.message || 'Unable to access microphone');
    }
  }

  function stopRecording() {
    if (recordingRef.current) {
      recordingRef.current.stop();
      recordingRef.current = null;
    }
  }

  async function handleVoiceGenerate() {
    const char = voiceCharacterId
      ? characters.find((c) => c.character_id === voiceCharacterId)
      : selectedCharacter;
    const resolvedVoiceId = voiceId || char?.voice_id || undefined;
    const jobId = startJob(voiceMode === 'tts' ? 'Generating voice (TTS)' : 'Generating voice (V2V)');
    try {
      if (voiceMode === 'tts') {
        if (!voiceText.trim()) {
          finishJob(jobId, 'error', 'No text provided');
          alert('Enter text for TTS.');
          return;
        }
        const r = await fetch('http://127.0.0.1:8000/ai/voice/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: projectId, text: voiceText, voice_id: resolvedVoiceId, filename: voiceOutputName || undefined })
        });
        const d = await r.json();
        if (d.status !== 'ok') {
          throw new Error(d.detail || 'Voice generation failed');
        }
      } else {
        const audioPath =
          recordedMediaPath ||
          (selectedAudioId ? media.find((m) => m.id === selectedAudioId)?.path : undefined);
        if (!audioPath) {
          finishJob(jobId, 'error', 'Select or record audio');
          alert('Select or record audio for voice-to-voice.');
          return;
        }
        const r = await fetch('http://127.0.0.1:8000/ai/voice/v2v', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: projectId,
            source_wav: audioPath,
            voice_id: resolvedVoiceId,
            filename: voiceOutputName || undefined
          })
        });
        const d = await r.json();
        if (d.status !== 'ok') {
          throw new Error(d.detail || 'Voice conversion failed');
        }
      }
      // Save TTS text to history
      if (voiceMode === 'tts' && voiceText.trim()) {
        setVoiceTTSHistory(prev => {
          const filtered = prev.filter(p => p !== voiceText.trim());
          return [...filtered, voiceText.trim()].slice(-20);
        });
        setVoiceTTSHistoryIndex(-1);
      }
      await refreshMedia();
      setIsVoiceOpen(false);
      setVoiceText('');
      setSelectedAudioId(null);
      setRecordedAudioUrl(null);
      setRecordedMediaPath(null);
      finishJob(jobId, 'done');
    } catch (err: any) {
      console.error(err);
      finishJob(jobId, 'error', err?.message || 'Voice generation error');
      alert(err?.message || 'Voice generation error');
    }
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

  useEffect(() => {
    // Prefill reference images when a character with references is active on Vertex provider
    if (provider !== 'vertex') return;
    const char = selectedCharacterId ? characters.find((c) => c.character_id === selectedCharacterId) : null;
    if (char?.reference_image_ids?.length) {
      setVxImageMode('reference');
      setVxRefImageIds(char.reference_image_ids);
    }
  }, [selectedCharacterId, provider, characters]);

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
    <div className="h-screen flex flex-col bg-neutral-950">
      {/* Top bar */}
          <div className="h-14 border-b border-neutral-800 px-4 flex items-center justify-between bg-neutral-900/60 backdrop-blur flex-shrink-0">
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
          {jobs.length ? (
            <div className="flex flex-wrap gap-2 max-w-[420px]">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className={`px-2 py-1 rounded-lg border text-[11px] ${
                    job.status === 'running'
                      ? 'border-amber-400 text-amber-200'
                      : job.status === 'done'
                      ? 'border-emerald-400 text-emerald-200'
                      : 'border-red-400 text-red-200'
                  }`}
                >
                  {job.status === 'running' ? '⏳' : job.status === 'done' ? '✅' : '⚠️'} {job.label}
                </div>
              ))}
            </div>
          ) : null}
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
                  <div className="col-span-2">
                    <label className="block text-xs text-neutral-400 mb-1">Vertex Temp GCS Bucket</label>
                    <input className="field" placeholder="your-bucket-name" value={settings.vertex_temp_bucket ?? ''} onChange={(e) => setSettings((s: any) => ({ ...s, vertex_temp_bucket: e.target.value }))} />
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

      {/* Main workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Compact Media & Character Library */}
        <aside className="w-64 border-r border-neutral-800 p-3 overflow-y-auto bg-neutral-900/40 flex-shrink-0">
          <h2 className="text-xs font-semibold mb-3 uppercase tracking-wide text-neutral-400">Library</h2>

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

        <div className="mt-6 mb-2">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs uppercase tracking-wide text-neutral-400">Media</div>
            <div className="flex items-center gap-1">
              <button className="button text-[10px] px-2 py-1 disabled:opacity-50" disabled={health !== 'ok'} onClick={() => fileInputRef.current?.click()}>
                Import
              </button>
              <button
                className="button text-[10px] px-2 py-1"
                onClick={async () => {
                  await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/scan`, { method: 'POST' });
                  await refreshMedia();
                }}
              >
                Scan
              </button>
            </div>
          </div>
          <div className="flex gap-1 flex-wrap">
            <button
              className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'all' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
              onClick={() => setMediaFilter('all')}
            >
              All ({media.length})
            </button>
            <button
              className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'image' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
              onClick={() => setMediaFilter('image')}
            >
              Images ({imageMedia.length})
            </button>
            <button
              className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'video' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
              onClick={() => setMediaFilter('video')}
            >
              Videos ({videoMedia.length})
            </button>
            <button
              className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'audio' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
              onClick={() => setMediaFilter('audio')}
            >
              Audio ({audioMedia.length})
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between mb-2 hidden">
          <div className="text-sm font-semibold">Files</div>
          <div className="flex items-center gap-2">
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
          {(() => {
            const filtered = mediaFilter === 'all' ? media : media.filter(m => m.type === mediaFilter);
            return filtered.length === 0 ? (
              <div className="text-xs text-neutral-500">No {mediaFilter === 'all' ? '' : mediaFilter} files yet.</div>
            ) : (
              filtered.map((m) => (
                <button
                  key={m.id}
                  className={`w-full text-left text-[11px] text-neutral-300 inline-flex items-center gap-2 hover:underline ${selectedMediaId === m.id ? 'text-violet-300' : ''}`}
                  onClick={() => {
                    setSelectedMediaId(m.id);
                    selectMediaForPlayback(m);
                  }}
                >
                  <FolderOpen className="w-3 h-3" /> {m.id}
                </button>
              ))
            );
          })()}
        </div>

        <div className="mt-6 text-xs uppercase tracking-wide text-neutral-400 mb-2">Characters</div>
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-semibold">Characters</div>
          <button className="button text-xs px-2 py-1" onClick={() => openCharacterModal()}>
            <Plus className="w-3 h-3" /> Add
          </button>
        </div>
        <div className="space-y-2 max-h-[30vh] overflow-y-auto pr-1">
          {characters.length === 0 ? (
            <div className="text-xs text-neutral-500 card p-3">No characters yet.</div>
          ) : (
            characters.map((c) => (
              <div
                key={c.character_id}
                className={`p-2 rounded-lg border cursor-pointer transition-all ${
                  selectedCharacterId === c.character_id ? 'border-violet-500 bg-violet-500/10' : 'border-neutral-800 bg-neutral-900/40 hover:border-neutral-700'
                }`}
                onClick={() => setSelectedCharacterId(c.character_id)}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="text-xs font-medium truncate">{c.name}</div>
                  <div className="flex gap-0.5">
                    <button
                      className="text-neutral-500 hover:text-neutral-300 p-1"
                      onClick={(e) => { e.stopPropagation(); openCharacterModal(c); }}
                      title="Edit"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      className="text-neutral-500 hover:text-red-400 p-1"
                      onClick={(e) => { e.stopPropagation(); handleDeleteCharacter(c.character_id); }}
                      title="Delete"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div className="text-[10px] text-neutral-500 truncate">
                  {c.voice_id || 'No voice'} • {c.reference_image_ids?.length ?? 0} refs
                </div>
              </div>
            ))
          )}
        </div>
        <Dialog.Root open={isCharacterModalOpen} onOpenChange={(open) => { setIsCharacterModalOpen(open); if (!open) setEditingCharacter(null); }}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/60" />
            <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] card p-5 max-h-[85vh] overflow-y-auto">
              <Dialog.Title className="text-sm font-semibold mb-3">
                {editingCharacter ? 'Edit Character' : 'Add Character'}
              </Dialog.Title>
              <label className="block text-xs text-neutral-400 mb-1">Name</label>
              <input className="field mb-2" value={newCharacterName} onChange={(e) => setNewCharacterName(e.target.value)} />
              <label className="block text-xs text-neutral-400 mb-1">ElevenLabs Voice ID</label>
              <input className="field mb-2" value={newCharacterVoice} onChange={(e) => setNewCharacterVoice(e.target.value)} placeholder="voice-..." />
              <label className="block text-xs text-neutral-400 mb-1">Style Tokens</label>
              <textarea className="field h-20 mb-2" value={newCharacterStyle} onChange={(e) => setNewCharacterStyle(e.target.value)} placeholder="ethereal, victorian, ..."></textarea>
              <div className="mb-2 text-xs text-neutral-400">Reference images (with preview)</div>
              <div className="flex flex-wrap gap-2 max-h-[200px] overflow-y-auto">
                {imageMedia.length === 0 ? (
                  <div className="text-xs text-neutral-500">Import images first.</div>
                ) : (
                  imageMedia.map((img) => {
                    const selected = newCharacterImages.includes(img.id);
                    const imgUrl = `http://127.0.0.1:8000${img.url}`;
                    return (
                      <button
                        key={img.id}
                        className={`rounded-lg border p-1 w-20 h-20 flex flex-col items-center justify-center text-[10px] ${
                          selected ? 'border-violet-500 text-violet-200' : 'border-neutral-700 text-neutral-300'
                        }`}
                        onClick={(e) => {
                          e.preventDefault();
                          setNewCharacterImages((prev) =>
                            prev.includes(img.id) ? prev.filter((id) => id !== img.id) : [...prev, img.id]
                          );
                        }}
                      >
                        <img src={imgUrl} className="w-full h-12 object-cover rounded" />
                        <span className="mt-1 truncate w-full">{img.id}</span>
                        {selected ? <span className="text-violet-300">✓</span> : null}
                      </button>
                    );
                  })
                )}
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <Dialog.Close asChild>
                  <button className="button">Cancel</button>
                </Dialog.Close>
                <button className="button-primary" onClick={handleSaveCharacter}>
                  Save
                </button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
        </aside>

        {/* Center: Main workspace with video preview + horizontal timeline */}
        {/* Center + Right Panel */}
        <div className="flex-1 flex overflow-hidden">
        <main className="flex-1 flex flex-col overflow-hidden border-r border-neutral-800">
          {/* Action bar */}
          <div className="h-12 border-b border-neutral-800 px-4 flex items-center justify-between bg-neutral-900/20 flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="text-xs text-neutral-400">
                Scene: <span className="text-neutral-200">{selectedSceneId || 'None'}</span>
              </div>
              {(sceneDetail?.shots || []).length > 0 ? (
                <div className="flex items-center gap-1 border-l border-neutral-700 pl-3">
                  <button
                    className="button text-xs px-2 py-1"
                    onClick={() => {
                      if (!sceneDetail?.shots?.length) return;
                      setPlayIdx(0);
                      const sh = sceneDetail.shots[0];
                      const videoRel = sh.file_path?.replace('project_data/', '');
                      const vidUrl = videoRel?.startsWith('project_data') ? `http://127.0.0.1:8000/files/${videoRel.replace('project_data/', '')}` : `http://127.0.0.1:8000/files/${videoRel ?? ''}`;
                      setCurrentImageUrl(null);
                      setCurrentVideoUrl(vidUrl);
                      setNowPlaying(vidUrl);
                      setTimeout(() => videoRef.current?.play(), 100);
                    }}
                  >
                    <Play className="w-3 h-3" /> Play Scene
                  </button>
                  {playIdx >= 0 ? (
                    <div className="text-[10px] text-neutral-500">
                      Playing {playIdx + 1}/{sceneDetail?.shots?.length ?? 0}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
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
                  <button className="button">
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
                      <div className="flex items-end">
                        <label className="inline-flex items-center gap-2 text-xs text-neutral-300">
                          <input
                            type="checkbox"
                            checked={genAudio}
                            onChange={(e) => setGenAudio(e.target.checked)}
                          />
                          Generate audio (costs more; Veo default off)
                        </label>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">Character</label>
                        <select className="field" value={selectedCharacterId ?? ''} onChange={(e) => setSelectedCharacterId(e.target.value || null)}>
                          <option value="">None</option>
                          {characters.map((c) => (
                            <option key={c.character_id} value={c.character_id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      {selectedCharacter ? (
                        <div className="text-xs text-neutral-400 mt-6">
                          Voice: {selectedCharacter.voice_id || 'unset'} {selectedCharacter.reference_image_ids?.length ? `• ${selectedCharacter.reference_image_ids.length} refs` : ''}
                        </div>
                      ) : (
                        <div className="text-xs text-neutral-500 mt-6">No character selected</div>
                      )}
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
                                setVxStartFromVideoId(null);
                                setVxStartFramePath(null);
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
                                setVxStartFromVideoId(null);
                                setVxStartFramePath(null);
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
                        {/* Preview of last frame when vxUsePrevLast is checked */}
                        {vxUsePrevLast && (sceneDetail?.shots || []).length > 0 ? (
                          (() => {
                            const lastShot = (sceneDetail?.shots || [])[(sceneDetail?.shots || []).length - 1];
                            const lastFramePath = lastShot?.last_frame_path?.replace('project_data/', '');
                            return lastFramePath ? (
                              <div className="mt-2 p-2 bg-violet-500/10 border border-violet-500/30 rounded">
                                <div className="text-[10px] text-violet-400 mb-1">Preview: Last frame from previous shot</div>
                                <img
                                  src={`http://127.0.0.1:8000/files/${lastFramePath}`}
                                  className="w-full h-24 object-cover rounded border border-violet-500/50"
                                  alt="Last frame preview"
                                />
                              </div>
                            ) : (
                              <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-[10px] text-red-400">
                                Previous shot has no last frame
                              </div>
                            );
                          })()
                        ) : null}
                        {vxImageMode === 'start_end' ? (
                        <>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">Start frame (image)</label>
                            <select
                              className="field"
                              disabled={vxUsePrevLast}
                              value={vxStartImageId ?? ''}
                              onChange={(e) => {
                                setVxStartImageId(e.target.value || null);
                                if (e.target.value) {
                                  setVxStartFromVideoId(null);
                                  setVxStartFramePath(null);
                                }
                              }}
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
                            <label className="block text-xs text-neutral-400 mb-1 mt-3">OR Start from video's last frame</label>
                            <select
                              className="field"
                              disabled={vxUsePrevLast}
                              value={vxStartFromVideoId ?? ''}
                              onChange={(e) => {
                                setVxStartFromVideoId(e.target.value || null);
                                if (e.target.value) {
                                  setVxStartImageId(null);
                                }
                              }}
                            >
                              <option value="">None</option>
                              {media.filter((m) => m.type === 'video').map((m) => (
                                <option key={m.id} value={m.id}>{m.id}</option>
                              ))}
                            </select>
                            <button
                              className="button text-[11px] px-2 py-1 mt-2"
                              disabled={!vxStartFromVideoId}
                              onClick={async () => {
                                const vid = media.find(m => m.id === vxStartFromVideoId);
                                if (!vid) return;
                                const r = await fetch('http://127.0.0.1:8000/frames/last', {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ project_id: projectId, video_path: vid.path })
                                });
                                const d = await r.json();
                                if (d.status === 'ok') {
                                  setVxStartFramePath(d.image_path);
                                  setVxImageMode('start_end');
                                } else {
                                  alert(d.detail || 'Failed to extract last frame');
                                }
                              }}
                            >
                              Extract as start
                            </button>
                            {vxStartFramePath ? (
                              <div className="mt-2">
                                <div className="text-[11px] text-neutral-400 mb-1">Extracted start frame</div>
                                <img
                                  src={`http://127.0.0.1:8000/files/${vxStartFramePath.replace('project_data/', '')}`}
                                  className="w-full h-24 object-cover rounded border border-neutral-800"
                                />
                              </div>
                            ) : null}
                          </div>
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">End frame (image, optional)</label>
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
                            <div className="text-[10px] text-neutral-500 mt-1">
                              Note: End frame requires a start frame (for interpolation)
                            </div>
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
                    <label className="block text-xs text-neutral-400 mb-1">
                      Prompt {shotPromptHistory.length > 0 ? <span className="text-neutral-600">(↑↓ for history)</span> : null}
                    </label>
                    <textarea
                      className="field h-28"
                      value={genPrompt}
                      onChange={(e) => {
                        setGenPrompt(e.target.value);
                        setShotPromptHistoryIndex(-1);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowUp') {
                          e.preventDefault();
                          if (shotPromptHistory.length === 0) return;
                          const newIndex = shotPromptHistoryIndex < shotPromptHistory.length - 1 ? shotPromptHistoryIndex + 1 : shotPromptHistoryIndex;
                          setShotPromptHistoryIndex(newIndex);
                          setGenPrompt(shotPromptHistory[shotPromptHistory.length - 1 - newIndex]);
                        } else if (e.key === 'ArrowDown') {
                          e.preventDefault();
                          if (shotPromptHistoryIndex === -1) return;
                          const newIndex = shotPromptHistoryIndex > 0 ? shotPromptHistoryIndex - 1 : -1;
                          setShotPromptHistoryIndex(newIndex);
                          if (newIndex === -1) {
                            setGenPrompt('');
                          } else {
                            setGenPrompt(shotPromptHistory[shotPromptHistory.length - 1 - newIndex]);
                          }
                        }
                      }}
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
                          let jobId: string | null = null;
                          try {
                            // Ensure a scene is selected; auto-create if missing
                            if (!selectedSceneId) {
                              const sceneId = `scene_${String(scenes.length + 1 || 1).padStart(3, '0')}`;
                              const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ scene_id: sceneId, title: `Scene ${sceneId.split('_').pop()}` })
                              }).catch(() => null);
                              if (res && res.ok) {
                                const s = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes`).then((r) => r.json()).catch(() => ({ scenes: [] }));
                                setScenes(s.scenes ?? []);
                                setSelectedSceneId(sceneId);
                              } else {
                                alert('Could not create a scene. Try again.');
                                return;
                              }
                            }
                            let reference_frame: string | undefined = undefined;
                            if (isContPrevFrame && (sceneDetail?.shots?.length ?? 0) > 0) {
                              const last = sceneDetail!.shots[sceneDetail!.shots.length - 1];
                              const ref = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${last.shot_id}/last-frame`).then((r) => r.json());
                              if (ref.status === 'ok') {
                                reference_frame = ref.path;
                              }
                            }
                            setIsGenerating(true);
                            // Enforce exclusivity in payload
                            let startFramePath: string | undefined = undefined;
                            let endFramePath: string | undefined = undefined;
                            let refImages: string[] | undefined = undefined;
                            const activeChar = selectedCharacterId ? characters.find((c) => c.character_id === selectedCharacterId) : null;
                            const charRefPaths = activeChar?.reference_image_ids
                              ?.map((id) => media.find((m) => m.id === id)?.path)
                              .filter(Boolean) as string[] | undefined;
                            const promptWithStyle =
                              activeChar?.style_tokens && activeChar.style_tokens.trim().length
                                ? `${genPrompt}\nCharacter style: ${activeChar.style_tokens}`
                                : genPrompt;
                            if (provider === 'vertex') {
                              if (vxImageMode === 'reference') {
                                const manualRefs = vxRefImageIds.map(id => media.find(m => m.id === id)?.path!).filter(Boolean) as string[];
                                refImages = manualRefs.length ? manualRefs : (charRefPaths ?? undefined);
                                startFramePath = undefined;
                                endFramePath = undefined;
                              } else if (vxImageMode === 'start_end') {
                                // Priority: vxUsePrevLast > vxStartFramePath (extracted from video) > vxStartImageId
                                if (vxUsePrevLast) {
                                  // Fetch last frame from previous shot
                                  const shots = sceneDetail?.shots || [];
                                  const lastShot = shots[shots.length - 1];
                                  if (lastShot?.last_frame_path) {
                                    startFramePath = lastShot.last_frame_path;
                                  } else {
                                    alert('Previous shot has no last frame. Generate a shot first or select a start frame manually.');
                                    setIsGenerating(false);
                                    return;
                                  }
                                } else {
                                  startFramePath = vxStartFramePath || (vxStartImageId ? media.find(m => m.id === vxStartImageId)?.path : undefined);
                                }
                                // End frame is always an image (vxEndImageId selected)
                                endFramePath = vxEndImageId ? media.find(m => m.id === vxEndImageId)?.path : undefined;
                              } else {
                                // none
                                startFramePath = undefined;
                                endFramePath = undefined;
                                refImages = charRefPaths;
                              }
                            } else {
                              // Replicate uses reference_frame only
                              startFramePath = reference_frame;
                            }
                            jobId = startJob(`Generating shot ${selectedSceneId}`);
                            const payload = {
                              project_id: projectId,
                              scene_id: selectedSceneId,
                              prompt: promptWithStyle,
                              provider,
                              model: provider === 'replicate' ? 'google/veo-3.1' : 'veo-3.1-fast-generate-preview',
                              duration: 8,
                              resolution: '1080p',
                              aspect_ratio: '16:9',
                              reference_frame: provider === 'replicate' ? startFramePath : undefined,
                              start_frame_path: provider === 'vertex' ? startFramePath : undefined,
                              end_frame_path: provider === 'vertex' ? endFramePath : undefined,
                              reference_images: provider === 'vertex' ? refImages : undefined,
                              generate_audio: provider === 'replicate' ? genAudio : false
                            };
                            console.log('Generate payload', payload);
                            const res = await fetch('http://127.0.0.1:8000/ai/generate-shot', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify(payload)
                            });
                            const data = await res.json().catch(() => ({}));
                            if (res.ok && data.status === 'ok') {
                              // Save prompt to history
                              if (genPrompt.trim()) {
                                setShotPromptHistory(prev => {
                                  const filtered = prev.filter(p => p !== genPrompt.trim());
                                  return [...filtered, genPrompt.trim()].slice(-20); // Keep last 20
                                });
                                setShotPromptHistoryIndex(-1);
                              }
                              const url = `http://127.0.0.1:8000${data.file_url}`;
                              setCurrentVideoUrl(url);
                              setNowPlaying(url);
                              setPlayError('');
                              // refresh detail and media
                              const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                              setSceneDetail(d.scene ?? null);
                              await refreshMedia();
                              setIsGenOpen(false);
                              if (jobId) finishJob(jobId, 'done');
                            } else {
                              console.error('Generate failed', data);
                              if (jobId) finishJob(jobId, 'error', data.detail || `HTTP ${res.status}`);
                              alert(data.detail || `Generation failed (${res.status})`);
                            }
                          } catch (err: any) {
                            console.error('Generate error', err);
                            if (jobId) finishJob(jobId, 'error', err?.message || 'Generation error');
                            alert(`Generation error: ${err?.message || err}`);
                          } finally {
                            setIsGenerating(false);
                          }
                        }}
                        className="button-primary"
                      >
                        {isGenerating ? 'Generating…' : 'Generate'}
                      </button>
                    </div>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <Dialog.Root
                open={isVoiceOpen}
                onOpenChange={(open) => {
                  setIsVoiceOpen(open);
                  if (open) {
                    setVoiceMode('tts');
                    setVoiceText('');
                    setVoiceId(selectedCharacter?.voice_id ?? '');
                    setVoiceCharacterId(selectedCharacter?.character_id ?? '');
                    setSelectedAudioId(null);
                    setRecordedAudioUrl(null);
                    setRecordedMediaPath(null);
                    setVoiceOutputName('');
                  } else {
                    if (recordingRef.current) {
                      recordingRef.current.stop();
                      recordingRef.current = null;
                    }
                    setIsRecording(false);
                  }
                }}
              >
                <Dialog.Trigger asChild>
                  <button className="button">Generate Voice (ElevenLabs)</button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/60" />
                  <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] card p-5">
                    <Dialog.Title className="text-sm font-semibold mb-2">Generate Voice</Dialog.Title>
                    <Dialog.Description className="text-xs text-neutral-400 mb-3">
                      Create TTS or voice-to-voice clips. Select a character to auto-fill voice IDs.
                    </Dialog.Description>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div>
                      <label className="block text-xs text-neutral-400 mb-1">Character</label>
                      <select
                        className="field"
                        value={voiceCharacterId || selectedCharacterId || ''}
                        onChange={(e) => setVoiceCharacterId(e.target.value || '')}
                      >
                        <option value="">None</option>
                        {characters.map((c) => (
                          <option key={c.character_id} value={c.character_id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-neutral-400 mb-1">Override Voice ID</label>
                      <input
                        className="field"
                        value={voiceId}
                        onChange={(e) => setVoiceId(e.target.value)}
                        placeholder={selectedCharacter?.voice_id || 'voice-...'}
                      />
                    </div>
                  </div>
                  <div className="flex gap-4 text-xs text-neutral-400 mb-3">
                    <label className="inline-flex items-center gap-2">
                      <input type="radio" checked={voiceMode === 'tts'} onChange={() => setVoiceMode('tts')} />
                      Text → Voice
                    </label>
                    <label className="inline-flex items-center gap-2">
                      <input type="radio" checked={voiceMode === 'v2v'} onChange={() => setVoiceMode('v2v')} />
                      Voice → Voice
                    </label>
                  </div>
                  {voiceMode === 'tts' ? (
                    <>
                      <label className="block text-xs text-neutral-400 mb-1">
                        Text {voiceTTSHistory.length > 0 ? <span className="text-neutral-600">(↑↓ for history)</span> : null}
                      </label>
                      <textarea
                        className="field h-28"
                        value={voiceText}
                        onChange={(e) => {
                          setVoiceText(e.target.value);
                          setVoiceTTSHistoryIndex(-1);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'ArrowUp') {
                            e.preventDefault();
                            if (voiceTTSHistory.length === 0) return;
                            const newIndex = voiceTTSHistoryIndex < voiceTTSHistory.length - 1 ? voiceTTSHistoryIndex + 1 : voiceTTSHistoryIndex;
                            setVoiceTTSHistoryIndex(newIndex);
                            setVoiceText(voiceTTSHistory[voiceTTSHistory.length - 1 - newIndex]);
                          } else if (e.key === 'ArrowDown') {
                            e.preventDefault();
                            if (voiceTTSHistoryIndex === -1) return;
                            const newIndex = voiceTTSHistoryIndex > 0 ? voiceTTSHistoryIndex - 1 : -1;
                            setVoiceTTSHistoryIndex(newIndex);
                            if (newIndex === -1) {
                              setVoiceText('');
                            } else {
                              setVoiceText(voiceTTSHistory[voiceTTSHistory.length - 1 - newIndex]);
                            }
                          }
                        }}
                      />
                    </>
                  ) : (
                    <>
                      <label className="block text-xs text-neutral-400 mb-1">Source audio</label>
                      <select className="field mb-2" value={selectedAudioId ?? ''} onChange={(e) => setSelectedAudioId(e.target.value || null)}>
                        <option value="">Select audio</option>
                        {audioMedia.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.id}
                          </option>
                        ))}
                      </select>
                      <div className="flex items-center gap-2 mb-2">
                        <button className="button text-xs px-2 py-1" onClick={startRecording} disabled={isRecording}>
                          {isRecording ? 'Recording…' : 'Record'}
                        </button>
                        <button className="button text-xs px-2 py-1" onClick={stopRecording} disabled={!isRecording}>
                          Stop
                        </button>
                        {recordedAudioUrl ? <span className="text-xs text-neutral-400">Recorded clip saved</span> : null}
                      </div>
                      {recordedAudioUrl ? (
                        <audio controls src={recordedAudioUrl} className="w-full mb-2">
                          Your browser does not support audio playback.
                        </audio>
                      ) : null}
                    </>
                  )}
                  <label className="block text-xs text-neutral-400 mt-3 mb-1">Output name</label>
                  <input className="field" placeholder="e.g., Ruthven line 1" value={voiceOutputName} onChange={(e) => setVoiceOutputName(e.target.value)} />
                    <div className="mt-4 flex justify-end gap-2">
                      <Dialog.Close asChild><button className="button">Cancel</button></Dialog.Close>
                    <button className="button-primary" onClick={handleVoiceGenerate}>
                      Generate
                    </button>
                    </div>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <Dialog.Root
                open={isLipOpen}
                onOpenChange={(o) => {
                  setIsLipOpen(o);
                  if (o) {
                    setLipMode('video');
                    const latestVideo = [...media].reverse().find((m) => m.type === 'video');
                    const latestAudio = [...media].reverse().find((m) => m.type === 'audio');
                    const latestImage = [...media].reverse().find((m) => m.type === 'image');
                    setLipVideoId(latestVideo?.id ?? null);
                    setLipAudioId(latestAudio?.id ?? null);
                    setLipImageId(latestImage?.id ?? null);
                    setLipPrompt('');
                    setLipOutputName('');
                  } else {
                    setLipVideoId(null);
                    setLipAudioId(null);
                    setLipImageId(null);
                  }
                }}
              >
                <Dialog.Trigger asChild>
                  <button className="button">Lip-Sync (Wavespeed)</button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/60" />
                  <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] card p-5">
                    <Dialog.Title className="text-sm font-semibold mb-2">Lip-Sync (Wavespeed)</Dialog.Title>
                    <Dialog.Description className="text-xs text-neutral-400 mb-3">
                      Choose a video or reference image plus an audio clip. Result saves into your media library.
                    </Dialog.Description>
                    <div className="flex gap-4 text-xs text-neutral-400 mb-3">
                      <label className="inline-flex items-center gap-2">
                        <input type="radio" checked={lipMode === 'video'} onChange={() => setLipMode('video')} />
                        Video + Audio → Re-sync
                      </label>
                      <label className="inline-flex items-center gap-2">
                        <input type="radio" checked={lipMode === 'image'} onChange={() => setLipMode('image')} />
                        Image + Audio → Talking portrait
                      </label>
                    </div>
                    {lipMode === 'video' ? (
                      <div>
                        <div className="text-xs text-neutral-400 mb-1">Video clip</div>
                        <div className="flex flex-wrap gap-2 max-h-[150px] overflow-y-auto">
                          {videoMedia.length === 0 ? (
                            <div className="text-xs text-neutral-500">No videos yet.</div>
                          ) : (
                            videoMedia.map((item) => (
                              <MediaPreviewCard key={item.id} item={item} selected={lipVideoId === item.id} onSelect={() => setLipVideoId(item.id)} />
                            ))
                          )}
                        </div>
                      </div>
                    ) : (
                      <div>
                        <div className="text-xs text-neutral-400 mb-1">Reference image</div>
                        <div className="flex flex-wrap gap-2 max-h-[150px] overflow-y-auto">
                          {imageMedia.length === 0 ? (
                            <div className="text-xs text-neutral-500">No images yet.</div>
                          ) : (
                            imageMedia.map((item) => (
                              <MediaPreviewCard key={item.id} item={item} selected={lipImageId === item.id} onSelect={() => setLipImageId(item.id)} />
                            ))
                          )}
                        </div>
                      </div>
                    )}
                    <div className="mt-3">
                      <div className="text-xs text-neutral-400 mb-1">Audio</div>
                      <div className="flex flex-wrap gap-2 max-h-[120px] overflow-y-auto">
                        {audioMedia.length === 0 ? (
                          <div className="text-xs text-neutral-500">No audio files yet.</div>
                        ) : (
                          audioMedia.map((item) => (
                            <MediaPreviewCard key={item.id} item={item} selected={lipAudioId === item.id} onSelect={() => setLipAudioId(item.id)} />
                          ))
                        )}
                      </div>
                    </div>
                    <label className="block text-xs text-neutral-400 mt-3 mb-1">
                      Prompt / notes (optional) {lipSyncPromptHistory.length > 0 ? <span className="text-neutral-600">(↑↓ for history)</span> : null}
                    </label>
                    <textarea
                      className="field h-20"
                      value={lipPrompt}
                      onChange={(e) => {
                        setLipPrompt(e.target.value);
                        setLipSyncPromptHistoryIndex(-1);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowUp') {
                          e.preventDefault();
                          if (lipSyncPromptHistory.length === 0) return;
                          const newIndex = lipSyncPromptHistoryIndex < lipSyncPromptHistory.length - 1 ? lipSyncPromptHistoryIndex + 1 : lipSyncPromptHistoryIndex;
                          setLipSyncPromptHistoryIndex(newIndex);
                          setLipPrompt(lipSyncPromptHistory[lipSyncPromptHistory.length - 1 - newIndex]);
                        } else if (e.key === 'ArrowDown') {
                          e.preventDefault();
                          if (lipSyncPromptHistoryIndex === -1) return;
                          const newIndex = lipSyncPromptHistoryIndex > 0 ? lipSyncPromptHistoryIndex - 1 : -1;
                          setLipSyncPromptHistoryIndex(newIndex);
                          if (newIndex === -1) {
                            setLipPrompt('');
                          } else {
                            setLipPrompt(lipSyncPromptHistory[lipSyncPromptHistory.length - 1 - newIndex]);
                          }
                        }
                      }}
                      placeholder="e.g., keep mouth subtle, calm delivery"
                    />
                    <label className="block text-xs text-neutral-400 mt-3 mb-1">Output name</label>
                    <input className="field" placeholder="e.g., Scene1_Ruthven_lipsync" value={lipOutputName} onChange={(e) => setLipOutputName(e.target.value)} />
                    <div className="mt-4 flex justify-end gap-2">
                      <Dialog.Close asChild><button className="button">Cancel</button></Dialog.Close>
                      <button
                        className="button-primary"
                        disabled={(lipMode === 'video' ? !lipVideoId : !lipImageId) || !lipAudioId}
                        onClick={async () => {
                          const jobId = startJob(lipMode === 'video' ? 'Lip-sync video' : 'Lip-sync image');
                          try {
                            const audioItem = media.find((m) => m.id === lipAudioId);
                            if (!audioItem) {
                              finishJob(jobId, 'error', 'Select audio');
                              alert('Select audio file.');
                              return;
                            }
                            const body: any = {
                              project_id: projectId,
                              audio_wav_path: audioItem.path,
                              prompt: lipPrompt || undefined,
                              filename: lipOutputName || undefined
                            };
                            let endpoint: string;
                            
                            if (lipMode === 'video') {
                              endpoint = 'http://127.0.0.1:8000/ai/lipsync/video';
                              const videoItem = media.find((m) => m.id === lipVideoId);
                              if (!videoItem) {
                                finishJob(jobId, 'error', 'Select video');
                                alert('Select a video clip.');
                                return;
                              }
                              body.video_path = videoItem.path;
                            } else {
                              endpoint = 'http://127.0.0.1:8000/ai/lipsync/image';
                              const imageItem = media.find((m) => m.id === lipImageId);
                              if (!imageItem) {
                                finishJob(jobId, 'error', 'Select image');
                                alert('Select an image.');
                                return;
                              }
                              body.image_path = imageItem.path;
                            }
                            const r = await fetch(endpoint, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify(body)
                            });
                            const d = await r.json();
                            if (d.status === 'ok') {
                              // Save lip-sync prompt to history
                              if (lipPrompt.trim()) {
                                setLipSyncPromptHistory(prev => {
                                  const filtered = prev.filter(p => p !== lipPrompt.trim());
                                  return [...filtered, lipPrompt.trim()].slice(-20);
                                });
                                setLipSyncPromptHistoryIndex(-1);
                              }
                              await refreshMedia();
                              setIsLipOpen(false);
                              setCurrentVideoUrl(`http://127.0.0.1:8000${d.file_url}`);
                              finishJob(jobId, 'done');
                            } else {
                              alert(d.detail || 'Lip-sync failed');
                              finishJob(jobId, 'error', d.detail || 'Lip-sync failed');
                            }
                          } catch (e: any) {
                            alert(e?.message || 'Lip-sync error');
                            finishJob(jobId, 'error', e?.message || 'Lip-sync error');
                          }
                        }}
                      >Sync</button>
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

          {/* Video preview - resizable */}
          <div className="p-4 overflow-hidden flex flex-col items-center justify-center bg-black/20" style={{ height: `${previewHeight}px` }}>
            <div className="w-full h-full max-w-[1000px] rounded-lg overflow-hidden border border-neutral-800 bg-black relative">
              <div className="absolute top-2 right-2 z-10 flex gap-1">
                <button
                  className="bg-black/80 text-white text-[10px] px-2 py-1 rounded hover:bg-black"
                  onClick={() => setPreviewHeight(Math.max(200, previewHeight - 50))}
                >
                  −
                </button>
                <button
                  className="bg-black/80 text-white text-[10px] px-2 py-1 rounded hover:bg-black"
                  onClick={() => setPreviewHeight(Math.min(800, previewHeight + 50))}
                >
                  +
                </button>
              </div>
              {currentImageUrl ? (
                <img src={currentImageUrl} className="w-full h-full object-contain" />
              ) : currentVideoUrl ? (
                <video
                  key={currentVideoUrl}
                  ref={videoRef}
                  src={currentVideoUrl}
                  controls
                  playsInline
                  preload="metadata"
                  crossOrigin="anonymous"
                  className="w-full h-full"
                  onError={(e) => {
                    const el = videoRef.current;
                    // @ts-ignore
                    const err = el?.error;
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
                      } else {
                        setPlayIdx(-1);
                      }
                    }
                  }}
                />
              ) : (
                <div className="w-full h-full grid place-items-center text-neutral-500">
                  <div className="text-center">
                    <Video className="w-16 h-16 mx-auto mb-2 opacity-20" />
                    <div className="text-sm">No video selected</div>
                    <div className="text-xs text-neutral-600 mt-1">Click a shot below to preview</div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Horizontal timeline at bottom */}
          <div className="h-64 border-t border-neutral-800 bg-neutral-900/40 p-3 overflow-x-auto overflow-y-auto flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-500">Timeline • {(sceneDetail?.shots || []).length} shots</div>
              {playError ? <div className="text-[10px] text-red-400">{playError}</div> : null}
            </div>
            <div className="flex gap-1 items-start min-h-[200px]">
              {(sceneDetail?.shots || []).map((sh: any, idx: number) => {
                const thumbPath = sh.first_frame_path?.replace('project_data/', '');
                const thumbUrl = thumbPath ? `http://127.0.0.1:8000/files/${thumbPath}` : null;
                // Debug: log if thumbnail is missing
                if (!thumbUrl && sh.shot_id) {
                  console.log(`Shot ${sh.shot_id} missing first_frame_path:`, sh);
                }
                const videoRel = sh.file_path?.replace('project_data/', '');
                const vidUrl = videoRel?.startsWith('project_data') ? `http://127.0.0.1:8000/files/${videoRel.replace('project_data/', '')}` : `http://127.0.0.1:8000/files/${videoRel ?? ''}`;
                const duration = sh.duration ?? 8;
                const widthPx = Math.max(140, duration * 18);
                const isLastShot = idx === (sceneDetail?.shots || []).length - 1;
                const nextShot = !isLastShot ? (sceneDetail?.shots || [])[idx + 1] : null;
                const contKey = nextShot ? `${sh.shot_id}_to_${nextShot.shot_id}` : null;
                const contSettings = contKey ? continuitySettings[contKey] : null;
                
                return (
                  <React.Fragment key={sh.shot_id}>
                  <div
                    draggable
                    onDragStart={(e) => {
                      setDraggedShotId(sh.shot_id);
                      e.dataTransfer.effectAllowed = 'move';
                    }}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.dataTransfer.dropEffect = 'move';
                    }}
                    onDrop={async (e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (!draggedShotId || draggedShotId === sh.shot_id) return;
                      
                      // Reorder shots by swapping positions
                      const shots = sceneDetail?.shots || [];
                      const draggedIdx = shots.findIndex((s: any) => s.shot_id === draggedShotId);
                      const targetIdx = idx;
                      if (draggedIdx === -1 || targetIdx === -1) return;
                      
                      const newShots = [...shots];
                      const [removed] = newShots.splice(draggedIdx, 1);
                      newShots.splice(targetIdx, 0, removed);
                      
                      // Optimistic update
                      setSceneDetail({ ...sceneDetail, shots: newShots });
                      
                      // Update backend
                      const shotOrder = newShots.map((s: any) => s.shot_id);
                      try {
                        await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`, {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ shot_order: shotOrder })
                        });
                        // Refresh from backend to confirm
                        const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                        setSceneDetail(d.scene ?? null);
                      } catch (err) {
                        console.error('Failed to reorder shots:', err);
                        // Revert on error
                        const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                        setSceneDetail(d.scene ?? null);
                      }
                      setDraggedShotId(null);
                    }}
                    onDragEnd={() => setDraggedShotId(null)}
                    className={`flex-shrink-0 rounded-lg border bg-neutral-900/70 hover:border-violet-500/50 transition-all cursor-move group ${
                      draggedShotId === sh.shot_id ? 'opacity-50 border-violet-500' : selectedShotId === sh.shot_id ? 'border-violet-500 ring-2 ring-violet-500/30' : 'border-neutral-800'
                    }`}
                    style={{ width: `${widthPx}px` }}
                    onClick={() => {
                      setCurrentVideoUrl(vidUrl);
                      setNowPlaying(vidUrl);
                      setSelectedShotId(sh.shot_id);
                      setShowInspector(true);
                    }}
                  >
                    <div className="relative">
                      <div className="aspect-video bg-black/60 overflow-hidden">
                        {thumbUrl ? <img src={thumbUrl} className="w-full h-full object-cover" alt={`Shot ${idx + 1}`} /> : null}
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                          <Play className="w-8 h-8 text-white" />
                        </div>
                      </div>
                      <div className="absolute top-1 left-1 bg-black/80 text-white text-[10px] px-1.5 py-0.5 rounded">
                        {idx + 1}
                      </div>
                      <div className="absolute top-1 right-1 bg-black/80 text-white text-[10px] px-1.5 py-0.5 rounded">
                        {duration}s
                      </div>
                    </div>
                    <div className="p-2 space-y-1">
                      <div className="text-[10px] text-neutral-400 truncate max-w-full" title={sh.shot_id}>{sh.shot_id}</div>
                      <div className="flex gap-1 flex-wrap">
                        <button
                          className="button text-[9px] px-1.5 py-0.5 flex-1"
                          onClick={(e) => {
                            e.stopPropagation();
                            setIsVoiceOpen(true);
                            setVoiceOutputName(`${sh.shot_id}_voice`);
                          }}
                        >
                          Voice
                        </button>
                        <button
                          className="button text-[9px] px-1.5 py-0.5 flex-1"
                          onClick={(e) => {
                            e.stopPropagation();
                            // Pre-select this video for lip-sync
                            const videoId = media.find(m => m.path === sh.file_path)?.id;
                            if (videoId) {
                              setLipMode('video');
                              setLipVideoId(videoId);
                            }
                            setIsLipOpen(true);
                            setLipOutputName(`${sh.shot_id}_lipsync`);
                          }}
                        >
                          Lip
                        </button>
                        <button
                          className="button text-[9px] px-1.5 py-0.5 text-red-400"
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (!confirm('Delete?')) return;
                            await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${sh.shot_id}`, {
                              method: 'DELETE'
                            });
                            const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                            setSceneDetail(d.scene ?? null);
                            await refreshMedia();
                          }}
                        >
                          ×
                        </button>
                      </div>
                      {isLastShot ? (
                        <button
                          className="button text-[9px] px-1.5 py-0.5 w-full bg-violet-500/20 hover:bg-violet-500/30 text-violet-300 mt-1"
                          onClick={async (e) => {
                            e.stopPropagation();
                            // Check if this shot has a last frame
                            if (!sh.last_frame_path) {
                              alert('This shot has no last frame extracted yet.');
                              return;
                            }
                            // Auto-configure for continuity from THIS shot
                            setIsContPrevFrame(true);
                            setVxImageMode('start_end');
                            setVxUsePrevLast(true);
                            setVxStartImageId(null);
                            setVxStartFromVideoId(null);
                            setVxStartFramePath(null);
                            setVxEndImageId(null);
                            setIsGenOpen(true);
                          }}
                        >
                          + Continue →
                        </button>
                      ) : null}
                    </div>
                  </div>
                  
                  {/* Continuity Bar */}
                  {nextShot && contKey ? (
                    <div className="flex-shrink-0 flex flex-col items-center justify-center px-2 space-y-1">
                      <div className="text-[9px] text-neutral-600">→</div>
                      <div className="flex flex-col gap-1">
                        <label className="flex items-center gap-1 text-[9px] text-neutral-400 cursor-pointer hover:text-violet-400">
                          <input
                            type="checkbox"
                            checked={contSettings?.useLastFrame ?? false}
                            onChange={(e) => {
                              setContinuitySettings(prev => ({
                                ...prev,
                                [contKey]: { ...prev[contKey], useLastFrame: e.target.checked }
                              }));
                            }}
                            className="w-3 h-3"
                          />
                          <span>Use last</span>
                        </label>
                        <label className="flex items-center gap-1 text-[9px] text-neutral-400 cursor-pointer hover:text-violet-400">
                          <input
                            type="checkbox"
                            checked={contSettings?.applyOpticalFlow ?? false}
                            onChange={(e) => {
                              setContinuitySettings(prev => ({
                                ...prev,
                                [contKey]: { ...prev[contKey], applyOpticalFlow: e.target.checked }
                              }));
                            }}
                            className="w-3 h-3"
                          />
                          <span>Smooth</span>
                        </label>
                        {contSettings?.applyOpticalFlow ? (
                          <button
                            className="button text-[8px] px-1 py-0.5 bg-violet-500/20 hover:bg-violet-500/30"
                            onClick={async () => {
                              const jobId = `optical_${Date.now()}`;
                              setJobs(prev => [...prev, { id: jobId, label: `Merging clips with smooth transition...`, status: 'running' }]);
                              try {
                                const res = await fetch('http://127.0.0.1:8000/video/optical-flow', {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({
                                    project_id: projectId,
                                    scene_id: selectedSceneId,
                                    shot_a_id: sh.shot_id,
                                    shot_b_id: nextShot.shot_id,
                                    transition_frames: 15,
                                    replace_shots: true
                                  })
                                });
                                const data = await res.json();
                                if (data.status === 'ok') {
                                  await refreshMedia();
                                  // Refresh scene to show merged shot
                                  const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                                  setSceneDetail(d.scene ?? null);
                                  setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'done' } : j));
                                  // Clear continuity settings for this pair since they're now merged
                                  setContinuitySettings(prev => {
                                    const newSettings = { ...prev };
                                    delete newSettings[contKey!];
                                    return newSettings;
                                  });
                                } else {
                                  setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'error', detail: data.detail } : j));
                                  alert(`Error: ${data.detail}`);
                                }
                              } catch (e: any) {
                                setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'error', detail: e.message } : j));
                                alert(`Error: ${e.message}`);
                              }
                            }}
                          >
                            Apply
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                  </React.Fragment>
                );
              })}
              
              {/* Frame Planning Card - passive preview, doesn't auto-fill */}
              {selectedSceneId ? (
                <div className="flex-shrink-0 w-[400px] rounded-lg border-2 border-dashed border-neutral-700 bg-neutral-900/30 p-3">
                  <div className="text-[10px] text-neutral-500 uppercase tracking-wide mb-2 text-center">Plan Next Shot</div>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {/* Start Frame */}
                    <div className="space-y-1">
                      <div className="text-[9px] text-neutral-600 text-center">Start Frame</div>
                      <button
                        className="aspect-video bg-black/40 rounded border border-neutral-800 hover:border-violet-500/50 flex items-center justify-center text-[8px] text-neutral-600 overflow-hidden w-full transition-colors"
                        onClick={() => {
                          setVxImageMode('start_end');
                          setIsGenOpen(true);
                        }}
                      >
                        {vxStartImageId ? (
                          <img 
                            src={`http://127.0.0.1:8000/files/${media.find(m => m.id === vxStartImageId)?.path?.replace('project_data/', '')}`}
                            className="w-full h-full object-cover rounded"
                            alt="Start"
                          />
                        ) : vxStartFramePath ? (
                          <img 
                            src={`http://127.0.0.1:8000/files/${vxStartFramePath.replace('project_data/', '')}`}
                            className="w-full h-full object-cover rounded"
                            alt="Start"
                          />
                        ) : (
                          <div className="text-neutral-600">Click to select</div>
                        )}
                      </button>
                    </div>
                    
                    {/* Video Generation */}
                    <div className="space-y-1">
                      <div className="text-[9px] text-neutral-600 text-center">Video</div>
                      <div className="aspect-video bg-gradient-to-br from-violet-500/10 to-purple-500/10 rounded border border-violet-500/30 flex items-center justify-center">
                        <Video className="w-6 h-6 text-violet-400/50" />
                      </div>
                    </div>
                    
                    {/* End Frame */}
                    <div className="space-y-1">
                      <div className="text-[9px] text-neutral-600 text-center">End Frame</div>
                      <button
                        className="aspect-video bg-black/40 rounded border border-neutral-800 hover:border-violet-500/50 flex items-center justify-center text-[8px] text-neutral-600 w-full transition-colors"
                        onClick={() => {
                          setVxImageMode('start_end');
                          setIsGenOpen(true);
                        }}
                      >
                        {vxEndImageId ? (
                          <img 
                            src={`http://127.0.0.1:8000/files/${media.find(m => m.id === vxEndImageId)?.path?.replace('project_data/', '')}`}
                            className="w-full h-full object-cover rounded"
                            alt="End"
                          />
                        ) : (
                          <div className="text-neutral-600">Click to select</div>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  <button
                    className="button text-[10px] w-full bg-violet-500/20 hover:bg-violet-500/30 text-violet-300"
                    onClick={() => {
                      // Just open modal, don't auto-configure
                      setIsGenOpen(true);
                    }}
                  >
                    Generate Next Shot →
                  </button>
                </div>
              ) : null}
              
              {(sceneDetail?.shots || []).length === 0 ? (
                <div className="flex-1 grid place-items-center text-neutral-600 text-xs">
                  No shots yet. Click "Generate Shot" above to start.
                </div>
              ) : null}
            </div>
          </div>
        </main>

        {/* Right: Shot Inspector */}
        {showInspector && selectedShotId && (() => {
          const shot = sceneDetail?.shots?.find((s: any) => s.shot_id === selectedShotId);
          if (!shot) return null;
          const thumbPath = shot.first_frame_path?.replace('project_data/', '');
          const thumbUrl = thumbPath ? `http://127.0.0.1:8000/files/${thumbPath}` : null;
          const lastPath = shot.last_frame_path?.replace('project_data/', '');
          const lastUrl = lastPath ? `http://127.0.0.1:8000/files/${lastPath}` : null;
          return (
            <aside className="w-80 bg-neutral-900/40 overflow-y-auto p-4 flex-shrink-0">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-neutral-200">Shot Inspector</h3>
                <button className="text-neutral-400 hover:text-neutral-200" onClick={() => setShowInspector(false)}>×</button>
              </div>

              {/* Metadata */}
              <div className="space-y-3 text-xs">
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide mb-1">Shot ID</div>
                  <div className="text-neutral-200">{shot.shot_id}</div>
                </div>
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide mb-1">Duration</div>
                  <div className="text-neutral-200">{shot.duration ?? 8}s</div>
                </div>
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide mb-1">Provider</div>
                  <div className="text-neutral-200">{shot.provider ?? 'N/A'}</div>
                </div>
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide mb-1">Model</div>
                  <div className="text-neutral-200">{shot.model ?? 'N/A'}</div>
                </div>
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide mb-1">Prompt</div>
                  <div className="text-neutral-300 text-[11px] leading-relaxed">{shot.prompt ?? 'N/A'}</div>
                </div>

                {/* Frames */}
                <div>
                  <div className="text-neutral-500 uppercase tracking-wide mb-2">Frames</div>
                  <div className="grid grid-cols-2 gap-2">
                    {thumbUrl ? (
                      <div>
                        <div className="text-[10px] text-neutral-600 mb-1">Start</div>
                        <img src={thumbUrl} className="w-full aspect-video object-cover rounded border border-neutral-700" alt="Start" />
                      </div>
                    ) : null}
                    {lastUrl ? (
                      <div>
                        <div className="text-[10px] text-neutral-600 mb-1">End</div>
                        <img src={lastUrl} className="w-full aspect-video object-cover rounded border border-neutral-700" alt="End" />
                      </div>
                    ) : null}
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-3 border-t border-neutral-800 space-y-2">
                  <button
                    className="button w-full text-xs"
                    onClick={() => {
                      setIsVoiceOpen(true);
                      setVoiceOutputName(`${shot.shot_id}_voice`);
                    }}
                  >
                    Generate Voice
                  </button>
                  <button
                    className="button w-full text-xs"
                    onClick={() => {
                      // Pre-select this video for lip-sync
                      const videoId = media.find(m => m.path === shot.file_path)?.id;
                      if (videoId) {
                        setLipMode('video');
                        setLipVideoId(videoId);
                      }
                      setIsLipOpen(true);
                      setLipOutputName(`${shot.shot_id}_lipsync`);
                    }}
                  >
                    Apply Lip-Sync
                  </button>
                  <button
                    className="button w-full text-xs text-red-400"
                    onClick={async () => {
                      if (!confirm('Delete this shot?')) return;
                      await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}/shots/${shot.shot_id}`, {
                        method: 'DELETE'
                      });
                      const d = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`).then((r) => r.json());
                      setSceneDetail(d.scene ?? null);
                      setShowInspector(false);
                      setSelectedShotId(null);
                      await refreshMedia();
                    }}
                  >
                    Delete Shot
                  </button>
                </div>
              </div>
            </aside>
          );
        })()}
        </div>
      </div>
    </div>
  );
}