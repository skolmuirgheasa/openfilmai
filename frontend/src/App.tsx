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
  const [genMediaType, setGenMediaType] = useState<'video' | 'image'>('video');
  const [replicateModel, setReplicateModel] = useState<string>('google/veo-3.1');
  const [seedreamAspectRatio, setSeedreamAspectRatio] = useState<string>('16:9');
  const [seedreamNumOutputs, setSeedreamNumOutputs] = useState<number>(1);
  const [videoAspectRatio, setVideoAspectRatio] = useState<string>('16:9');
  const [replicateRefImages, setReplicateRefImages] = useState<string[]>([]);
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
  const [voiceStability, setVoiceStability] = useState<number>(() => {
    const saved = localStorage.getItem('voiceStability');
    return saved ? parseFloat(saved) : 0.5;
  });
  const [voiceSimilarity, setVoiceSimilarity] = useState<number>(() => {
    const saved = localStorage.getItem('voiceSimilarity');
    return saved ? parseFloat(saved) : 0.75;
  });
  const [voiceStyle, setVoiceStyle] = useState<number>(() => {
    const saved = localStorage.getItem('voiceStyle');
    return saved ? parseFloat(saved) : 0.0;
  });
  const [voiceSpeakerBoost, setVoiceSpeakerBoost] = useState<boolean>(() => {
    const saved = localStorage.getItem('voiceSpeakerBoost');
    return saved ? saved === 'true' : true;
  });
  const [voiceRemoveNoise, setVoiceRemoveNoise] = useState<boolean>(() => {
    const saved = localStorage.getItem('voiceRemoveNoise');
    return saved ? saved === 'true' : false;
  });
  const [isLipOpen, setIsLipOpen] = useState<boolean>(false);
  
  // Voice Scene Builder state
  type VoiceSceneSlot = {
    id: string;
    visualId: string | null; // media ID for image or video
    visualType: 'image' | 'video' | null;
    dialogueText: string;
    characterId: string | null;
    voiceId: string;
    recordedAudioPath: string | null;
    selectedAudioId: string | null;
    generatedVoiceId: string | null; // media ID after TTS/V2V
    generatedLipSyncId: string | null; // media ID after lip-sync
    lipSyncPrompt: string;
  };
  const [isVoiceSceneOpen, setIsVoiceSceneOpen] = useState<boolean>(false);
  const [voiceSceneSlots, setVoiceSceneSlots] = useState<VoiceSceneSlot[]>([]);
  const [voiceSceneName, setVoiceSceneName] = useState<string>('Untitled Voice Scene');
  const [voiceSceneRecordingSlotId, setVoiceSceneRecordingSlotId] = useState<string | null>(null);
  const voiceSceneRecorderRef = useRef<MediaRecorder | null>(null);
  
  // Multi-Character Lip-Sync state
  type CharacterBoundingBox = {
    box_id: string; // unique ID for this box instance
    character_id: string;
    character_name: string;
    x: number; // percentage 0-100
    y: number; // percentage 0-100
    width: number; // percentage 0-100
    height: number; // percentage 0-100
    audio_track_id: string | null; // which audio file is assigned to this character
  };
  const [isMultiLipSyncOpen, setIsMultiLipSyncOpen] = useState<boolean>(false);
  const [multiLipSyncImageId, setMultiLipSyncImageId] = useState<string | null>(null);
  const [multiLipSyncBoundingBoxes, setMultiLipSyncBoundingBoxes] = useState<CharacterBoundingBox[]>([]);
  const [multiLipSyncPrompt, setMultiLipSyncPrompt] = useState<string>('');
  const [multiLipSyncOutputName, setMultiLipSyncOutputName] = useState<string>('');
  const multiLipSyncCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [drawingBox, setDrawingBox] = useState<{ startX: number; startY: number; character_id: string } | null>(null);
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
  const [customModels, setCustomModels] = useState<any[]>([]);
  const [isAddCustomModelOpen, setIsAddCustomModelOpen] = useState<boolean>(false);
  const [customModelInput, setCustomModelInput] = useState<string>('');
  const [customModelFetching, setCustomModelFetching] = useState<boolean>(false);
  const [customModelPreview, setCustomModelPreview] = useState<any>(null);
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
  const [sourceFilter, setSourceFilter] = useState<'all' | 'generated' | 'uploaded' | 'extracted'>('all');
  // Prompt history for each generation type
  const [shotPromptHistory, setShotPromptHistory] = useState<string[]>([]);
  const [shotPromptHistoryIndex, setShotPromptHistoryIndex] = useState<number>(-1);
  const [voiceTTSHistory, setVoiceTTSHistory] = useState<string[]>([]);
  const [voiceTTSHistoryIndex, setVoiceTTSHistoryIndex] = useState<number>(-1);
  const [lipSyncPromptHistory, setLipSyncPromptHistory] = useState<string[]>([]);
  const [lipSyncPromptHistoryIndex, setLipSyncPromptHistoryIndex] = useState<number>(-1);
  
  // Prompt templates
  const [promptTemplates, setPromptTemplates] = useState<{name: string; prompt: string}[]>(() => {
    const stored = localStorage.getItem('promptTemplates');
    return stored ? JSON.parse(stored) : [
      { name: "Cinematic Shot", prompt: "A cinematic shot, 35mm film, shallow depth of field, professional color grading" },
      { name: "Character Close-up", prompt: "Close-up shot of [character], emotional expression, soft lighting, film grain" },
      { name: "Establishing Shot", prompt: "Wide establishing shot, golden hour lighting, atmospheric, cinematic composition" },
      { name: "Action Sequence", prompt: "Dynamic action shot, fast motion, dramatic lighting, high contrast" },
    ];
  });
  const [isTemplatesOpen, setIsTemplatesOpen] = useState<boolean>(false);
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
  // Sort media by ID (which contains timestamp) - newest first
  const sortedMedia = [...media].sort((a, b) => {
    // Extract timestamp from ID (e.g., "1763077360_voice.mp3" -> 1763077360)
    const getTimestamp = (id: string) => {
      const match = id.match(/^(\d+)/);
      return match ? parseInt(match[1]) : 0;
    };
    return getTimestamp(b.id) - getTimestamp(a.id);
  });
  
  const imageMedia = sortedMedia.filter((m) => m.type === 'image');
  const audioMedia = sortedMedia.filter((m) => m.type === 'audio');
  const videoMedia = sortedMedia.filter((m) => m.type === 'video');
  const selectedCharacter = selectedCharacterId ? characters.find((c) => c.character_id === selectedCharacterId) : null;
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  const [showInspector, setShowInspector] = useState<boolean>(false);
  const [continuitySettings, setContinuitySettings] = useState<Record<string, { useLastFrame: boolean; applyOpticalFlow: boolean }>>({});
  const [selectedMediaIds, setSelectedMediaIds] = useState<Set<string>>(new Set());
  const [showArchived, setShowArchived] = useState<boolean>(false);
  const [archivedMedia, setArchivedMedia] = useState<any[]>([]);
  
  // Auto-update voiceId when voiceCharacterId changes
  useEffect(() => {
    if (voiceCharacterId) {
      const char = characters.find((c) => c.character_id === voiceCharacterId);
      if (char?.voice_id) {
        setVoiceId(char.voice_id);
      }
    }
  }, [voiceCharacterId, characters]);
  
  // Persist voice settings to localStorage
  useEffect(() => {
    localStorage.setItem('voiceStability', voiceStability.toString());
  }, [voiceStability]);
  
  useEffect(() => {
    localStorage.setItem('voiceSimilarity', voiceSimilarity.toString());
  }, [voiceSimilarity]);
  
  useEffect(() => {
    localStorage.setItem('voiceStyle', voiceStyle.toString());
  }, [voiceStyle]);
  
  useEffect(() => {
    localStorage.setItem('voiceSpeakerBoost', voiceSpeakerBoost.toString());
  }, [voiceSpeakerBoost]);
  
  useEffect(() => {
    localStorage.setItem('voiceRemoveNoise', voiceRemoveNoise.toString());
  }, [voiceRemoveNoise]);
  
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
    const initial = stored || 'default';
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
      // Use first available project if current project doesn't exist
      try {
        const projs = await fetch('http://127.0.0.1:8000/storage/projects').then((r) => r.json());
        if (!cancelled && Array.isArray(projs?.projects) && projs.projects.length > 0) {
          // If current project doesn't exist, switch to first available
          if (!projs.projects.includes(projectId)) {
            const firstProject = projs.projects[0];
            localStorage.setItem('projectId', firstProject);
            setProjectId(firstProject);
            return;
          }
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
      // Load custom Replicate models
      try {
        const cm = await fetch('http://127.0.0.1:8000/settings/custom-models').then((r) => r.json());
        if (!cancelled) setCustomModels(cm.models ?? []);
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
    // Sort by most recent first (newest at top)
    const sorted = (m.media ?? []).sort((a: any, b: any) => {
      // Use timestamp field if available (more reliable)
      if (a.timestamp && b.timestamp) {
        return b.timestamp - a.timestamp;
      }
      // Fallback: Extract timestamp from filename
      const getTimestamp = (item: any) => {
        if (item.timestamp) return item.timestamp;
        // Pattern 1: "1763084012_video.mp4" or "1763084012.mp4"
        const match1 = item.id?.match(/^(\d{10,13})[_\.]/);
        if (match1) return parseInt(match1[1]);
        // Pattern 2: "wavespeed_1763084012.mp4" or "scene_002_shot_1763084012.mp4"
        const match2 = item.id?.match(/_(\d{10,13})[_\.]/);
        if (match2) return parseInt(match2[1]);
        // Pattern 3: Any 10-13 digit number in the filename
        const match3 = item.id?.match(/(\d{10,13})/);
        if (match3) return parseInt(match3[1]);
        // Fallback: use 0 (will sort to end)
        return 0;
      };
      return getTimestamp(b) - getTimestamp(a);
    });
    console.log('Media sorted:', sorted.length, 'items. Newest:', sorted[0]?.id, sorted[0]?.timestamp);
    setMedia(sorted);
  }

  async function showInFinder(mediaItem: any) {
    try {
      // Convert relative path to absolute path
      // mediaItem.path is like "project_data/vampyre/media/video/file.mp4"
      const response = await fetch(`http://127.0.0.1:8000/storage/show-in-finder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: mediaItem.path })
      });
      const data = await response.json();
      if (data.status !== 'ok') {
        alert(`Failed to show in Finder: ${data.detail}`);
      }
    } catch (err: any) {
      console.error('Show in Finder error:', err);
      alert(`Failed to show in Finder: ${err.message}`);
    }
  }
  
  function addVoiceSceneSlot() {
    const newSlot: VoiceSceneSlot = {
      id: `slot_${Date.now()}`,
      visualId: null,
      visualType: null,
      dialogueText: '',
      characterId: null,
      voiceId: '',
      recordedAudioPath: null,
      selectedAudioId: null,
      generatedVoiceId: null,
      generatedLipSyncId: null,
      lipSyncPrompt: ''
    };
    setVoiceSceneSlots([...voiceSceneSlots, newSlot]);
  }
  
  function removeVoiceSceneSlot(slotId: string) {
    setVoiceSceneSlots(voiceSceneSlots.filter(s => s.id !== slotId));
  }
  
  function updateVoiceSceneSlot(slotId: string, updates: Partial<VoiceSceneSlot>) {
    setVoiceSceneSlots(voiceSceneSlots.map(s => s.id === slotId ? { ...s, ...updates } : s));
  }
  
  async function startVoiceSceneRecording(slotId: string) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('file', blob, `voice_scene_${slotId}_${Date.now()}.webm`);
        formData.append('project_id', projectId);
        
        console.log('[Voice Scene Recording] Uploading recorded audio for slot:', slotId);
        const r = await fetch('http://127.0.0.1:8000/storage/' + projectId + '/media', {
          method: 'POST',
          body: formData
        });
        const d = await r.json();
        console.log('[Voice Scene Recording] Upload response:', d);
        
        if (d.status === 'ok' && d.item) {
          await refreshMedia();
          // Update slot with new recording, replacing any previous selection
          updateVoiceSceneSlot(slotId, { 
            recordedAudioPath: d.item.path, 
            selectedAudioId: d.item.id,
            generatedVoiceId: null // Clear generated voice since we have new source audio
          });
          console.log('[Voice Scene Recording] Slot updated with new audio:', d.item.id);
        }
        stream.getTracks().forEach(t => t.stop());
      };
      
      recorder.start();
      voiceSceneRecorderRef.current = recorder;
      setVoiceSceneRecordingSlotId(slotId);
      console.log('[Voice Scene Recording] Started recording for slot:', slotId);
    } catch (err: any) {
      console.error('[Voice Scene Recording] Error:', err);
      alert('Failed to start recording: ' + err.message);
    }
  }
  
  function stopVoiceSceneRecording() {
    if (voiceSceneRecorderRef.current) {
      console.log('[Voice Scene Recording] Stopping recording');
      voiceSceneRecorderRef.current.stop();
      voiceSceneRecorderRef.current = null;
    }
    setVoiceSceneRecordingSlotId(null);
  }
  
  function addCharacterBoundingBox() {
    if (!selectedCharacterId) {
      alert('Select a character first');
      return;
    }
    const char = characters.find(c => c.character_id === selectedCharacterId);
    if (!char) return;
    
    // Offset each new box slightly so they don't overlap
    const offset = multiLipSyncBoundingBoxes.length * 5;
    
    const newBox: CharacterBoundingBox = {
      box_id: `box_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      character_id: char.character_id,
      character_name: char.name,
      x: 25 + offset,
      y: 25 + offset,
      width: 20,
      height: 30,
      audio_track_id: null
    };
    setMultiLipSyncBoundingBoxes([...multiLipSyncBoundingBoxes, newBox]);
  }
  
  function removeCharacterBoundingBox(box_id: string) {
    setMultiLipSyncBoundingBoxes(multiLipSyncBoundingBoxes.filter(b => b.box_id !== box_id));
  }
  
  function updateCharacterBoundingBox(box_id: string, updates: Partial<CharacterBoundingBox>) {
    setMultiLipSyncBoundingBoxes(multiLipSyncBoundingBoxes.map(b => 
      b.box_id === box_id ? { ...b, ...updates } : b
    ));
  }
  
  async function generateMultiCharacterLipSync() {
    if (!multiLipSyncImageId) {
      alert('Select an image first');
      return;
    }
    if (multiLipSyncBoundingBoxes.length === 0) {
      alert('Add at least one character bounding box');
      return;
    }
    
    const unassignedBoxes = multiLipSyncBoundingBoxes.filter(b => !b.audio_track_id);
    if (unassignedBoxes.length > 0) {
      alert(`Assign audio to all characters. Missing: ${unassignedBoxes.map(b => b.character_name).join(', ')}`);
      return;
    }
    
    const image = media.find(m => m.id === multiLipSyncImageId);
    if (!image) {
      alert('Image not found');
      return;
    }
    
    const jobId = startJob('Multi-character lip-sync (may take 10-45 min)');
    console.log('[Multi-Character Lip-Sync] Starting with', multiLipSyncBoundingBoxes.length, 'characters');
    
    try {
      // Build the payload with character-to-audio mappings and bounding boxes
      const payload = {
        project_id: projectId,
        image_path: image.path,
        characters: multiLipSyncBoundingBoxes.map(box => {
          const audioItem = media.find(m => m.id === box.audio_track_id);
          return {
            character_id: box.character_id,
            character_name: box.character_name,
            audio_path: audioItem?.path,
            bounding_box: {
              x: box.x,
              y: box.y,
              width: box.width,
              height: box.height
            }
          };
        }),
        prompt: multiLipSyncPrompt || undefined,
        filename: multiLipSyncOutputName || undefined
      };
      
      console.log('[Multi-Character Lip-Sync] Payload:', payload);
      
      const r = await fetch('http://127.0.0.1:8000/ai/lipsync/multi-character', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const d = await r.json();
      console.log('[Multi-Character Lip-Sync] Response:', d);
      
      if (d.status === 'ok' && d.job_id) {
        setIsMultiLipSyncOpen(false);
        
        // Poll for completion
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`http://127.0.0.1:8000/jobs/${d.job_id}`);
            const statusData = await statusRes.json();
            
            if (statusData.status === 'completed') {
              clearInterval(pollInterval);
              await refreshMedia();
              finishJob(jobId, 'done', 'Multi-character lip-sync complete!');
            } else if (statusData.status === 'failed') {
              clearInterval(pollInterval);
              finishJob(jobId, 'error', statusData.error || 'Failed');
            } else if (statusData.message) {
              setJobs(prev => prev.map(j => j.id === jobId ? { ...j, label: statusData.message } : j));
            }
          } catch (e) {
            console.error('Error polling job status:', e);
          }
        }, 5000);
        
        setTimeout(() => {
          clearInterval(pollInterval);
          finishJob(jobId, 'error', 'Job timed out after 45 minutes');
        }, 2700000); // 45 minutes
      } else {
        throw new Error(d.detail || 'Failed to start multi-character lip-sync');
      }
    } catch (err: any) {
      console.error('[Multi-Character Lip-Sync] Error:', err);
      finishJob(jobId, 'error', err.message);
      alert(`❌ Multi-character lip-sync failed: ${err.message}`);
    }
  }
  
  async function generateVoiceForSlot(slotId: string) {
    const slot = voiceSceneSlots.find(s => s.id === slotId);
    if (!slot) return;
    
    const char = slot.characterId ? characters.find(c => c.character_id === slot.characterId) : null;
    const resolvedVoiceId = slot.voiceId || char?.voice_id || undefined;
    
    const voiceSettings = {
      stability: voiceStability,
      similarity_boost: voiceSimilarity,
      style: voiceStyle,
      use_speaker_boost: voiceSpeakerBoost
    };
    
    const jobId = startJob(`Generating voice for slot #${voiceSceneSlots.indexOf(slot) + 1}`);
    console.log('[Voice Scene] Generating voice for slot:', slotId);
    
    try {
      if (slot.dialogueText.trim()) {
        // TTS mode
        const payload = {
          project_id: projectId,
          text: slot.dialogueText,
          voice_id: resolvedVoiceId,
          filename: `${voiceSceneName}_slot${voiceSceneSlots.indexOf(slot) + 1}`,
          voice_settings: voiceSettings
        };
        console.log('[Voice Scene TTS] Payload:', payload);
        const r = await fetch('http://127.0.0.1:8000/ai/voice/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await r.json();
        console.log('[Voice Scene TTS] Response:', d);
        if (d.status !== 'ok') throw new Error(d.detail || 'TTS failed');
        
        await refreshMedia();
        const newMedia = media.find(m => m.id === d.item.id);
        if (newMedia) {
          updateVoiceSceneSlot(slotId, { generatedVoiceId: newMedia.id });
        }
        finishJob(jobId, 'done');
        alert(`✅ Voice generated: ${d.item.id}`);
      } else if (slot.recordedAudioPath || slot.selectedAudioId) {
        // V2V mode
        const audioPath = slot.recordedAudioPath || (slot.selectedAudioId ? media.find(m => m.id === slot.selectedAudioId)?.path : undefined);
        if (!audioPath) throw new Error('No audio source');
        
        const payload = {
          project_id: projectId,
          source_wav: audioPath,
          voice_id: resolvedVoiceId,
          filename: `${voiceSceneName}_slot${voiceSceneSlots.indexOf(slot) + 1}`,
          voice_settings: voiceSettings,
          remove_background_noise: voiceRemoveNoise
        };
        console.log('[Voice Scene V2V] Payload:', payload);
        const r = await fetch('http://127.0.0.1:8000/ai/voice/v2v', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await r.json();
        console.log('[Voice Scene V2V] Response:', d);
        if (d.status !== 'ok') throw new Error(d.detail || 'V2V failed');
        
        await refreshMedia();
        const newMedia = media.find(m => m.id === d.item.id);
        if (newMedia) {
          updateVoiceSceneSlot(slotId, { generatedVoiceId: newMedia.id });
        }
        finishJob(jobId, 'done');
        alert(`✅ Voice converted: ${d.item.id}`);
      } else {
        throw new Error('No dialogue text or audio source');
      }
    } catch (err: any) {
      console.error('[Voice Scene] Voice generation error:', err);
      finishJob(jobId, 'error', err.message);
      alert(`❌ Voice generation failed: ${err.message}`);
    }
  }
  
  async function generateLipSyncForSlot(slotId: string) {
    const slot = voiceSceneSlots.find(s => s.id === slotId);
    if (!slot) return;
    
    if (!slot.visualId) {
      alert('Select an image or video first');
      return;
    }
    
    // Check for ANY audio source (generated, selected, or recorded)
    const audioId = slot.generatedVoiceId || slot.selectedAudioId;
    if (!audioId) {
      alert('Generate voice or select audio first');
      return;
    }
    
    const visual = media.find(m => m.id === slot.visualId);
    const audio = media.find(m => m.id === audioId);
    if (!visual || !audio) {
      alert('Visual or audio not found in media library');
      return;
    }
    
    const slotIndex = voiceSceneSlots.indexOf(slot) + 1;
    const jobId = startJob(`Lip-sync slot #${slotIndex} (may take 5-30 min)`);
    console.log('[Voice Scene Lip-Sync] Starting for slot:', slotId, 'Visual:', visual.id, 'Audio:', audio.id);
    
    try {
      const endpoint = slot.visualType === 'video' ? '/ai/lipsync/video' : '/ai/lipsync/image';
      const payload = slot.visualType === 'video'
        ? {
            project_id: projectId,
            video_path: visual.path,
            audio_wav_path: audio.path,
            prompt: slot.lipSyncPrompt || undefined,
            filename: `${voiceSceneName}_slot${slotIndex}_lipsync`
          }
        : {
            project_id: projectId,
            image_path: visual.path,
            audio_wav_path: audio.path,
            prompt: slot.lipSyncPrompt || undefined,
            filename: `${voiceSceneName}_slot${slotIndex}_lipsync`
          };
      
      console.log('[Voice Scene Lip-Sync] Payload:', payload);
      const r = await fetch(`http://127.0.0.1:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      console.log('[Voice Scene Lip-Sync] Response:', d);
      
      if (d.status === 'ok' && d.job_id) {
        // Poll for job completion
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`http://127.0.0.1:8000/jobs/${d.job_id}`);
            const statusData = await statusRes.json();
            
            if (statusData.status === 'completed') {
              clearInterval(pollInterval);
              await refreshMedia();
              if (statusData.result?.item?.id) {
                updateVoiceSceneSlot(slotId, { generatedLipSyncId: statusData.result.item.id });
              }
              finishJob(jobId, 'done', 'Lip-sync complete!');
            } else if (statusData.status === 'failed') {
              clearInterval(pollInterval);
              finishJob(jobId, 'error', statusData.error || 'Lip-sync failed');
            } else if (statusData.message) {
              setJobs(prev => prev.map(j => j.id === jobId ? { ...j, label: statusData.message } : j));
            }
          } catch (e) {
            console.error('Error polling job status:', e);
          }
        }, 5000);
        
        setTimeout(() => {
          clearInterval(pollInterval);
          finishJob(jobId, 'error', 'Job timed out after 30 minutes');
        }, 1800000);
      } else {
        throw new Error(d.detail || 'Failed to start lip-sync job');
      }
    } catch (err: any) {
      console.error('[Voice Scene Lip-Sync] Error:', err);
      finishJob(jobId, 'error', err.message);
      alert(`❌ Lip-sync failed: ${err.message}`);
    }
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
    // Auto-dismiss after 3 seconds for success, 8 seconds for errors
    const dismissDelay = status === 'done' ? 3000 : 8000;
    setTimeout(() => {
      setJobs((jobs) => jobs.filter((job) => job.id !== id));
    }, dismissDelay);
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

  const MediaPreviewCard = React.memo(({
    item,
    selected,
    onSelect,
  }: {
    item: any;
    selected: boolean;
    onSelect: () => void;
  }) => {
    const url = `http://127.0.0.1:8000${item.url}`;
    return (
      <button
        className={`rounded-lg border p-1 w-24 h-28 flex flex-col items-center justify-center text-[10px] ${
          selected ? 'border-violet-500 bg-violet-500/10 text-violet-200' : 'border-neutral-700 text-neutral-300 hover:border-violet-500/50'
        }`}
        onClick={onSelect}
        title={item.id}
      >
        {item.type === 'image' ? (
          <img src={url} className="w-full h-16 object-cover rounded" alt={item.id} />
        ) : item.type === 'video' ? (
          <video src={url} className="w-full h-16 object-cover rounded" muted playsInline />
        ) : (
          <div className="w-full h-16 bg-neutral-900/60 rounded flex items-center justify-center text-[12px]">
            🎵
          </div>
        )}
        <span className="mt-1 truncate w-full text-[9px]">{item.id}</span>
        {selected ? <span className="text-violet-300 font-bold">✓</span> : null}
      </button>
    );
  });

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
    console.log('[Voice Generate] Mode:', voiceMode, 'Character:', char?.name, 'Voice ID:', resolvedVoiceId);
    
    const voiceSettings = {
      stability: voiceStability,
      similarity_boost: voiceSimilarity,
      style: voiceStyle,
      use_speaker_boost: voiceSpeakerBoost
    };
    
    try {
      if (voiceMode === 'tts') {
        if (!voiceText.trim()) {
          finishJob(jobId, 'error', 'No text provided');
          alert('Enter text for TTS.');
          return;
        }
        const payload = { 
          project_id: projectId, 
          text: voiceText, 
          voice_id: resolvedVoiceId, 
          filename: voiceOutputName || undefined,
          voice_settings: voiceSettings
        };
        console.log('[Voice TTS] Payload:', payload);
        const r = await fetch('http://127.0.0.1:8000/ai/voice/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await r.json();
        console.log('[Voice TTS] Response:', d);
        if (d.status !== 'ok') {
          throw new Error(d.detail || 'Voice generation failed');
        }
        alert(`✅ Voice generated: ${d.filename || 'voice.mp3'}`);
      } else {
        const audioPath =
          recordedMediaPath ||
          (selectedAudioId ? media.find((m) => m.id === selectedAudioId)?.path : undefined);
        if (!audioPath) {
          finishJob(jobId, 'error', 'Select or record audio');
          alert('Select or record audio for voice-to-voice.');
          return;
        }
        const payload = {
          project_id: projectId,
          source_wav: audioPath,
          voice_id: resolvedVoiceId,
          filename: voiceOutputName || undefined,
          voice_settings: voiceSettings,
          remove_background_noise: voiceRemoveNoise
        };
        console.log('[Voice V2V] Payload:', payload);
        const r = await fetch('http://127.0.0.1:8000/ai/voice/v2v', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const d = await r.json();
        console.log('[Voice V2V] Response:', d);
        if (d.status !== 'ok') {
          throw new Error(d.detail || 'Voice conversion failed');
        }
        alert(`✅ Voice converted: ${d.filename || 'voice.mp3'}`);
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
      console.error('[Voice Generate] Error:', err);
      alert(`❌ Voice generation failed: ${err?.message || 'Unknown error'}`);
      finishJob(jobId, 'error', err?.message || 'Voice generation error');
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
    if (showArchived && projectId) {
      fetch(`http://127.0.0.1:8000/storage/${projectId}/media/archived`)
        .then((r) => r.json())
        .then((d) => {
          const sorted = (d.media ?? []).sort((a: any, b: any) => {
            const getTimestamp = (item: any) => {
              const match1 = item.id?.match(/^(\d{10,13})[_\.]/);
              if (match1) return parseInt(match1[1]);
              const match2 = item.id?.match(/_(\d{10,13})[_\.]/);
              if (match2) return parseInt(match2[1]);
              const match3 = item.id?.match(/(\d{10,13})/);
              if (match3) return parseInt(match3[1]);
              return 0;
            };
            return getTimestamp(b) - getTimestamp(a);
          });
          setArchivedMedia(sorted);
        })
        .catch(() => setArchivedMedia([]));
    } else {
      setArchivedMedia([]);
    }
  }, [showArchived, projectId]);

  useEffect(() => {
    const char = selectedCharacterId ? characters.find((c) => c.character_id === selectedCharacterId) : null;
    
    // Prefill reference images when a character with references is active
    if (provider === 'vertex' || (provider === 'replicate' && genMediaType === 'image')) {
      // Auto-populate reference images for both Vertex and Replicate image generation
      if (selectedCharacterId && char?.reference_image_ids?.length) {
        if (provider === 'vertex') {
          setVxRefImageIds(char.reference_image_ids);
        } else if (provider === 'replicate' && genMediaType === 'image') {
          setReplicateRefImages(char.reference_image_ids);
        }
      } else {
        if (provider === 'vertex') {
          setVxRefImageIds([]);
        } else if (provider === 'replicate' && genMediaType === 'image') {
          setReplicateRefImages([]);
        }
      }
    }
    
    // Only continue with Vertex-specific logic
    if (provider !== 'vertex') return;
    if (char?.reference_image_ids?.length) {
      setVxImageMode('reference');
      setVxRefImageIds(char.reference_image_ids);
    }
  }, [selectedCharacterId, provider, genMediaType, characters]);

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
                
                {/* Custom Replicate Models Section */}
                <div className="mt-6 pt-4 border-t border-neutral-700">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="text-sm font-semibold">Custom Replicate Models</h3>
                      <p className="text-xs text-neutral-400 mt-1">Add your own Replicate models</p>
                    </div>
                    <button
                      className="button-primary text-xs px-2 py-1"
                      onClick={() => setIsAddCustomModelOpen(true)}
                    >
                      + Add Model
                    </button>
                  </div>
                  
                  {customModels.length === 0 ? (
                    <div className="text-xs text-neutral-500 italic">No custom models added yet.</div>
                  ) : (
                    <div className="space-y-2">
                      {customModels.map((model) => (
                        <div key={model.model_id} className="flex items-center justify-between p-2 bg-neutral-900/50 rounded border border-neutral-800">
                          <div className="flex-1">
                            <div className="text-xs font-medium">{model.friendly_name}</div>
                            <div className="text-[10px] text-neutral-500">{model.model_id}</div>
                            <span className="inline-block mt-1 px-2 py-0.5 text-[9px] rounded-full bg-violet-500/20 text-violet-300">
                              {model.model_type}
                            </span>
                          </div>
                          <button
                            className="button text-xs px-2 py-1 text-red-400 hover:text-red-300"
                            onClick={async () => {
                              if (confirm(`Delete custom model "${model.friendly_name}"?`)) {
                                await fetch(`http://127.0.0.1:8000/settings/custom-models/${encodeURIComponent(model.model_id)}`, {
                                  method: 'DELETE'
                                });
                                const cm = await fetch('http://127.0.0.1:8000/settings/custom-models').then((r) => r.json());
                                setCustomModels(cm.models ?? []);
                              }
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
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
          
          {/* Add Custom Model Dialog */}
          <Dialog.Root open={isAddCustomModelOpen} onOpenChange={(open) => {
            setIsAddCustomModelOpen(open);
            if (!open) {
              // Reset state when closing
              setCustomModelInput('');
              setCustomModelPreview(null);
              setCustomModelFetching(false);
            }
          }}>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 bg-black/60" />
              <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] max-h-[80vh] overflow-y-auto card p-5">
                <Dialog.Title className="text-sm font-semibold mb-2">Add Custom Replicate Model</Dialog.Title>
                <Dialog.Description className="text-xs text-neutral-400 mb-4">
                  Paste a Replicate model URL or ID to add it to your library.
                </Dialog.Description>
                
                <div className="space-y-4">
                  {/* Step 1: Input model ID */}
                  <div>
                    <label className="block text-xs text-neutral-400 mb-1">
                      Replicate Model URL or ID
                    </label>
                    <div className="flex gap-2">
                      <input
                        className="field flex-1"
                        placeholder="e.g. owner/model-name or https://replicate.com/owner/model-name"
                        value={customModelInput}
                        onChange={(e) => setCustomModelInput(e.target.value)}
                        disabled={customModelFetching || customModelPreview !== null}
                      />
                      {!customModelPreview && (
                        <button
                          className="button-primary"
                          disabled={!customModelInput.trim() || customModelFetching}
                          onClick={async () => {
                            setCustomModelFetching(true);
                            try {
                              const response = await fetch('http://127.0.0.1:8000/replicate/fetch-schema', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ model_id: customModelInput })
                              });
                              const data = await response.json();
                              
                              if (data.status === 'ok') {
                                setCustomModelPreview({
                                  ...data,
                                  friendly_name: data.model_id.split('/')[1] || data.model_id
                                });
                              } else {
                                alert(`Error: ${data.detail || 'Failed to fetch schema'}`);
                              }
                            } catch (err) {
                              alert(`Error: ${err}`);
                            } finally {
                              setCustomModelFetching(false);
                            }
                          }}
                        >
                          {customModelFetching ? 'Fetching...' : 'Fetch Schema'}
                        </button>
                      )}
                      {customModelPreview && (
                        <button
                          className="button"
                          onClick={() => {
                            setCustomModelPreview(null);
                            setCustomModelInput('');
                          }}
                        >
                          Reset
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* Step 2: Preview and configure */}
                  {customModelPreview && (
                    <div className="space-y-3 p-3 bg-neutral-900/50 rounded border border-neutral-800">
                      <div>
                        <div className="text-xs font-semibold text-green-400 mb-2">✓ Schema Fetched Successfully</div>
                        <div className="text-[10px] text-neutral-400">
                          Model ID: <span className="text-neutral-200">{customModelPreview.model_id}</span>
                        </div>
                        <div className="text-[10px] text-neutral-400 mt-1">
                          Detected Type: <span className="inline-block px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300">
                            {customModelPreview.model_type}
                          </span>
                        </div>
                        {customModelPreview.model_type === 'unknown' && (
                          <div className="text-[10px] text-yellow-400 mt-2">
                            ⚠️ Could not auto-detect model type. Only image and video models are supported.
                          </div>
                        )}
                      </div>
                      
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">Friendly Name</label>
                        <input
                          className="field"
                          value={customModelPreview.friendly_name}
                          onChange={(e) => setCustomModelPreview({ ...customModelPreview, friendly_name: e.target.value })}
                          placeholder="e.g. My Video Model"
                        />
                      </div>
                      
                      <div>
                        <div className="text-xs text-neutral-400 mb-1">Parameters ({customModelPreview.parameters.length})</div>
                        <div className="max-h-40 overflow-y-auto space-y-1">
                          {customModelPreview.parameters.slice(0, 10).map((param: any) => (
                            <div key={param.name} className="text-[10px] flex items-center gap-2 p-1 bg-neutral-900/70 rounded">
                              <span className="font-mono text-violet-300">{param.name}</span>
                              <span className="text-neutral-500">({param.type})</span>
                              {param.required && <span className="text-red-400">*</span>}
                            </div>
                          ))}
                          {customModelPreview.parameters.length > 10 && (
                            <div className="text-[10px] text-neutral-500 italic">
                              ... and {customModelPreview.parameters.length - 10} more
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="mt-4 flex justify-end gap-2">
                  <button
                    className="button"
                    onClick={() => {
                      setIsAddCustomModelOpen(false);
                      setCustomModelInput('');
                      setCustomModelPreview(null);
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    className="button-primary"
                    disabled={!customModelPreview || customModelPreview.model_type === 'unknown'}
                    onClick={async () => {
                      try {
                        const response = await fetch('http://127.0.0.1:8000/settings/custom-models', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            model_id: customModelPreview.model_id,
                            friendly_name: customModelPreview.friendly_name,
                            model_type: customModelPreview.model_type,
                            schema: customModelPreview.schema,
                            parameters: customModelPreview.parameters
                          })
                        });
                        const data = await response.json();
                        
                        if (data.status === 'ok') {
                          // Reload custom models list
                          const cm = await fetch('http://127.0.0.1:8000/settings/custom-models').then((r) => r.json());
                          setCustomModels(cm.models ?? []);
                          
                          // Close dialog and reset
                          setIsAddCustomModelOpen(false);
                          setCustomModelInput('');
                          setCustomModelPreview(null);
                          
                          alert(`✓ Model "${customModelPreview.friendly_name}" added successfully!`);
                        } else {
                          alert(`Error: ${data.detail || 'Failed to save model'}`);
                        }
                      } catch (err) {
                        alert(`Error: ${err}`);
                      }
                    }}
                  >
                    Save Model
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
          {selectedMediaIds.size > 0 && (
            <div className="flex items-center gap-2 mb-2 p-1.5 bg-neutral-800/40 border border-neutral-700 rounded text-xs">
              <span className="text-neutral-400">{selectedMediaIds.size} selected</span>
              <button
                className="text-[10px] px-2 py-0.5 bg-neutral-700 hover:bg-neutral-600 rounded text-neutral-200"
                onClick={() => {
                  // Filter by type
                  let filtered = mediaFilter === 'all' ? media : media.filter(m => m.type === mediaFilter);
                  // Filter by source
                  if (sourceFilter !== 'all') {
                    filtered = filtered.filter(m => m.source === sourceFilter);
                  }
                  const allIds = new Set(filtered.map(m => m.id));
                  setSelectedMediaIds(allIds);
                }}
              >
                Select All
              </button>
              <button
                className="text-[10px] px-2 py-0.5 bg-neutral-700 hover:bg-red-600 rounded text-neutral-200"
                onClick={async () => {
                  const ids = Array.from(selectedMediaIds);
                  const response = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/bulk-archive`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ media_ids: ids, archived: true })
                  });
                  const data = await response.json();
                  
                  // Show message if items were skipped
                  if (data.skipped && data.skipped.length > 0) {
                    const skippedList = data.skipped.map((s: any) => 
                      `• ${s.id} (used by: ${s.characters.join(', ')})`
                    ).join('\n');
                    alert(`${data.message}\n\nSkipped items:\n${skippedList}\n\nRemove these images from their characters first, or unarchive them from the Archive section below.`);
                  }
                  
                  setSelectedMediaIds(new Set());
                  await refreshMedia();
                  // Refresh archived list
                  const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/archived`);
                  const archData = await res.json();
                  const sorted = (archData.media ?? []).sort((a: any, b: any) => {
                    const getTimestamp = (item: any) => {
                      const match1 = item.id?.match(/^(\d{10,13})[_\.]/);
                      if (match1) return parseInt(match1[1]);
                      const match2 = item.id?.match(/_(\d{10,13})[_\.]/);
                      if (match2) return parseInt(match2[1]);
                      const match3 = item.id?.match(/(\d{10,13})/);
                      if (match3) return parseInt(match3[1]);
                      return 0;
                    };
                    return getTimestamp(b) - getTimestamp(a);
                  });
                  setArchivedMedia(sorted);
                }}
              >
                Archive
              </button>
              <button
                className="text-[10px] px-2 py-0.5 bg-neutral-700 hover:bg-neutral-600 rounded text-neutral-200"
                onClick={() => setSelectedMediaIds(new Set())}
              >
                Clear
              </button>
            </div>
          )}
          <div className="space-y-2">
            <div>
              <div className="text-[10px] text-neutral-500 mb-1">Type</div>
              <div className="flex gap-1 flex-wrap">
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'all' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('all')}
                >
                  All
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'image' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('image')}
                >
                  Images
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'video' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('video')}
                >
                  Videos
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'audio' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('audio')}
                >
                  Audio
                </button>
              </div>
            </div>
            <div>
              <div className="text-[10px] text-neutral-500 mb-1">Source</div>
              <div className="flex gap-1 flex-wrap">
                <button
                  className={`text-[9px] px-2 py-1 rounded ${sourceFilter === 'all' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setSourceFilter('all')}
                >
                  All
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${sourceFilter === 'generated' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setSourceFilter('generated')}
                >
                  API Generated
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${sourceFilter === 'uploaded' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setSourceFilter('uploaded')}
                >
                  Uploaded
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${sourceFilter === 'extracted' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setSourceFilter('extracted')}
                >
                  Auto-Extracted Frames
                </button>
              </div>
            </div>
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
            // Filter by type first
            let filtered = mediaFilter === 'all' ? media : media.filter(m => m.type === mediaFilter);
            // Then filter by source
            if (sourceFilter !== 'all') {
              filtered = filtered.filter(m => m.source === sourceFilter);
            }
            // Note: showExtractedFrames toggle is now replaced by source filter
            
            return filtered.length === 0 ? (
              <div className="text-xs text-neutral-500 p-2">No matching files.</div>
            ) : (
              filtered.map((m) => (
                <div
                  key={m.id}
                  className={`w-full text-left text-[11px] text-neutral-300 inline-flex items-center gap-2 p-1 rounded hover:bg-neutral-800/30 ${
                    selectedMediaId === m.id ? 'bg-violet-500/10' : ''
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedMediaIds.has(m.id)}
                    onChange={(e) => {
                      const newSet = new Set(selectedMediaIds);
                      if (e.target.checked) {
                        newSet.add(m.id);
                      } else {
                        newSet.delete(m.id);
                      }
                      setSelectedMediaIds(newSet);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="w-3 h-3"
                  />
                  <button
                    className="text-left inline-flex items-center gap-1 hover:text-violet-400"
                    onClick={(e) => {
                      e.stopPropagation();
                      showInFinder(m);
                    }}
                    title="Show in Finder"
                  >
                    <FolderOpen className="w-3 h-3" />
                  </button>
                  <button
                    className="flex-1 text-left hover:underline"
                    onClick={() => {
                      setSelectedMediaId(m.id);
                      selectMediaForPlayback(m);
                    }}
                  >
                    {m.id}
                  </button>
                </div>
              ))
            );
          })()}
        </div>

        {/* Archive Section - Completely Separate */}
        <div className="mt-6">
          <button
            className="w-full flex items-center justify-between text-xs uppercase tracking-wide text-neutral-400 mb-2 hover:text-neutral-300"
            onClick={() => setShowArchived(!showArchived)}
          >
            <span>Archive ({archivedMedia.length})</span>
            <span className="text-[10px]">{showArchived ? '▼' : '▶'}</span>
          </button>
          {showArchived && (
            <>
              {selectedMediaIds.size > 0 && (
                <div className="flex items-center gap-2 mb-2 p-1.5 bg-neutral-800/40 border border-neutral-700 rounded text-xs">
                  <span className="text-neutral-400">{selectedMediaIds.size} selected</span>
                  <button
                    className="text-[10px] px-2 py-0.5 bg-neutral-700 hover:bg-neutral-600 rounded text-neutral-200"
                    onClick={() => {
                      const filtered = mediaFilter === 'all' ? archivedMedia : archivedMedia.filter(m => m.type === mediaFilter);
                      const allIds = new Set(filtered.map(m => m.id));
                      setSelectedMediaIds(allIds);
                    }}
                  >
                    Select All
                  </button>
                  <button
                    className="text-[10px] px-2 py-0.5 bg-neutral-700 hover:bg-green-600 rounded text-neutral-200"
                    onClick={async () => {
                      const ids = Array.from(selectedMediaIds);
                      await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/bulk-archive`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ media_ids: ids, archived: false })
                      });
                      setSelectedMediaIds(new Set());
                      await refreshMedia();
                      // Refresh archived list
                      const res = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/archived`);
                      const data = await res.json();
                      const sorted = (data.media ?? []).sort((a: any, b: any) => {
                        const getTimestamp = (item: any) => {
                          const match1 = item.id?.match(/^(\d{10,13})[_\.]/);
                          if (match1) return parseInt(match1[1]);
                          const match2 = item.id?.match(/_(\d{10,13})[_\.]/);
                          if (match2) return parseInt(match2[1]);
                          const match3 = item.id?.match(/(\d{10,13})/);
                          if (match3) return parseInt(match3[1]);
                          return 0;
                        };
                        return getTimestamp(b) - getTimestamp(a);
                      });
                      setArchivedMedia(sorted);
                    }}
                  >
                    Unarchive
                  </button>
                  <button
                    className="text-[10px] px-2 py-0.5 bg-neutral-700 hover:bg-neutral-600 rounded text-neutral-200"
                    onClick={() => setSelectedMediaIds(new Set())}
                  >
                    Clear
                  </button>
                </div>
              )}
              <div className="flex gap-1 flex-wrap mb-2">
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'all' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('all')}
                >
                  All ({archivedMedia.length})
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'image' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('image')}
                >
                  Images ({archivedMedia.filter(m => m.type === 'image').length})
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'video' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('video')}
                >
                  Videos ({archivedMedia.filter(m => m.type === 'video').length})
                </button>
                <button
                  className={`text-[9px] px-2 py-1 rounded ${mediaFilter === 'audio' ? 'bg-violet-500/20 text-violet-300' : 'bg-neutral-800/50 text-neutral-500 hover:text-neutral-300'}`}
                  onClick={() => setMediaFilter('audio')}
                >
                  Audio ({archivedMedia.filter(m => m.type === 'audio').length})
                </button>
              </div>
              <div className="space-y-2 max-h-[28vh] overflow-y-auto pr-1 rounded-md border border-neutral-800 bg-neutral-900/20">
                {(() => {
                  const filtered = mediaFilter === 'all' ? archivedMedia : archivedMedia.filter(m => m.type === mediaFilter);
                  
                  return filtered.length === 0 ? (
                    <div className="text-xs text-neutral-500 p-2">No archived {mediaFilter === 'all' ? '' : mediaFilter} files.</div>
                  ) : (
                    filtered.map((m) => (
                      <div
                        key={m.id}
                        className={`w-full text-left text-[11px] text-neutral-400 inline-flex items-center gap-2 p-1 rounded hover:bg-neutral-800/30 ${
                          selectedMediaId === m.id ? 'bg-violet-500/10' : ''
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedMediaIds.has(m.id)}
                          onChange={(e) => {
                            const newSet = new Set(selectedMediaIds);
                            if (e.target.checked) {
                              newSet.add(m.id);
                            } else {
                              newSet.delete(m.id);
                            }
                            setSelectedMediaIds(newSet);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          className="w-3 h-3"
                        />
                        <button
                          className="text-left inline-flex items-center gap-1 hover:text-violet-400"
                          onClick={(e) => {
                            e.stopPropagation();
                            showInFinder(m);
                          }}
                          title="Show in Finder"
                        >
                          <FolderOpen className="w-3 h-3" />
                        </button>
                        <button
                          className="flex-1 text-left hover:underline"
                          onClick={() => {
                            setSelectedMediaId(m.id);
                            selectMediaForPlayback(m);
                          }}
                        >
                          {m.id}
                        </button>
                      </div>
                    ))
                  );
                })()}
              </div>
            </>
          )}
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
                        <label className="block text-xs text-neutral-400 mb-1">Media Type</label>
                        <select className="field" value={genMediaType} onChange={(e) => {
                          setGenMediaType(e.target.value as 'video' | 'image');
                          if (e.target.value === 'image') {
                            setProvider('replicate');
                            setReplicateModel('bytedance/seedream-4');
                          }
                        }}>
                          <option value="video">Video</option>
                          <option value="image">Image</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">Provider</label>
                        <select className="field" value={provider} onChange={(e) => setProvider(e.target.value as any)} disabled={genMediaType === 'image'}>
                          <option value="replicate">Replicate</option>
                          <option value="vertex">Vertex (Veo 3.1)</option>
                        </select>
                      </div>
                    </div>
                    {provider === 'replicate' && (
                      <div className="mb-3">
                        <label className="block text-xs text-neutral-400 mb-1">Model</label>
                        <select className="field" value={replicateModel} onChange={(e) => setReplicateModel(e.target.value)}>
                          {genMediaType === 'video' ? (
                            <>
                              <option value="google/veo-3.1">Google Veo 3.1</option>
                              <option value="kwaivgi/kling-v1.6-pro">Kling v1.6 Pro</option>
                              <option value="bytedance/seedance-1-pro">ByteDance Seedance-1-Pro</option>
                              {customModels.filter(m => m.model_type === 'video').length > 0 && (
                                <optgroup label="Custom Models">
                                  {customModels.filter(m => m.model_type === 'video').map(m => (
                                    <option key={m.model_id} value={m.model_id}>{m.friendly_name}</option>
                                  ))}
                                </optgroup>
                              )}
                            </>
                          ) : (
                            <>
                              <option value="bytedance/seedream-4">ByteDance Seedream-4</option>
                              {customModels.filter(m => m.model_type === 'image').length > 0 && (
                                <optgroup label="Custom Models">
                                  {customModels.filter(m => m.model_type === 'image').map(m => (
                                    <option key={m.model_id} value={m.model_id}>{m.friendly_name}</option>
                                  ))}
                                </optgroup>
                              )}
                            </>
                          )}
                        </select>
                      </div>
                    )}
                    {genMediaType === 'image' && replicateModel === 'bytedance/seedream-4' && (
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        <div>
                          <label className="block text-xs text-neutral-400 mb-1">Aspect Ratio</label>
                          <select className="field" value={seedreamAspectRatio} onChange={(e) => setSeedreamAspectRatio(e.target.value)}>
                            <option value="4:3">4:3</option>
                            <option value="16:9">16:9</option>
                            <option value="21:9">21:9</option>
                            <option value="1:1">1:1</option>
                            <option value="2:3">2:3</option>
                            <option value="3:2">3:2</option>
                            <option value="9:16">9:16</option>
                            <option value="9:21">9:21</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-neutral-400 mb-1">Number of Images</label>
                          <input
                            type="number"
                            className="field"
                            min="1"
                            max="4"
                            value={seedreamNumOutputs}
                            onChange={(e) => setSeedreamNumOutputs(parseInt(e.target.value) || 1)}
                          />
                        </div>
                      </div>
                    )}
                    {genMediaType === 'video' && (
                      <>
                        <div className="grid grid-cols-2 gap-3 mb-3">
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">Aspect Ratio</label>
                            <select className="field" value={videoAspectRatio} onChange={(e) => setVideoAspectRatio(e.target.value)}>
                              <option value="16:9">16:9 (Landscape)</option>
                              <option value="9:16">9:16 (Portrait)</option>
                            </select>
                          </div>
                          <div className="flex items-end">
                            <label className="inline-flex items-center gap-2 text-xs text-neutral-300">
                              <input
                                type="checkbox"
                                checked={genAudio}
                                onChange={(e) => setGenAudio(e.target.checked)}
                              />
                              Generate audio (costs more)
                            </label>
                          </div>
                        </div>
                      </>
                    )}
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
                    {genMediaType === 'video' ? (
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
                            Start/End frames {provider === 'vertex' ? '(Veo 3.1 fast)' : provider === 'replicate' && (replicateModel.includes('kling') || replicateModel.includes('seedance')) ? '(Kling/Seedance)' : ''}
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
                            <label className="block text-xs text-neutral-400 mb-1">Start frame (select image)</label>
                            <div className="grid grid-cols-3 gap-2 max-h-[120px] overflow-y-auto p-2 bg-neutral-900/30 rounded border border-neutral-800">
                              {media.filter((m) => m.type === 'image').length === 0 ? (
                                <div className="col-span-3 text-xs text-neutral-500 text-center py-2">No images</div>
                              ) : (
                                media.filter((m) => m.type === 'image').map((m) => {
                                  const selected = vxStartImageId === m.id;
                                  return (
                                    <button
                                      key={m.id}
                                      disabled={vxUsePrevLast}
                                      className={`relative aspect-video rounded overflow-hidden border-2 transition-all ${
                                        selected ? 'border-violet-500 ring-2 ring-violet-500/50' : 'border-neutral-700 hover:border-violet-400'
                                      } ${vxUsePrevLast ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
                                      onClick={() => {
                                        if (!vxUsePrevLast) {
                                          setVxStartImageId(m.id);
                                          setVxStartFromVideoId(null);
                                          setVxStartFramePath(null);
                                        }
                                      }}
                                    >
                                      <img
                                        src={`http://127.0.0.1:8000${m.url}`}
                                        className="w-full h-full object-cover"
                                        alt={m.id}
                                      />
                                      {selected ? (
                                        <div className="absolute inset-0 bg-violet-500/20 flex items-center justify-center">
                                          <div className="bg-violet-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                                            ✓
                                          </div>
                                        </div>
                                      ) : null}
                                      <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-white text-[8px] px-1 py-0.5 truncate">
                                        {m.id}
                                      </div>
                                    </button>
                                  );
                                })
                              )}
                            </div>
                            <label className="block text-xs text-neutral-400 mb-1 mt-3">OR extract from video's last frame</label>
                            <div className="grid grid-cols-3 gap-2 max-h-[120px] overflow-y-auto p-2 bg-neutral-900/30 rounded border border-neutral-800">
                              {media.filter((m) => m.type === 'video').length === 0 ? (
                                <div className="col-span-3 text-xs text-neutral-500 text-center py-2">No videos</div>
                              ) : (
                                media.filter((m) => m.type === 'video').map((m) => {
                                  const selected = vxStartFromVideoId === m.id;
                                  return (
                                    <button
                                      key={m.id}
                                      disabled={vxUsePrevLast}
                                      className={`relative aspect-video rounded overflow-hidden border-2 transition-all ${
                                        selected ? 'border-violet-500 ring-2 ring-violet-500/50' : 'border-neutral-700 hover:border-violet-400'
                                      } ${vxUsePrevLast ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
                                      onClick={() => {
                                        if (!vxUsePrevLast) {
                                          setVxStartFromVideoId(m.id);
                                          setVxStartImageId(null);
                                        }
                                      }}
                                    >
                                      <img
                                        src={`http://127.0.0.1:8000${m.url}`}
                                        className="w-full h-full object-cover"
                                        alt={m.id}
                                      />
                                      {selected ? (
                                        <div className="absolute inset-0 bg-violet-500/20 flex items-center justify-center">
                                          <div className="bg-violet-500 text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                                            ✓
                                          </div>
                                        </div>
                                      ) : null}
                                    </button>
                                  );
                                })
                              )}
                            </div>
                            {vxStartFromVideoId ? (
                              <button
                                className="button text-[11px] px-2 py-1 mt-2 w-full"
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
                                Extract as start frame
                              </button>
                            ) : null}
                            {vxStartFramePath ? (
                              <div className="mt-2">
                                <div className="text-[11px] text-neutral-400 mb-1">✓ Extracted start frame</div>
                                <img
                                  src={`http://127.0.0.1:8000/files/${vxStartFramePath.replace('project_data/', '')}`}
                                  className="w-full h-24 object-cover rounded border border-violet-500"
                                />
                              </div>
                            ) : null}
                          </div>
                          <div>
                            <label className="block text-xs text-neutral-400 mb-1">End frame (optional)</label>
                            <div className="text-[10px] text-neutral-500 mb-2">
                              Note: End frame requires a start frame (for interpolation)
                            </div>
                            <div className="grid grid-cols-3 gap-2 max-h-[120px] overflow-y-auto p-2 bg-neutral-900/30 rounded border border-neutral-800">
                              {media.filter((m) => m.type === 'image').length === 0 ? (
                                <div className="col-span-3 text-xs text-neutral-500 text-center py-2">No images</div>
                              ) : (
                                media.filter((m) => m.type === 'image').map((m) => {
                                  const selected = vxEndImageId === m.id;
                                  return (
                                    <button
                                      key={m.id}
                                      className={`relative aspect-video rounded overflow-hidden border-2 transition-all ${
                                        selected ? 'border-violet-500 ring-2 ring-violet-500/50' : 'border-neutral-700 hover:border-violet-400'
                                      } cursor-pointer`}
                                      onClick={() => setVxEndImageId(selected ? null : m.id)}
                                    >
                                      <img
                                        src={`http://127.0.0.1:8000${m.url}`}
                                        className="w-full h-full object-cover"
                                        alt={m.id}
                                      />
                                      {selected ? (
                                        <div className="absolute inset-0 bg-violet-500/20 flex items-center justify-center">
                                          <div className="bg-violet-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                                            ✓
                                          </div>
                                        </div>
                                      ) : null}
                                      <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-white text-[8px] px-1 py-0.5 truncate">
                                        {m.id}
                                      </div>
                                    </button>
                                  );
                                })
                              )}
                            </div>
                          </div>
                        </div>
                        </>
                        ) : null}
                      </div>
                    ) : null}
                    {provider === 'replicate' && genMediaType === 'image' && (
                      <div className="mb-3">
                        <label className="block text-xs text-neutral-400 mb-1">Reference Images (optional - for character consistency)</label>
                        <div className="text-[10px] text-neutral-500 mb-2">
                          {selectedCharacter && selectedCharacter.reference_image_ids?.length ? (
                            <span className="text-violet-400">Character "{selectedCharacter.name}" has {selectedCharacter.reference_image_ids.length} reference image(s) - will be used automatically</span>
                          ) : (
                            'Select images manually or choose a character with reference images'
                          )}
                        </div>
                        <div className="grid grid-cols-4 gap-2 max-h-[200px] overflow-y-auto p-2 bg-neutral-900/30 rounded border border-neutral-800">
                          {media.filter((m) => m.type === 'image').length === 0 ? (
                            <div className="col-span-4 text-xs text-neutral-500 text-center py-4">No images yet</div>
                          ) : (
                            media.filter((m) => m.type === 'image').map((m) => {
                              const selected = replicateRefImages.includes(m.id);
                              return (
                                <button
                                  key={m.id}
                                  className={`relative aspect-video rounded overflow-hidden border-2 transition-all ${
                                    selected ? 'border-violet-500 ring-2 ring-violet-500/50' : 'border-neutral-700 hover:border-violet-400'
                                  } cursor-pointer`}
                                  onClick={() => {
                                    setReplicateRefImages((prev) =>
                                      selected ? prev.filter((id) => id !== m.id) : [...prev, m.id]
                                    );
                                  }}
                                >
                                  <img
                                    src={`http://127.0.0.1:8000${m.url}`}
                                    className="w-full h-full object-cover"
                                    alt={m.id}
                                  />
                                  {selected ? (
                                    <div className="absolute inset-0 bg-violet-500/20 flex items-center justify-center">
                                      <div className="bg-violet-500 text-white text-xs font-bold rounded-full w-6 h-6 flex items-center justify-center">
                                        ✓
                                      </div>
                                    </div>
                                  ) : null}
                                  <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-white text-[8px] px-1 py-0.5 truncate">
                                    {m.id}
                                  </div>
                                </button>
                              );
                            })
                          )}
                        </div>
                      </div>
                    )}
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-xs text-neutral-400">
                        Prompt {shotPromptHistory.length > 0 ? <span className="text-neutral-600">(↑↓ for history)</span> : null}
                      </label>
                      <button
                        className="text-[10px] text-violet-400 hover:text-violet-300"
                        onClick={() => setIsTemplatesOpen(true)}
                      >
                        📝 Templates
                      </button>
                    </div>
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
                    <label className="mt-3 inline-flex items-center gap-2 text-sm text-neutral-300 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={vxUsePrevLast} 
                        onChange={async (e) => {
                          const checked = e.target.checked;
                          setVxUsePrevLast(checked);
                          
                          if (checked && vxImageMode === 'start_end') {
                            // Auto-extract last frame from previous shot
                            const shots = sceneDetail?.shots || [];
                            if (shots.length > 0) {
                              const lastShot = shots[shots.length - 1];
                              if (lastShot.file_path) {
                                try {
                                  const r = await fetch('http://127.0.0.1:8000/frames/last', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ 
                                      project_id: projectId, 
                                      video_path: lastShot.file_path 
                                    })
                                  });
                                  const d = await r.json();
                                  if (d.status === 'ok') {
                                    setVxStartFramePath(d.image_path);
                                    // Clear conflicting selections
                                    setVxStartImageId(null);
                                    setVxStartFromVideoId(null);
                                  } else {
                                    alert(d.detail || 'Failed to extract last frame');
                                  }
                                } catch (e) {
                                  console.error('Failed to extract frame:', e);
                                }
                              } else {
                                alert('Previous shot has no video file');
                              }
                            } else {
                              alert('No previous shot exists');
                            }
                          }
                        }} 
                      />
                      Use previous shot's last frame as start
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
                              // Vertex Veo 3.1 fast only supports start and/or end frames (no reference images)
                              if (vxImageMode === 'start_end') {
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
                                // none - no frames provided
                                startFramePath = undefined;
                                endFramePath = undefined;
                              }
                            } else {
                              // Replicate
                              if (genMediaType === 'image') {
                                // For image generation, use reference images (from character or manual selection)
                                refImages = charRefPaths || replicateRefImages.map(id => media.find(m => m.id === id)?.path).filter(Boolean) as string[];
                                startFramePath = undefined;
                              } else {
                                // For video generation, use start/end frames (same logic as Vertex)
                                if (vxImageMode === 'start_end') {
                                  // Priority: vxUsePrevLast > vxStartFramePath (extracted from video) > vxStartImageId
                                  if (vxUsePrevLast) {
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
                                  // Legacy reference_frame fallback
                                  startFramePath = reference_frame;
                                }
                              }
                            }
                            jobId = startJob(`Generating ${genMediaType} ${selectedSceneId}`);
                            const payload = {
                              project_id: projectId,
                              scene_id: selectedSceneId,
                              prompt: promptWithStyle,
                              provider,
                              media_type: genMediaType,
                              model: provider === 'replicate' ? replicateModel : 'veo-3.1-fast-generate-preview',
                              duration: genMediaType === 'video' ? 8 : undefined,
                              resolution: genMediaType === 'video' ? '1080p' : undefined,
                              aspect_ratio: genMediaType === 'image' ? seedreamAspectRatio : videoAspectRatio,
                              // For video generation, send start_frame_path and end_frame_path for all providers
                              start_frame_path: genMediaType === 'video' ? startFramePath : undefined,
                              end_frame_path: genMediaType === 'video' ? endFramePath : undefined,
                              reference_images: (provider === 'replicate' && genMediaType === 'image') ? refImages : undefined,
                              generate_audio: provider === 'replicate' && genMediaType === 'video' ? genAudio : false,
                              num_outputs: genMediaType === 'image' && replicateModel === 'bytedance/seedream-4' ? seedreamNumOutputs : undefined,
                              character_id: selectedCharacterId || undefined
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
                              
                              if (genMediaType === 'image') {
                                // For image generation, refresh media to show new images
                                await refreshMedia();
                                
                                // Auto-select the first generated image
                                if (data.images && data.images.length > 0) {
                                  const firstImageUrl = `http://127.0.0.1:8000${data.images[0].replace('project_data/', '/files/')}`;
                                  setCurrentImageUrl(firstImageUrl);
                                  setNowPlaying('');
                                  setPlayError('');
                                }
                                
                                setIsGenOpen(false);
                                if (jobId) finishJob(jobId, 'done');
                                const imageList = data.images?.map((img: string) => {
                                  const filename = img.split('/').pop();
                                  return `• ${filename}`;
                                }).join('\n') || '';
                                alert(`Generated ${data.images?.length || 1} image(s)!\n\n${imageList}\n\nImages are now visible and the first one is selected in the preview.`);
                              } else {
                                // For video generation, show the video
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
                              }
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
                  <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] max-h-[90vh] overflow-y-auto card p-5">
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
                  
                  <div className="mt-4 border-t border-neutral-700 pt-3">
                    <div className="text-xs font-semibold text-neutral-300 mb-2">Voice Settings</div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">
                          Stability: {voiceStability.toFixed(2)}
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.01"
                          value={voiceStability}
                          onChange={(e) => setVoiceStability(parseFloat(e.target.value))}
                          className="w-full"
                        />
                        <div className="text-[10px] text-neutral-500">Higher = more consistent</div>
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">
                          Similarity: {voiceSimilarity.toFixed(2)}
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.01"
                          value={voiceSimilarity}
                          onChange={(e) => setVoiceSimilarity(parseFloat(e.target.value))}
                          className="w-full"
                        />
                        <div className="text-[10px] text-neutral-500">Higher = closer to original</div>
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-400 mb-1">
                          Style: {voiceStyle.toFixed(2)}
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.01"
                          value={voiceStyle}
                          onChange={(e) => setVoiceStyle(parseFloat(e.target.value))}
                          className="w-full"
                        />
                        <div className="text-[10px] text-neutral-500">Higher = more expressive</div>
                      </div>
                      <div>
                        <label className="inline-flex items-center gap-2 text-xs text-neutral-400 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={voiceSpeakerBoost}
                            onChange={(e) => setVoiceSpeakerBoost(e.target.checked)}
                          />
                          Speaker Boost
                        </label>
                        <div className="text-[10px] text-neutral-500 mt-1">Enhance similarity (slower)</div>
                      </div>
                    </div>
                    {voiceMode === 'v2v' && (
                      <div className="mt-2">
                        <label className="inline-flex items-center gap-2 text-xs text-neutral-400 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={voiceRemoveNoise}
                            onChange={(e) => setVoiceRemoveNoise(e.target.checked)}
                          />
                          Remove Background Noise
                        </label>
                      </div>
                    )}
                  </div>
                  
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
                  if (!o) {
                    // Only clear if not pre-selected by clicking "Lip" button
                    // The button handlers will set these before opening
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
                      <div className="text-xs text-neutral-400 mb-1 flex items-center justify-between">
                        <span>Audio</span>
                        {lipAudioId && (() => {
                          const selectedAudio = media.find(m => m.id === lipAudioId);
                          return selectedAudio ? (
                            <audio controls className="h-6 max-w-[200px]">
                              <source src={`http://127.0.0.1:8000${selectedAudio.url}`} />
                            </audio>
                          ) : null;
                        })()}
                      </div>
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
                          const jobId = startJob(lipMode === 'video' ? 'Lip-sync video (may take 5-30 min)' : 'Lip-sync image (may take 5-30 min)');
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
                            console.log('Starting lip-sync request:', endpoint, body);
                            
                            // Start the background job
                            const r = await fetch(endpoint, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify(body)
                            });
                            
                            const d = await r.json();
                            console.log('Lip-sync job started:', d);
                            
                            if (d.status === 'ok' && d.job_id) {
                              // Save lip-sync prompt to history
                              if (lipPrompt.trim()) {
                                setLipSyncPromptHistory(prev => {
                                  const filtered = prev.filter(p => p !== lipPrompt.trim());
                                  return [...filtered, lipPrompt.trim()].slice(-20);
                                });
                                setLipSyncPromptHistoryIndex(-1);
                              }
                              setIsLipOpen(false);
                              
                              // Poll for job completion in background
                              const pollInterval = setInterval(async () => {
                                try {
                                  const statusRes = await fetch(`http://127.0.0.1:8000/jobs/${d.job_id}`);
                                  const statusData = await statusRes.json();
                                  
                                  if (statusData.status === 'completed') {
                                    clearInterval(pollInterval);
                                    await refreshMedia();
                                    if (statusData.result?.url) {
                                      setCurrentVideoUrl(`http://127.0.0.1:8000${statusData.result.url}`);
                                    }
                                    finishJob(jobId, 'done', statusData.message || 'Lip-sync complete!');
                                  } else if (statusData.status === 'failed') {
                                    clearInterval(pollInterval);
                                    finishJob(jobId, 'error', statusData.error || 'Lip-sync failed');
                                  } else if (statusData.message) {
                                    // Update job message with progress
                                    setJobs(prev => prev.map(j => 
                                      j.id === jobId ? { ...j, label: statusData.message } : j
                                    ));
                                  }
                                } catch (e) {
                                  console.error('Error polling job status:', e);
                                }
                              }, 5000); // Poll every 5 seconds
                              
                              // Timeout after 30 minutes
                              setTimeout(() => {
                                clearInterval(pollInterval);
                                finishJob(jobId, 'error', 'Job timed out after 30 minutes');
                              }, 1800000); // 30 minutes
                            } else {
                              alert(d.detail || 'Failed to start lip-sync job');
                              finishJob(jobId, 'error', d.detail || 'Failed to start job');
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
              
              {/* Voice Scene Builder */}
              <Dialog.Root open={isVoiceSceneOpen} onOpenChange={(open) => {
                setIsVoiceSceneOpen(open);
                if (!open && voiceSceneRecorderRef.current) {
                  stopVoiceSceneRecording();
                }
              }}>
                <Dialog.Trigger asChild>
                  <button className="button">Voice Scene Builder</button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/60" />
                  <Dialog.Content className="fixed inset-4 overflow-y-auto card p-5">
                    <Dialog.Title className="text-sm font-semibold mb-2">Voice Scene Builder</Dialog.Title>
                    <Dialog.Description className="text-xs text-neutral-400 mb-3">
                      Build a dialogue scene: visual + voice + lip-sync for each line
                    </Dialog.Description>
                    
                    <div className="flex items-center gap-3 mb-4">
                      <input
                        className="field flex-1 text-sm"
                        placeholder="Scene name"
                        value={voiceSceneName}
                        onChange={(e) => setVoiceSceneName(e.target.value)}
                      />
                      <button className="button-primary text-sm" onClick={addVoiceSceneSlot}>
                        + Add Slot
                      </button>
                    </div>
                    
                    {voiceSceneSlots.length === 0 ? (
                      <div className="text-xs text-neutral-500 text-center py-8">
                        No slots yet. Click "+ Add Slot" to start.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {voiceSceneSlots.map((slot, idx) => {
                          const visual = slot.visualId ? media.find(m => m.id === slot.visualId) : null;
                          const generatedVoice = slot.generatedVoiceId ? media.find(m => m.id === slot.generatedVoiceId) : null;
                          const generatedLipSync = slot.generatedLipSyncId ? media.find(m => m.id === slot.generatedLipSyncId) : null;
                          const selectedAudio = slot.selectedAudioId ? media.find(m => m.id === slot.selectedAudioId) : null;
                          const isRecording = voiceSceneRecordingSlotId === slot.id;
                          
                          return (
                            <div key={slot.id} className="border border-neutral-700 rounded-lg p-3 bg-neutral-900/30">
                              <div className="flex items-center justify-between mb-2">
                                <div className="text-xs font-semibold text-neutral-300">#{idx + 1}</div>
                                <button
                                  className="text-xs text-red-400 hover:text-red-300"
                                  onClick={() => removeVoiceSceneSlot(slot.id)}
                                >
                                  ✕
                                </button>
                              </div>
                              
                              <div className="grid grid-cols-[200px_1fr_200px] gap-3">
                                {/* Visual Column */}
                                <div>
                                  <div className="text-[10px] uppercase text-neutral-500 mb-1">Visual</div>
                                  {visual ? (
                                    <div className="relative group">
                                      {visual.type === 'image' ? (
                                        <img src={`http://127.0.0.1:8000${visual.url}`} className="w-full h-28 object-cover rounded border border-neutral-700" />
                                      ) : (
                                        <video src={`http://127.0.0.1:8000${visual.url}`} className="w-full h-28 object-cover rounded border border-neutral-700" />
                                      )}
                                      <button
                                        className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-xs text-white"
                                        onClick={() => updateVoiceSceneSlot(slot.id, { visualId: null, visualType: null })}
                                      >
                                        Change
                                      </button>
                                    </div>
                                  ) : (
                                    <div
                                      className="border-2 border-dashed border-neutral-700 rounded h-28 flex flex-col items-center justify-center text-[10px] text-neutral-500 hover:border-violet-500/50 cursor-pointer"
                                      onDrop={async (e) => {
                                        e.preventDefault();
                                        const files = Array.from(e.dataTransfer.files);
                                        if (files.length > 0) {
                                          const formData = new FormData();
                                          formData.append('file', files[0]);
                                          formData.append('project_id', projectId);
                                          const r = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`, {
                                            method: 'POST',
                                            body: formData
                                          });
                                          const d = await r.json();
                                          if (d.status === 'ok' && d.item) {
                                            await refreshMedia();
                                            updateVoiceSceneSlot(slot.id, { visualId: d.item.id, visualType: d.item.type });
                                          }
                                        }
                                      }}
                                      onDragOver={(e) => e.preventDefault()}
                                    >
                                      <span>Drop file</span>
                                      <span className="text-[9px] text-neutral-600 mt-1">or select below</span>
                                    </div>
                                  )}
                                  {!visual && (
                                    <div className="mt-1 max-h-32 overflow-y-auto border border-neutral-800 rounded p-1">
                                      <div className="grid grid-cols-2 gap-1">
                                        {[...imageMedia, ...videoMedia].slice(0, 20).map(m => (
                                          <button
                                            key={m.id}
                                            className="relative group"
                                            onClick={() => updateVoiceSceneSlot(slot.id, { visualId: m.id, visualType: m.type as 'image' | 'video' })}
                                          >
                                            {m.type === 'image' ? (
                                              <img src={`http://127.0.0.1:8000${m.url}`} className="w-full h-12 object-cover rounded border border-neutral-700 hover:border-violet-500" />
                                            ) : (
                                              <video src={`http://127.0.0.1:8000${m.url}`} className="w-full h-12 object-cover rounded border border-neutral-700 hover:border-violet-500" />
                                            )}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                
                                {/* Voice Column */}
                                <div className="space-y-2">
                                  <div className="text-[10px] uppercase text-neutral-500">Voice Setup</div>
                                  <div className="grid grid-cols-2 gap-2">
                                    <select
                                      className="field text-xs"
                                      value={slot.characterId || ''}
                                      onChange={(e) => {
                                        const charId = e.target.value || null;
                                        const c = charId ? characters.find(ch => ch.character_id === charId) : null;
                                        updateVoiceSceneSlot(slot.id, { characterId: charId, voiceId: c?.voice_id || '' });
                                      }}
                                    >
                                      <option value="">Character...</option>
                                      {characters.map(c => (
                                        <option key={c.character_id} value={c.character_id}>{c.name}</option>
                                      ))}
                                    </select>
                                    <input
                                      className="field text-xs"
                                      placeholder="Voice ID"
                                      value={slot.voiceId}
                                      onChange={(e) => updateVoiceSceneSlot(slot.id, { voiceId: e.target.value })}
                                    />
                                  </div>
                                  
                                  <textarea
                                    className="field text-xs h-16"
                                    placeholder="Dialogue text (for TTS)..."
                                    value={slot.dialogueText}
                                    onChange={(e) => updateVoiceSceneSlot(slot.id, { dialogueText: e.target.value })}
                                  />
                                  
                                  <div className="flex gap-2">
                                    <button
                                      className={`text-[10px] px-2 py-1 rounded ${isRecording ? 'bg-red-500 text-white' : 'bg-neutral-700 hover:bg-neutral-600 text-neutral-300'}`}
                                      onClick={() => isRecording ? stopVoiceSceneRecording() : startVoiceSceneRecording(slot.id)}
                                    >
                                      {isRecording ? '⏹ Stop' : '🎤 Record'}
                                    </button>
                                    <div
                                      className="flex-1 border border-dashed border-neutral-700 rounded px-2 py-1 text-[10px] text-neutral-500 hover:border-violet-500/50 cursor-pointer flex items-center justify-center"
                                      onDrop={async (e) => {
                                        e.preventDefault();
                                        const files = Array.from(e.dataTransfer.files);
                                        if (files.length > 0) {
                                          const formData = new FormData();
                                          formData.append('file', files[0]);
                                          formData.append('project_id', projectId);
                                          const r = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media`, {
                                            method: 'POST',
                                            body: formData
                                          });
                                          const d = await r.json();
                                          if (d.status === 'ok' && d.item) {
                                            await refreshMedia();
                                            updateVoiceSceneSlot(slot.id, { selectedAudioId: d.item.id });
                                          }
                                        }
                                      }}
                                      onDragOver={(e) => e.preventDefault()}
                                    >
                                      Drop audio
                                    </div>
                                  </div>
                                  
                                  <select
                                    className="field text-[10px]"
                                    value={slot.selectedAudioId || ''}
                                    onChange={(e) => updateVoiceSceneSlot(slot.id, { selectedAudioId: e.target.value || null })}
                                  >
                                    <option value="">Or select existing audio...</option>
                                    {audioMedia.map(a => (
                                      <option key={a.id} value={a.id}>{a.id}</option>
                                    ))}
                                  </select>
                                  
                                  {selectedAudio && (
                                    <div className="bg-neutral-800/50 rounded p-1">
                                      <div className="text-[9px] text-neutral-500 mb-1">Selected: {selectedAudio.id}</div>
                                      <audio key={selectedAudio.id} controls className="w-full h-6">
                                        <source src={`http://127.0.0.1:8000${selectedAudio.url}?t=${Date.now()}`} />
                                      </audio>
                                    </div>
                                  )}
                                  
                                  <button
                                    className="button-primary w-full text-xs py-1"
                                    onClick={() => generateVoiceForSlot(slot.id)}
                                    disabled={!slot.dialogueText.trim() && !slot.recordedAudioPath && !slot.selectedAudioId}
                                  >
                                    Generate Voice
                                  </button>
                                  
                                  {generatedVoice && (
                                    <div className="bg-green-900/20 border border-green-500/30 rounded p-1">
                                      <div className="text-[9px] text-green-400 mb-1">✓ Generated: {generatedVoice.id}</div>
                                      <audio key={generatedVoice.id} controls className="w-full h-6">
                                        <source src={`http://127.0.0.1:8000${generatedVoice.url}?t=${Date.now()}`} />
                                      </audio>
                                    </div>
                                  )}
                                </div>
                                
                                {/* Lip-Sync Column */}
                                <div>
                                  <div className="text-[10px] uppercase text-neutral-500 mb-1">Lip-Sync</div>
                                  {generatedLipSync ? (
                                    <div>
                                      <video
                                        src={`http://127.0.0.1:8000${generatedLipSync.url}`}
                                        controls
                                        className="w-full h-28 rounded border border-green-500/30"
                                      />
                                      <div className="text-[10px] text-green-400 mt-1">✓ Complete</div>
                                    </div>
                                  ) : (
                                    <div className="space-y-2">
                                      <div className="text-[10px] text-neutral-500 bg-neutral-800/50 rounded p-2 h-16 flex flex-col items-center justify-center">
                                        {!slot.visualId ? (
                                          <span>⚠ Need visual</span>
                                        ) : !(slot.generatedVoiceId || slot.selectedAudioId) ? (
                                          <span>⚠ Need audio</span>
                                        ) : (
                                          <span className="text-green-400">✓ Ready</span>
                                        )}
                                      </div>
                                      <input
                                        className="field text-[10px]"
                                        placeholder="Prompt (optional)"
                                        value={slot.lipSyncPrompt}
                                        onChange={(e) => updateVoiceSceneSlot(slot.id, { lipSyncPrompt: e.target.value })}
                                      />
                                      <button
                                        className="button-primary w-full text-xs py-1"
                                        onClick={() => generateLipSyncForSlot(slot.id)}
                                        disabled={!slot.visualId || !(slot.generatedVoiceId || slot.selectedAudioId)}
                                      >
                                        Generate
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    
                    <div className="mt-4 flex justify-end gap-2">
                      <Dialog.Close asChild>
                        <button className="button">Close</button>
                      </Dialog.Close>
                    </div>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              
              {/* Multi-Character Lip-Sync */}
              <Dialog.Root open={isMultiLipSyncOpen} onOpenChange={setIsMultiLipSyncOpen}>
                <Dialog.Trigger asChild>
                  <button className="button" title="UI ready, backend compositing in progress">
                    Multi-Character Lip-Sync (Beta)
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/60" />
                  <Dialog.Content className="fixed inset-4 overflow-y-auto card p-5">
                    <Dialog.Title className="text-sm font-semibold mb-2">Multi-Character Lip-Sync</Dialog.Title>
                    <Dialog.Description className="text-xs text-neutral-400 mb-3">
                      Precisely assign audio tracks to specific characters using bounding boxes
                    </Dialog.Description>
                    
                    <div className="grid grid-cols-2 gap-4">
                      {/* Left: Image + Bounding Boxes */}
                      <div>
                        <div className="text-xs text-neutral-400 mb-2">Reference Image</div>
                        {multiLipSyncImageId ? (
                          <div className="relative">
                            <img 
                              src={`http://127.0.0.1:8000${media.find(m => m.id === multiLipSyncImageId)?.url}`}
                              className="w-full rounded border border-neutral-700"
                            />
                            <button
                              className="absolute top-2 right-2 text-xs px-2 py-1 bg-red-500/80 hover:bg-red-500 rounded text-white"
                              onClick={() => {
                                setMultiLipSyncImageId(null);
                                setMultiLipSyncBoundingBoxes([]);
                              }}
                            >
                              Change Image
                            </button>
                            {/* Draw bounding boxes */}
                            {multiLipSyncBoundingBoxes.map((box, idx) => (
                              <div
                                key={box.box_id}
                                className="absolute border-2 border-violet-500"
                                style={{
                                  left: `${box.x}%`,
                                  top: `${box.y}%`,
                                  width: `${box.width}%`,
                                  height: `${box.height}%`
                                }}
                              >
                                <div className="absolute -top-5 left-0 text-[10px] bg-violet-500 text-white px-1 rounded">
                                  {box.character_name} #{idx + 1}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="border-2 border-dashed border-neutral-700 rounded h-96 flex items-center justify-center">
                            <div className="text-center">
                              <div className="text-xs text-neutral-500 mb-3">Select an image</div>
                              <div className="max-h-64 overflow-y-auto grid grid-cols-3 gap-2 p-2">
                                {imageMedia.slice(0, 30).map(img => (
                                  <button
                                    key={img.id}
                                    onClick={() => setMultiLipSyncImageId(img.id)}
                                    className="relative group"
                                  >
                                    <img 
                                      src={`http://127.0.0.1:8000${img.url}`}
                                      className="w-full h-20 object-cover rounded border border-neutral-700 hover:border-violet-500"
                                    />
                                  </button>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {/* Right: Character Assignments */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-neutral-400">Character Assignments</div>
                          <button
                            className="button-primary text-xs px-2 py-1"
                            onClick={addCharacterBoundingBox}
                            disabled={!selectedCharacterId || !multiLipSyncImageId}
                          >
                            + Add Character
                          </button>
                        </div>
                        
                        {multiLipSyncBoundingBoxes.length === 0 ? (
                          <div className="text-xs text-neutral-500 text-center py-8 border border-dashed border-neutral-700 rounded">
                            Select a character and click "+ Add Character"
                          </div>
                        ) : (
                          <div className="space-y-3 max-h-[500px] overflow-y-auto">
                            {multiLipSyncBoundingBoxes.map((box, idx) => {
                              const assignedAudio = box.audio_track_id ? media.find(m => m.id === box.audio_track_id) : null;
                              return (
                                <div key={box.box_id} className="border border-neutral-700 rounded p-3 bg-neutral-900/30">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="text-xs font-semibold text-violet-400">{box.character_name} #{idx + 1}</div>
                                    <button
                                      className="text-xs text-red-400 hover:text-red-300"
                                      onClick={() => removeCharacterBoundingBox(box.box_id)}
                                    >
                                      ✕
                                    </button>
                                  </div>
                                  
                                  <div className="space-y-2">
                                    <div className="text-[10px] text-neutral-500 mb-1">Bounding Box (% of image)</div>
                                    <div className="grid grid-cols-2 gap-2">
                                      <input
                                        className="field text-[10px]"
                                        type="number"
                                        placeholder="X %"
                                        value={box.x}
                                        onChange={(e) => updateCharacterBoundingBox(box.box_id, { x: parseFloat(e.target.value) || 0 })}
                                      />
                                      <input
                                        className="field text-[10px]"
                                        type="number"
                                        placeholder="Y %"
                                        value={box.y}
                                        onChange={(e) => updateCharacterBoundingBox(box.box_id, { y: parseFloat(e.target.value) || 0 })}
                                      />
                                      <input
                                        className="field text-[10px]"
                                        type="number"
                                        placeholder="Width %"
                                        value={box.width}
                                        onChange={(e) => updateCharacterBoundingBox(box.box_id, { width: parseFloat(e.target.value) || 0 })}
                                      />
                                      <input
                                        className="field text-[10px]"
                                        type="number"
                                        placeholder="Height %"
                                        value={box.height}
                                        onChange={(e) => updateCharacterBoundingBox(box.box_id, { height: parseFloat(e.target.value) || 0 })}
                                      />
                                    </div>
                                    
                                    <div className="text-[10px] text-neutral-500 mb-1">Audio Track</div>
                                    <select
                                      className="field text-xs"
                                      value={box.audio_track_id || ''}
                                      onChange={(e) => updateCharacterBoundingBox(box.box_id, { audio_track_id: e.target.value || null })}
                                    >
                                      <option value="">Select audio...</option>
                                      {audioMedia.map(a => (
                                        <option key={a.id} value={a.id}>{a.id}</option>
                                      ))}
                                    </select>
                                    
                                    {assignedAudio && (
                                      <div className="bg-neutral-800/50 rounded p-1">
                                        <audio controls className="w-full h-6">
                                          <source src={`http://127.0.0.1:8000${assignedAudio.url}`} />
                                        </audio>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                        
                        <div className="space-y-2 pt-3 border-t border-neutral-700">
                          <input
                            className="field text-xs"
                            placeholder="Prompt (optional)"
                            value={multiLipSyncPrompt}
                            onChange={(e) => setMultiLipSyncPrompt(e.target.value)}
                          />
                          <input
                            className="field text-xs"
                            placeholder="Output filename"
                            value={multiLipSyncOutputName}
                            onChange={(e) => setMultiLipSyncOutputName(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-4 flex justify-between items-center">
                      <div className="text-[10px] text-neutral-500">
                        {multiLipSyncBoundingBoxes.length} character(s) • {multiLipSyncBoundingBoxes.filter(b => b.audio_track_id).length} assigned
                      </div>
                      <div className="flex gap-2">
                        <Dialog.Close asChild>
                          <button className="button">Cancel</button>
                        </Dialog.Close>
                        <button
                          className="button-primary"
                          onClick={generateMultiCharacterLipSync}
                          disabled={!multiLipSyncImageId || multiLipSyncBoundingBoxes.length === 0 || multiLipSyncBoundingBoxes.some(b => !b.audio_track_id)}
                        >
                          Generate Multi-Character Lip-Sync
                        </button>
                      </div>
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
                className="button text-xs"
                onClick={async () => {
                  const jobId = startJob('Fixing video formats...');
                  try {
                    const r = await fetch(`http://127.0.0.1:8000/storage/${projectId}/media/fix-formats`, {
                      method: 'POST'
                    });
                    const d = await r.json();
                    if (d.status === 'ok') {
                      await refreshMedia();
                      finishJob(jobId, 'done', `Fixed ${d.fixed} videos`);
                      if (d.fixed > 0) {
                        alert(`Fixed ${d.fixed} video(s) for browser compatibility!`);
                      } else {
                        alert('All videos are already compatible!');
                      }
                    } else {
                      finishJob(jobId, 'error', 'Failed to fix formats');
                    }
                  } catch (e: any) {
                    finishJob(jobId, 'error', e.message);
                  }
                }}
              >
                🔧 Fix Video Formats
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
                      // Visual feedback: highlight drop target
                      e.currentTarget.classList.add('ring-2', 'ring-violet-400');
                    }}
                    onDragLeave={(e) => {
                      e.currentTarget.classList.remove('ring-2', 'ring-violet-400');
                    }}
                    onDrop={async (e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      e.currentTarget.classList.remove('ring-2', 'ring-violet-400');
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
                      setCurrentImageUrl(null); // Clear any image preview
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
                      {sh.file_path && (
                        <button
                          className="absolute bottom-1 right-1 bg-black/80 hover:bg-black/90 text-white p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={async (e) => {
                            e.stopPropagation();
                            try {
                              await fetch('http://127.0.0.1:8000/storage/reveal-file', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ file_path: sh.file_path })
                              });
                            } catch (err) {
                              console.error('Failed to reveal file:', err);
                            }
                          }}
                          title="Reveal in Finder"
                        >
                          <FolderOpen className="w-3 h-3" />
                        </button>
                      )}
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
                            // Match by path (exact or normalized)
                            const videoId = media.find(m => {
                              const mPath = m.path?.replace('project_data/', '');
                              const shPath = sh.file_path?.replace('project_data/', '');
                              return mPath === shPath || m.path === sh.file_path;
                            })?.id;
                            console.log('Lip button clicked for shot:', sh.shot_id, 'file_path:', sh.file_path, 'found videoId:', videoId, 'media:', media.map(m => ({ id: m.id, path: m.path })));
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
                            // Extract last frame if missing
                            if (!sh.last_frame_path && sh.file_path) {
                              try {
                                const r = await fetch('http://127.0.0.1:8000/frames/last', {
                                  method: 'POST',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({ 
                                    project_id: projectId, 
                                    video_path: sh.file_path 
                                  })
                                });
                                const d = await r.json();
                                if (d.status === 'ok') {
                                  // Refresh scene to get updated shot with last_frame_path
                                  const sceneRes = await fetch(`http://127.0.0.1:8000/storage/${projectId}/scenes/${selectedSceneId}`);
                                  const sceneData = await sceneRes.json();
                                  setSceneDetail(sceneData.scene ?? null);
                                  setVxStartFramePath(d.image_path);
                                } else {
                                  alert(d.detail || 'Failed to extract last frame');
                                  return;
                                }
                              } catch (err) {
                                alert('Failed to extract frame');
                                return;
                              }
                            } else if (sh.last_frame_path) {
                              setVxStartFramePath(sh.last_frame_path);
                            } else {
                              alert('This shot has no video file');
                              return;
                            }
                            
                            // Auto-configure for continuity from THIS shot
                            setIsContPrevFrame(true);
                            setVxImageMode('start_end');
                            setVxUsePrevLast(true);
                            setVxStartImageId(null);
                            setVxStartFromVideoId(null);
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
                      // If frames are planned, use them
                      if (vxStartImageId || vxStartFramePath || vxEndImageId) {
                        setVxImageMode('start_end');
                      }
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
                      // Match by path (exact or normalized)
                      const videoId = media.find(m => {
                        const mPath = m.path?.replace('project_data/', '');
                        const shPath = shot.file_path?.replace('project_data/', '');
                        return mPath === shPath || m.path === shot.file_path;
                      })?.id;
                      console.log('Inspector lip-sync button clicked for shot:', shot.shot_id, 'file_path:', shot.file_path, 'found videoId:', videoId, 'media:', media.map(m => ({ id: m.id, path: m.path })));
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
      
      {/* Prompt Templates Modal */}
      <Dialog.Root open={isTemplatesOpen} onOpenChange={setIsTemplatesOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/60" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] max-h-[80vh] card p-5 overflow-y-auto">
            <Dialog.Title className="text-sm font-semibold mb-2">Prompt Templates</Dialog.Title>
            <Dialog.Description className="text-xs text-neutral-400 mb-4">
              Click a template to use it, or create your own.
            </Dialog.Description>
            
            <div className="space-y-2 mb-4">
              {promptTemplates.map((template, idx) => (
                <div key={idx} className="flex items-start gap-2 p-3 bg-neutral-900/50 rounded border border-neutral-800 hover:border-violet-500/50 transition-colors">
                  <div className="flex-1">
                    <div className="text-xs font-medium text-neutral-200 mb-1">{template.name}</div>
                    <div className="text-[11px] text-neutral-400">{template.prompt}</div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      className="button text-[10px] px-2 py-1"
                      onClick={() => {
                        setGenPrompt(template.prompt);
                        setIsTemplatesOpen(false);
                      }}
                    >
                      Use
                    </button>
                    <button
                      className="button text-[10px] px-2 py-1 text-red-400"
                      onClick={() => {
                        const newTemplates = promptTemplates.filter((_, i) => i !== idx);
                        setPromptTemplates(newTemplates);
                        localStorage.setItem('promptTemplates', JSON.stringify(newTemplates));
                      }}
                    >
                      ×
                    </button>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="border-t border-neutral-800 pt-4">
              <div className="text-xs font-medium text-neutral-300 mb-2">Add New Template</div>
              <input
                className="field mb-2"
                placeholder="Template name"
                id="newTemplateName"
              />
              <textarea
                className="field h-20 mb-2"
                placeholder="Template prompt"
                id="newTemplatePrompt"
              />
              <button
                className="button-primary w-full"
                onClick={() => {
                  const nameInput = document.getElementById('newTemplateName') as HTMLInputElement;
                  const promptInput = document.getElementById('newTemplatePrompt') as HTMLTextAreaElement;
                  if (nameInput.value && promptInput.value) {
                    const newTemplates = [...promptTemplates, { name: nameInput.value, prompt: promptInput.value }];
                    setPromptTemplates(newTemplates);
                    localStorage.setItem('promptTemplates', JSON.stringify(newTemplates));
                    nameInput.value = '';
                    promptInput.value = '';
                  }
                }}
              >
                Add Template
              </button>
            </div>
            
            <div className="mt-4 flex justify-end">
              <Dialog.Close asChild>
                <button className="button">Close</button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}