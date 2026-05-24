"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { api, Project, Scene, MEDIA_BASE } from "@/lib/api";
import {
  ArrowLeft, Loader2, Sparkles, Film, Image as ImageIcon, Volume2,
  CheckCircle, Play, Save, RefreshCw, Layers, Sliders, ChevronLeft,
  ChevronRight, AlertCircle, StopCircle, Check, X, Clock, Edit3,
  ShieldAlert, Database, Search, TrendingUp, FileText, Eye, Maximize2,
  Activity, Cpu, Zap, Terminal, ChevronDown, Video, Clapperboard
} from "lucide-react";

/* ─── stage configuration ───────────────────────────────── */
const STAGE_CONFIG: Record<string, {
  icon: React.ElementType;
  label: string;
  verb: string;
  color: string;
  glow: string;
  ring: string;
}> = {
  ingest: {
    icon: Database, label: "Content Ingestion", verb: "Extracting content...",
    color: "text-emerald-400", glow: "glow-emerald",
    ring: "border-emerald-500/60 bg-emerald-500/10",
  },
  research: {
    icon: Search, label: "AI Research", verb: "Analyzing topic...",
    color: "text-sky-400", glow: "glow-sky",
    ring: "border-sky-500/60 bg-sky-500/10",
  },
  viral_strategy: {
    icon: TrendingUp, label: "Viral Strategy", verb: "Building hooks & CTAs...",
    color: "text-amber-400", glow: "glow-amber",
    ring: "border-amber-500/60 bg-amber-500/10",
  },
  script: {
    icon: FileText, label: "Script Writing", verb: "Writing narration...",
    color: "text-violet-400", glow: "glow-violet",
    ring: "border-violet-500/60 bg-violet-500/10",
  },
  storyboard: {
    icon: Film, label: "Storyboarding", verb: "Generating scenes...",
    color: "text-fuchsia-400", glow: "glow-violet",
    ring: "border-fuchsia-500/60 bg-fuchsia-500/10",
  },
};

const STAGE_ORDER = ["ingest","research","viral_strategy","script","storyboard"];

/* ─── countdown ring component ─────────────────────────── */
function CountdownRing({ countdown, target }: { countdown: number; target: number }) {
  const r = 22;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, countdown / target);
  const dashArray = `${pct * circ} ${circ}`;
  const color = pct > 0.6 ? "#8b5cf6" : pct > 0.3 ? "#f59e0b" : "#f43f5e";

  return (
    <div className="relative flex items-center justify-center w-14 h-14">
      <svg width="56" height="56" className="-rotate-90">
        <circle cx="28" cy="28" r={r} stroke="rgba(255,255,255,0.06)" strokeWidth="3" fill="none" />
        <circle
          cx="28" cy="28" r={r}
          stroke={color} strokeWidth="3" fill="none"
          strokeDasharray={dashArray}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.8s ease, stroke 0.5s ease" }}
        />
      </svg>
      <span className="absolute text-sm font-bold font-mono" style={{ color }}>
        {countdown}
      </span>
    </div>
  );
}

/* ─── skeleton scene card ────────────────────────────────── */
function SceneCardSkeleton() {
  return (
    <div className="w-40 flex-shrink-0 rounded-xl border border-border bg-card p-2 overflow-hidden">
      <div className="aspect-video bg-zinc-900 rounded-lg mb-2 shimmer" />
      <div className="skeleton h-2.5 w-2/3 mb-1.5" />
      <div className="skeleton h-2 w-full" />
    </div>
  );
}

/* ─── main studio page ──────────────────────────────────── */
export default function ProjectWorkspace() {
  const params = useParams();
  const projectId = params.id as string;

  const [project,      setProject]      = useState<Project | null>(null);
  const [loading,      setLoading]       = useState(true);
  const [wsStatus,     setWsStatus]      = useState<string>("Disconnected");
  const [wsProgress,   setWsProgress]    = useState<number>(0);
  const [wsMessage,    setWsMessage]     = useState<string>("");
  const [imageVersion, setImageVersion]  = useState<number>(1);
  const [selectedSceneIndex, setSelectedSceneIndex] = useState<number>(0);

  // Inspector form states
  const [narration,          setNarration]          = useState("");
  const [imagePrompt,        setImagePrompt]         = useState("");
  const [subtitle,           setSubtitle]            = useState("");
  const [sceneDuration,      setSceneDuration]       = useState<number>(3);
  const [transitionStyle,    setTransitionStyle]     = useState<"fade"|"slide"|"none">("fade");
  const [selectedImageIndex, setSelectedImageIndex] = useState<number>(0);

  // Approval / stage-edit states
  const [countdown,          setCountdown]      = useState<number>(0);
  const [timerActive,        setTimerActive]    = useState<boolean>(false);
  const [isEditingStage,     setIsEditingStage] = useState<boolean>(false);
  const [stageContentText,   setStageContentText]   = useState<string>("");
  const [stagePromptOverride,setStagePromptOverride] = useState<string>("");
  const [stageToneOverride,  setStageToneOverride]   = useState<string>("");

  // Activity
  const [activityLogs,    setActivityLogs]    = useState<string[]>([]);
  const [showDebug,       setShowDebug]        = useState<boolean>(false);
  const [latestWsPayload, setLatestWsPayload] = useState<any>(null);

  // UI spinners
  const [savingScene,       setSavingScene]       = useState(false);
  const [regeneratingScene, setRegeneratingScene] = useState(false);
  const [cancelling,        setCancelling]         = useState(false);
  const [retrying,          setRetrying]           = useState(false);
  const [actionLoading,     setActionLoading]      = useState(false);

  // Image lightbox (visual only)
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  // Left panel collapsed
  const [leftCollapsed, setLeftCollapsed] = useState(false);

  const wsRef          = useRef<WebSocket | null>(null);
  const timerRef       = useRef<NodeJS.Timeout | null>(null);
  const consoleBottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    loadProject();
    setupWebSocket();
    return () => {
      stopTimer();
      if (wsRef.current) wsRef.current.close();
    };
  }, [projectId]);

  // Sync inspector when scene changes
  useEffect(() => {
    if (project?.scenes?.length) {
      const scene = project.scenes.find(s => s.scene_index === selectedSceneIndex) || project.scenes[0];
      setNarration(scene.narration_text);
      setImagePrompt(scene.image_prompt);
      setSubtitle(scene.subtitle_text);
      setSceneDuration(scene.scene_duration || scene.audio_duration || 3);
      setTransitionStyle((scene.transition_style as any) || "fade");
      setSelectedImageIndex(scene.selected_image_index || 0);
    }
  }, [selectedSceneIndex, project]);

  // Autoscroll console
  useEffect(() => {
    consoleBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activityLogs]);

  // Approval countdown
  useEffect(() => {
    if (project?.status === "REVIEW_PENDING" && !project.stage_approved) {
      const secs = project.current_stage === "storyboard" ? 20 : 5;
      if (!timerActive && !isEditingStage) {
        setCountdown(secs);
        setTimerActive(true);
        startCountdown(secs);
      }
    } else {
      stopTimer();
    }
  }, [project, timerActive, isEditingStage]);

  function startCountdown(init: number) {
    if (timerRef.current) clearInterval(timerRef.current);
    let cur = init;
    timerRef.current = setInterval(async () => {
      cur -= 1;
      setCountdown(cur);
      if (cur <= 0) {
        clearInterval(timerRef.current!);
        setTimerActive(false);
        try { await api.approveStage(projectId); loadProject(); }
        catch (e) { console.error("Auto approve failed:", e); }
      }
    }, 1000);
  }

  function stopTimer() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    setTimerActive(false);
  }

  function handleInteraction() { if (timerActive) stopTimer(); }

  async function loadProject() {
    try {
      const data = await api.getProject(projectId);
      setProject(data);
      setImageVersion(v => v + 1);
      if (data.current_stage === "research")        setStageContentText(data.summary || "");
      else if (data.current_stage === "viral_strategy") setStageContentText(data.viral_hooks || "");
      else if (data.current_stage === "script")     setStageContentText(data.script || "");
      else setStageContentText("");
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  function setupWebSocket() {
    setWsStatus("Connecting...");
    wsRef.current = api.connectWS(
      projectId,
      (data) => {
        setWsStatus("Connected");
        setWsProgress(data.progress || 0);
        setWsMessage(data.message || "");
        setLatestWsPayload(data);
        if (data.message) {
          setActivityLogs(prev => {
            if (prev.length > 0 && prev[prev.length - 1].includes(data.message!)) return prev;
            return [...prev, `[${new Date().toLocaleTimeString()}] ${data.message}`];
          });
        }
        if (["workflow.stage.completed","workflow.stage.failed","workflow.cancelled"].includes(data.type || "") ||
            ["COMPLETED","FAILED"].includes(data.status || "")) {
          loadProject();
        }
      },
      () => setWsStatus("Disconnected"),
    );
  }

  /* handlers — unchanged logic */
  async function handleApprove() {
    handleInteraction(); setActionLoading(true);
    try { await api.approveStage(projectId); await loadProject(); }
    catch (e) { console.error(e); alert("Failed to approve stage."); }
    finally { setActionLoading(false); }
  }

  async function handleRerun() {
    handleInteraction(); setActionLoading(true);
    try { await api.rerunStage(projectId); await loadProject(); }
    catch (e) { console.error(e); alert("Failed to rerun stage."); }
    finally { setActionLoading(false); }
  }

  async function handleSaveAndContinue() {
    handleInteraction(); setActionLoading(true);
    try {
      await api.editStage(projectId, { content_text: stageContentText, prompt_override: stagePromptOverride || null, tone_override: stageToneOverride || null });
      setIsEditingStage(false); setStagePromptOverride(""); setStageToneOverride("");
      await loadProject();
    } catch (e) { console.error(e); alert("Failed to save changes."); }
    finally { setActionLoading(false); }
  }

  async function handleGlobalStop() {
    setCancelling(true);
    try { await api.cancelProject(projectId); await loadProject(); }
    catch (e) { console.error(e); }
    finally { setCancelling(false); }
  }

  async function handleMoveScene(index: number, dir: "left"|"right") {
    if (!project?.scenes) return;
    const sorted = [...project.scenes].sort((a, b) => a.scene_index - b.scene_index);
    const ti = dir === "left" ? index - 1 : index + 1;
    if (ti < 0 || ti >= sorted.length) return;
    const tmp = sorted[index].scene_index;
    sorted[index].scene_index = sorted[ti].scene_index;
    sorted[ti].scene_index = tmp;
    try {
      setLoading(true);
      await api.updateScenes(projectId, sorted.map(s => ({ id: s.id, narration_text: s.narration_text, image_prompt: s.image_prompt, subtitle_text: s.subtitle_text, image_path_1: s.image_path_1, image_path_2: s.image_path_2, selected_image_index: s.selected_image_index, transition_style: s.transition_style, scene_duration: s.scene_duration })));
      await loadProject(); setSelectedSceneIndex(ti);
    } catch { alert("Failed to swap scenes"); }
    finally { setLoading(false); }
  }

  async function handleSaveSceneChanges() {
    if (!project?.scenes) return;
    const scene = project.scenes.find(s => s.scene_index === selectedSceneIndex);
    if (!scene) return;
    setSavingScene(true);
    try {
      await api.updateScenes(projectId, project.scenes.map(s => s.id === scene.id
        ? { id: s.id, narration_text: narration, image_prompt: imagePrompt, subtitle_text: subtitle, image_path_1: s.image_path_1, image_path_2: s.image_path_2, selected_image_index: selectedImageIndex, transition_style: transitionStyle, scene_duration: sceneDuration }
        : { id: s.id, narration_text: s.narration_text, image_prompt: s.image_prompt, subtitle_text: s.subtitle_text, image_path_1: s.image_path_1, image_path_2: s.image_path_2, selected_image_index: s.selected_image_index, transition_style: s.transition_style, scene_duration: s.scene_duration }
      ));
      await loadProject();
    } catch { alert("Failed to save changes."); }
    finally { setSavingScene(false); }
  }

  async function handleRegenerateScene() {
    if (!project?.scenes) return;
    const scene = project.scenes.find(s => s.scene_index === selectedSceneIndex);
    if (!scene) return;
    await handleSaveSceneChanges();
    setRegeneratingScene(true);
    try { await api.regenerateScene(projectId, scene.id); }
    catch { alert("Failed to start scene regeneration."); }
    finally { setRegeneratingScene(false); }
  }

  async function handleRetryStoryboard() {
    setRetrying(true);
    try { await api.generateStoryboard(projectId); await loadProject(); }
    catch { alert("Failed to retry."); }
    finally { setRetrying(false); }
  }

  /* ─── computed ─── */
  const getSceneImageSrc = (scene: Scene, index: number) => {
    const path = index === 0 ? scene.image_path_1 : scene.image_path_2;
    if (path) {
      const filename = path.split(/[\\\/]/).pop();
      return `${MEDIA_BASE}/${projectId}/${filename}?v=${imageVersion}`;
    }
    return `${MEDIA_BASE}/${projectId}/scene_${scene.scene_index}_img${index + 1}.png?v=${imageVersion}`;
  };

  const getCanvasAspectRatio = () => {
    switch (project?.aspect_ratio) {
      case "16:9": return "aspect-video max-w-3xl";
      case "1:1":  return "aspect-square max-w-lg";
      default:     return "aspect-[9/16] max-w-[300px]";
    }
  };

  const getStageMetadata = () => {
    if (!project?.stage_metadata) return null;
    try { const m = JSON.parse(project.stage_metadata); return m[project.current_stage] || null; }
    catch { return null; }
  };

  /* ─── loading / not found ─── */
  if (loading) return (
    <div className="h-screen bg-background flex flex-col items-center justify-center gap-4">
      <div className="relative">
        <Loader2 className="w-10 h-10 text-primary animate-spin" />
        <div className="absolute inset-0 animate-pulse-glow rounded-full" />
      </div>
      <p className="text-muted-foreground text-sm font-mono">Loading workspace...</p>
    </div>
  );

  if (!project) return (
    <div className="h-screen bg-background flex flex-col items-center justify-center gap-5">
      <AlertCircle className="w-14 h-14 text-rose-500" />
      <div className="text-center">
        <h2 className="text-xl font-bold mb-1">Project Not Found</h2>
        <p className="text-muted-foreground text-sm">This project may have been deleted.</p>
      </div>
      <Link href="/" className="bg-primary px-5 py-2.5 rounded-lg text-white text-sm font-semibold hover:bg-violet-600 transition-colors">
        ← Back to Dashboard
      </Link>
    </div>
  );

  const scenes = [...(project.scenes || [])].sort((a, b) => a.scene_index - b.scene_index);
  const activeScene = scenes.find(s => s.scene_index === selectedSceneIndex) || scenes[0];
  const stageMeta = getStageMetadata();
  const approvalTargetSecs = project.current_stage === "storyboard" ? 20 : 5;
  const isWorkflowActive = STAGE_ORDER.includes(project.current_stage) &&
    !["REVIEW_PENDING","FAILED","CANCELLED"].includes(project.status);
  const isGeneratingMedia = ["GENERATING","RENDERING"].includes(project.status);
  const currentStageCfg = STAGE_CONFIG[project.current_stage] || STAGE_CONFIG.ingest;

  return (
    <div className="h-screen bg-background text-foreground flex flex-col overflow-hidden">

      {/* ════════════════ STUDIO HEADER ════════════════ */}
      <header className="shrink-0 border-b border-border bg-glass-md z-20 px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link href="/" className="shrink-0 p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-white transition-all border border-transparent hover:border-border">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div className="flex items-center gap-2 text-[11px] text-zinc-600 font-mono">
            <span>Dashboard</span>
            <ChevronRight className="w-3 h-3" />
            <span className="text-zinc-300 truncate max-w-[200px]">{project.title}</span>
          </div>
        </div>

        {/* center: stage info */}
        <div className="hidden md:flex items-center gap-2">
          <div className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full border ${currentStageCfg.ring}`}>
            <currentStageCfg.icon className={`w-3 h-3 ${currentStageCfg.color}`} />
            <span className={currentStageCfg.color}>{currentStageCfg.label}</span>
          </div>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase tracking-wider ${
            project.status === "COMPLETED"      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25" :
            project.status === "FAILED"         ? "bg-rose-500/10 text-rose-400 border-rose-500/25" :
            project.status === "REVIEW_PENDING" ? "bg-amber-500/10 text-amber-400 border-amber-500/25" :
            project.status === "CANCELLED"      ? "bg-zinc-800 text-zinc-500 border-zinc-700" :
            "bg-violet-500/10 text-violet-400 border-violet-500/25"
          }`}>
            {project.status.replace(/_/g," ")}
          </span>
        </div>

        {/* right: controls */}
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => { loadProject(); setupWebSocket(); }}
            className="p-1.5 bg-zinc-900 hover:bg-zinc-800 border border-border rounded-lg text-zinc-500 hover:text-white transition-all" title="Refresh">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          {/* WS indicator */}
          <div className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1.5 rounded-lg border font-mono ${
            wsStatus === "Connected"
              ? "bg-emerald-500/8 text-emerald-400 border-emerald-500/20"
              : "bg-rose-500/8 text-rose-400 border-rose-500/20"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${wsStatus === "Connected" ? "bg-emerald-400" : "bg-rose-400 animate-pulse"}`} />
            {wsStatus === "Connected" ? "Live" : "Offline"}
          </div>

          {(isWorkflowActive || isGeneratingMedia) && (
            <button onClick={handleGlobalStop} disabled={cancelling}
              className="flex items-center gap-1.5 bg-rose-600/90 hover:bg-rose-600 text-white font-bold px-3 py-1.5 rounded-lg text-xs transition-all disabled:opacity-50 border border-rose-500/40">
              {cancelling ? <Loader2 className="w-3 h-3 animate-spin" /> : <StopCircle className="w-3 h-3" />}
              Stop
            </button>
          )}
        </div>
      </header>

      {/* ════════════════ THREE-COLUMN LAYOUT ════════════════ */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* ═══ LEFT PANEL: Workflow + Console ═══ */}
        <motion.aside
          animate={{ width: leftCollapsed ? 48 : 272 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="shrink-0 border-r border-border bg-black/30 flex flex-col overflow-hidden relative"
        >
          {/* collapse toggle */}
          <button
            onClick={() => setLeftCollapsed(!leftCollapsed)}
            className="absolute top-3 right-2 z-10 p-1 rounded-md hover:bg-zinc-800 text-zinc-600 hover:text-zinc-300 transition-all"
          >
            <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${leftCollapsed ? "rotate-180" : ""}`} />
          </button>

          {!leftCollapsed && (
            <div className="flex flex-col flex-1 overflow-hidden p-4 gap-4">

              {/* ── Workflow Timeline ── */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Layers className="w-3.5 h-3.5 text-zinc-500" />
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Pipeline</span>
                </div>
                <div className="space-y-1">
                  {STAGE_ORDER.map((stageKey, idx) => {
                    const cfg = STAGE_CONFIG[stageKey];
                    const currentIdx = STAGE_ORDER.indexOf(project.current_stage);
                    const isCompleted = idx < currentIdx ||
                      ["COMPLETED","GENERATING","RENDERING"].includes(project.status);
                    const isActive = idx === currentIdx;
                    const isFailed = isActive && project.status === "FAILED";
                    const isWaiting = isActive && project.status === "REVIEW_PENDING";

                    return (
                      <div key={stageKey}>
                        <div className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all ${
                          isActive && !isFailed ? `${cfg.ring} border` : "border border-transparent"
                        } ${isActive && isWorkflowActive ? "animate-pulse-glow" : ""}`}>
                          {/* icon bubble */}
                          <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${
                            isCompleted ? "bg-emerald-500/15 border border-emerald-500/30" :
                            isFailed    ? "bg-rose-500/15 border border-rose-500/30" :
                            isActive    ? `${cfg.ring} border` :
                            "bg-zinc-900 border border-border"
                          }`}>
                            {isCompleted
                              ? <Check className="w-3 h-3 text-emerald-400" />
                              : isFailed
                                ? <X className="w-3 h-3 text-rose-400" />
                                : <cfg.icon className={`w-3 h-3 ${isActive ? cfg.color : "text-zinc-600"}`} />
                            }
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`text-[11px] font-semibold leading-none truncate ${
                              isCompleted ? "text-zinc-400" :
                              isActive    ? "text-white" :
                              "text-zinc-600"
                            }`}>{cfg.label}</p>
                            {isActive && (
                              <p className={`text-[9px] mt-0.5 font-mono truncate ${
                                isWaiting ? "text-amber-400" :
                                isFailed  ? "text-rose-400" :
                                cfg.color
                              }`}>
                                {isWaiting ? "⏸ Awaiting approval" : isFailed ? "✗ Failed" : cfg.verb}
                              </p>
                            )}
                          </div>
                        </div>
                        {idx < STAGE_ORDER.length - 1 && (
                          <div className={`ml-5 w-[1px] h-2 mx-auto ${isCompleted ? "bg-emerald-500/30" : "bg-border"}`} />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* ── AI Activity Console ── */}
              <div className="flex-1 flex flex-col min-h-0 border-t border-border/50 pt-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-zinc-500" />
                    <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Activity</span>
                  </div>
                  <button onClick={() => setShowDebug(!showDebug)} className="text-[9px] font-mono text-zinc-600 hover:text-zinc-400 transition-colors">
                    {showDebug ? "hide json" : "show json"}
                  </button>
                </div>

                {/* console area */}
                <div className="flex-1 bg-black/60 rounded-xl border border-border/60 p-3 font-mono text-[10px] overflow-y-auto flex flex-col min-h-0">
                  <div className="text-emerald-400 font-bold mb-2 flex items-center gap-1">
                    <Cpu className="w-2.5 h-2.5" />
                    &gt; llama3.2:3b · ComfyUI · Piper TTS
                  </div>

                  <div className="flex-1 space-y-1">
                    {activityLogs.length === 0 ? (
                      <div className="text-zinc-700 italic">Console idle. Awaiting events...</div>
                    ) : (
                      activityLogs.map((log, i) => (
                        <div key={i} className="text-zinc-400 leading-relaxed break-words">
                          <span className="text-zinc-700">{log.match(/\[.*?\]/)?.[0]}</span>
                          {" "}
                          <span className={i === activityLogs.length - 1 ? "text-violet-300" : ""}>
                            {log.replace(/\[.*?\]\s?/, "")}
                          </span>
                        </div>
                      ))
                    )}
                    {isWorkflowActive && (
                      <div className="flex items-center gap-1.5 text-violet-400 mt-1">
                        <Loader2 className="w-2.5 h-2.5 animate-spin" />
                        <span>Processing<span className="animate-blink-cursor">_</span></span>
                      </div>
                    )}
                    <div ref={consoleBottomRef} />
                  </div>

                  {/* WS progress bar */}
                  {isGeneratingMedia && wsProgress > 0 && (
                    <div className="border-t border-zinc-800/60 pt-2 mt-2">
                      <div className="flex justify-between text-[9px] text-zinc-500 mb-1">
                        <span>Rendering</span><span>{wsProgress.toFixed(0)}%</span>
                      </div>
                      <div className="w-full bg-zinc-900 rounded-full h-1 overflow-hidden">
                        <div className="h-full progress-gradient transition-all duration-500 rounded-full" style={{ width: `${wsProgress}%` }} />
                      </div>
                    </div>
                  )}
                </div>

                {showDebug && latestWsPayload && (
                  <pre className="mt-2 bg-zinc-950 border border-zinc-800 rounded-lg p-2 text-[9px] font-mono text-zinc-500 overflow-x-auto max-h-28">
                    {JSON.stringify(latestWsPayload, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </motion.aside>

        {/* ═══ CENTER: Stage Review + Canvas + Storyboard ═══ */}
        <main className="flex-1 flex flex-col overflow-y-auto min-w-0 bg-zinc-950/30">

          {/* ── Stage Approval Dialog ── */}
          <AnimatePresence>
            {project.status === "REVIEW_PENDING" && (
              <motion.div
                key="approval"
                initial={{ opacity: 0, y: -12 }}
                animate={{ opacity: 1, y:  0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3, ease: [0.16,1,0.3,1] }}
                className="shrink-0 m-4 mb-0 rounded-2xl border border-amber-500/20 bg-glass-md overflow-hidden"
                onClick={handleInteraction}
              >
                {/* rainbow accent top bar */}
                <div className="h-[2px] bg-gradient-to-r from-violet-500 via-amber-400 to-fuchsia-500" />

                <div className="p-4 md:p-5">
                  <div className="flex items-start justify-between gap-4 mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center">
                        <Sparkles className="w-4 h-4 text-amber-400" />
                      </div>
                      <div>
                        <h3 className="font-bold text-white text-sm">
                          Stage Review —{" "}
                          <span className={`${currentStageCfg.color} uppercase font-mono text-xs`}>
                            {project.current_stage.replace(/_/g," ")}
                          </span>
                        </h3>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          Validate AI output before pipeline advances
                        </p>
                      </div>
                    </div>

                    {/* countdown ring */}
                    {timerActive && (
                      <CountdownRing countdown={countdown} target={approvalTargetSecs} />
                    )}
                  </div>

                  {/* metrics strip */}
                  <div className="grid grid-cols-4 gap-2 bg-black/30 rounded-xl p-3 border border-border/50 text-[11px] mb-4">
                    {[
                      { label: "Tokens",   val: stageMeta?.tokens || "~180",      color: "text-zinc-300" },
                      { label: "Cost",     val: "$0.00 Local",                     color: "text-emerald-400" },
                      { label: "Duration", val: stageMeta?.duration_ms ? `${(stageMeta.duration_ms/1000).toFixed(1)}s` : "—", color: "text-zinc-300" },
                      { label: "Reruns",   val: stageMeta?.reruns ?? 0,            color: "text-violet-400" },
                    ].map(m => (
                      <div key={m.label} className="text-center">
                        <div className="text-zinc-600 text-[9px] uppercase mb-0.5">{m.label}</div>
                        <div className={`font-semibold ${m.color}`}>{m.val}</div>
                      </div>
                    ))}
                  </div>

                  {/* stage output */}
                  {!isEditingStage ? (
                    <div className="bg-black/40 border border-border/60 rounded-xl p-3.5 text-[12px] text-zinc-300 leading-relaxed max-h-40 overflow-y-auto mb-4">
                      {project.current_stage === "research" && (project.summary || "No summary generated.")}
                      {project.current_stage === "viral_strategy" && (
                        <div className="space-y-2">
                          <p className="text-xs font-bold text-white">Viral Hooks:</p>
                          {project.viral_hooks && (
                            <ul className="list-disc pl-4 space-y-1">
                              {JSON.parse(project.viral_hooks).map((h: string, i: number) => (
                                <li key={i} className="text-zinc-300">{h}</li>
                              ))}
                            </ul>
                          )}
                          <p className="text-xs font-bold text-white mt-2">CTA:</p>
                          <p>{project.viral_cta}</p>
                        </div>
                      )}
                      {project.current_stage === "script" && (project.script || "No script generated.")}
                      {project.current_stage === "storyboard" && (
                        <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                          <Check className="w-4 h-4" />
                          Storyboard complete — {scenes.length} scenes generated. Review the timeline below.
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3 mb-4">
                      <div>
                        <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Stage Output (Editable)</label>
                        <textarea rows={3} value={stageContentText} onChange={e => setStageContentText(e.target.value)} onClick={handleInteraction}
                          className="w-full bg-input border border-border rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-primary resize-none leading-relaxed transition-colors" />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Custom Instruction</label>
                          <input type="text" placeholder="e.g. emphasize Shivaji's valor" value={stagePromptOverride} onChange={e => setStagePromptOverride(e.target.value)} onClick={handleInteraction}
                            className="w-full bg-input border border-border rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-primary transition-colors" />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Tone / Style</label>
                          <input type="text" placeholder="e.g. inspirational, cinematic" value={stageToneOverride} onChange={e => setStageToneOverride(e.target.value)} onClick={handleInteraction}
                            className="w-full bg-input border border-border rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-primary transition-colors" />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* action row */}
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex gap-2">
                      <button onClick={handleRerun} disabled={actionLoading}
                        className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 border border-border text-zinc-300 text-xs font-semibold px-3 py-2 rounded-lg transition-all disabled:opacity-50">
                        <RefreshCw className="w-3 h-3" /> Re-run
                      </button>
                      {!isEditingStage ? (
                        <button onClick={() => { handleInteraction(); setIsEditingStage(true); }}
                          className="flex items-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 border border-border text-zinc-300 text-xs font-semibold px-3 py-2 rounded-lg transition-all">
                          <Edit3 className="w-3 h-3" /> Edit
                        </button>
                      ) : (
                        <button onClick={handleSaveAndContinue} disabled={actionLoading}
                          className="flex items-center gap-1.5 bg-violet-600/90 hover:bg-violet-600 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-all disabled:opacity-50">
                          <Save className="w-3 h-3" /> Save & Continue
                        </button>
                      )}
                    </div>

                    <button onClick={handleApprove} disabled={actionLoading}
                      className="flex items-center gap-2 bg-primary hover:bg-violet-600 text-white text-sm font-bold px-5 py-2 rounded-xl shadow-lg shadow-primary/20 transition-all hover:shadow-primary/35 hover:-translate-y-0.5 disabled:opacity-50">
                      {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                      Approve Stage
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Video / Preview Canvas ── */}
          <div className="flex-1 flex items-center justify-center p-5">
            <div className={`relative w-full bg-black rounded-2xl border border-border/60 shadow-2xl overflow-hidden flex items-center justify-center ${getCanvasAspectRatio()}`}>

              {/* corner decorations */}
              <div className="absolute top-2 left-2 w-4 h-4 border-t-2 border-l-2 border-zinc-700 rounded-tl-lg" />
              <div className="absolute top-2 right-2 w-4 h-4 border-t-2 border-r-2 border-zinc-700 rounded-tr-lg" />
              <div className="absolute bottom-2 left-2 w-4 h-4 border-b-2 border-l-2 border-zinc-700 rounded-bl-lg" />
              <div className="absolute bottom-2 right-2 w-4 h-4 border-b-2 border-r-2 border-zinc-700 rounded-br-lg" />

              {project.status === "COMPLETED" ? (
                <video
                  src={`${MEDIA_BASE}/${projectId}/final.mp4?v=${imageVersion}`}
                  controls className="w-full h-full object-contain"
                  poster={activeScene?.image_path_1 ? getSceneImageSrc(activeScene, activeScene.selected_image_index) : undefined}
                />
              ) : isGeneratingMedia ? (
                <div className="absolute inset-0 bg-zinc-950/95 flex flex-col items-center justify-center gap-4 p-6 text-center">
                  <div className="relative">
                    <div className="w-14 h-14 rounded-full border-2 border-primary/20 flex items-center justify-center">
                      <Clapperboard className="w-6 h-6 text-primary animate-pulse" />
                    </div>
                    <div className="absolute inset-0 w-14 h-14 rounded-full border-t-2 border-primary animate-spin" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-1">{project.status}</h4>
                    <p className="text-[11px] text-zinc-500 max-w-[180px] mx-auto">{wsMessage || "Compiling cinematic scenes..."}</p>
                  </div>
                  <div className="w-full max-w-[180px]">
                    <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden border border-border">
                      <div className="h-full progress-gradient transition-all duration-700 rounded-full" style={{ width: `${wsProgress}%` }} />
                    </div>
                    <p className="text-[10px] font-mono text-zinc-500 mt-1">{wsProgress.toFixed(0)}% complete</p>
                  </div>
                </div>
              ) : project.status === "CANCELLED" ? (
                <div className="text-center p-6 text-zinc-500">
                  <ShieldAlert className="w-12 h-12 mx-auto mb-3 opacity-50 animate-pulse" />
                  <h4 className="font-bold text-zinc-400 mb-1">Pipeline Stopped</h4>
                  <p className="text-[11px] leading-relaxed max-w-[200px] mx-auto">Your generated outputs are preserved. Approve storyboard to compile.</p>
                </div>
              ) : project.status === "FAILED" ? (
                <div className="text-center p-6 text-rose-400">
                  <AlertCircle className="w-12 h-12 mx-auto mb-3 text-rose-500/70" />
                  <h4 className="font-bold mb-1">Production Failed</h4>
                  <p className="text-[11px] text-rose-300/60 max-w-[200px] mx-auto">{wsMessage || "Check Ollama or ComfyUI logs."}</p>
                </div>
              ) : activeScene?.image_path_1 || activeScene?.image_path_2 ? (
                <img
                  src={getSceneImageSrc(activeScene, activeScene.selected_image_index)}
                  alt="Scene Preview"
                  className="w-full h-full object-contain cursor-zoom-in"
                  onClick={() => setPreviewImage(getSceneImageSrc(activeScene, activeScene.selected_image_index))}
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center p-6">
                  <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-border flex items-center justify-center">
                    <Sparkles className="w-6 h-6 text-zinc-700 animate-pulse" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-zinc-500">Canvas Ready</p>
                    <p className="text-[10px] text-zinc-700 mt-1 max-w-[180px]">Scene previews appear here after generation</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Storyboard Scene Deck ── */}
          <div className="shrink-0 border-t border-border/50 bg-black/20 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sliders className="w-3.5 h-3.5 text-zinc-500" />
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                  Storyboard Timeline
                </span>
                <span className="text-[9px] text-zinc-600">({scenes.length} scenes)</span>
              </div>
            </div>

            <div className="flex items-start gap-3 overflow-x-auto pb-2">
              {loading ? (
                [1,2,3,4,5].map(i => <SceneCardSkeleton key={i} />)
              ) : scenes.length === 0 ? (
                <div className="text-[11px] text-zinc-600 py-4 w-full text-center font-mono italic">
                  No scenes yet — pipeline will populate this after storyboard stage
                </div>
              ) : (
                scenes.map((scene, idx) => {
                  const isSelected = selectedSceneIndex === scene.scene_index;
                  const hasImage = scene.status === "COMPLETED" && (scene.image_path_1 || scene.image_path_2);

                  return (
                    <motion.div
                      key={scene.id}
                      layout
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: idx * 0.04 }}
                      onClick={() => setSelectedSceneIndex(scene.scene_index)}
                      className={`group w-36 flex-shrink-0 rounded-xl border cursor-pointer transition-all overflow-hidden ${
                        isSelected
                          ? "border-primary bg-primary/5 shadow-lg shadow-primary/10 ring-1 ring-primary/40"
                          : "border-border bg-card hover:border-zinc-600"
                      }`}
                    >
                      {/* thumbnail */}
                      <div className="relative w-full aspect-video bg-zinc-900 overflow-hidden">
                        {hasImage ? (
                          <img
                            src={getSceneImageSrc(scene, scene.selected_image_index)}
                            alt={`S${idx + 1}`}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="w-full h-full flex flex-col items-center justify-center text-zinc-700 gap-1">
                            {scene.status === "GENERATING"
                              ? <Loader2 className="w-4 h-4 text-primary animate-spin" />
                              : <ImageIcon className="w-4 h-4" />
                            }
                          </div>
                        )}

                        {/* scene number */}
                        <span className="absolute top-1 left-1 text-[9px] font-mono font-bold bg-black/75 text-zinc-300 px-1.5 rounded leading-5">
                          S{idx + 1}
                        </span>

                        {/* duration */}
                        {(scene.scene_duration || scene.audio_duration) && (
                          <span className="absolute bottom-1 right-1 text-[8px] font-mono bg-black/80 text-zinc-400 px-1 rounded">
                            {(scene.scene_duration || scene.audio_duration || 0).toFixed(1)}s
                          </span>
                        )}
                      </div>

                      {/* caption + controls */}
                      <div className="p-2">
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-[9px] font-mono font-bold uppercase ${
                            scene.status === "COMPLETED" ? "text-emerald-400" :
                            scene.status === "GENERATING" ? "text-violet-400" :
                            "text-zinc-600"
                          }`}>
                            {scene.status}
                          </span>
                          <div className="flex gap-0.5">
                            <button onClick={e => { e.stopPropagation(); handleMoveScene(idx, "left"); }} disabled={idx === 0}
                              className="p-0.5 hover:bg-zinc-700 disabled:opacity-20 rounded text-zinc-500 hover:text-white transition-all">
                              <ChevronLeft className="w-2.5 h-2.5" />
                            </button>
                            <button onClick={e => { e.stopPropagation(); handleMoveScene(idx, "right"); }} disabled={idx === scenes.length - 1}
                              className="p-0.5 hover:bg-zinc-700 disabled:opacity-20 rounded text-zinc-500 hover:text-white transition-all">
                              <ChevronRight className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        </div>
                        <p className="text-[9px] text-zinc-500 line-clamp-2 leading-relaxed">
                          {scene.narration_text}
                        </p>
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>
          </div>
        </main>

        {/* ═══ RIGHT PANEL: Scene Inspector ═══ */}
        <aside className="w-72 shrink-0 border-l border-border bg-black/30 flex flex-col overflow-y-auto">
          <div className="p-4 border-b border-border/50">
            <div className="flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-violet-400" />
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Scene Inspector</span>
              {activeScene && (
                <span className="ml-auto text-[9px] font-mono text-zinc-600">
                  S{(scenes.indexOf(activeScene) + 1)} / {scenes.length}
                </span>
              )}
            </div>
          </div>

          <div className="flex-1 flex flex-col gap-5 p-4 overflow-y-auto">
            {activeScene ? (
              <>
                {/* Image Selection */}
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                    Generated Images
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {[0, 1].map(imgIdx => {
                      const src = getSceneImageSrc(activeScene, imgIdx);
                      const isSelected = selectedImageIndex === imgIdx;
                      return (
                        <div
                          key={imgIdx}
                          onClick={() => setSelectedImageIndex(imgIdx)}
                          className={`group relative aspect-video rounded-lg border overflow-hidden cursor-pointer transition-all ${
                            isSelected
                              ? "border-primary ring-2 ring-primary/30"
                              : "border-border hover:border-zinc-600"
                          }`}
                        >
                          <img
                            src={src} alt={`Option ${imgIdx + 1}`}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                            onError={e => {
                              e.currentTarget.src = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='60' viewBox='0 0 100 60'%3E%3Crect width='100' height='60' fill='%2313131a'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%2327272f' font-size='9' font-family='sans-serif'%3EImage ${imgIdx+1}%3C/text%3E%3C/svg%3E`;
                            }}
                          />
                          {/* expand button */}
                          <button
                            onClick={e => { e.stopPropagation(); setPreviewImage(src); }}
                            className="absolute top-1 right-1 p-0.5 bg-black/70 rounded opacity-0 group-hover:opacity-100 transition-opacity text-white"
                          >
                            <Maximize2 className="w-2.5 h-2.5" />
                          </button>
                          <div className={`absolute top-1 left-1 w-4 h-4 rounded-full flex items-center justify-center text-[8px] font-bold ${
                            isSelected ? "bg-primary text-white" : "bg-black/60 text-zinc-400"
                          }`}>{imgIdx + 1}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Narration */}
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                    <Volume2 className="w-3 h-3 inline mr-1 text-zinc-500" />Voice Narration
                  </label>
                  <textarea rows={3} value={narration} onChange={e => setNarration(e.target.value)}
                    className="w-full bg-input border border-border rounded-lg px-2.5 py-2 text-white text-[11px] focus:outline-none focus:border-primary resize-none leading-relaxed transition-colors" />
                </div>

                {/* Subtitle */}
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                    Caption / Subtitle
                  </label>
                  <textarea rows={2} value={subtitle} onChange={e => setSubtitle(e.target.value)}
                    className="w-full bg-input border border-border rounded-lg px-2.5 py-2 text-white text-[11px] focus:outline-none focus:border-primary resize-none leading-relaxed transition-colors" />
                </div>

                {/* Image Prompt */}
                <div>
                  <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                    <ImageIcon className="w-3 h-3 inline mr-1 text-zinc-500" />Visual Prompt
                  </label>
                  <textarea rows={3} value={imagePrompt} onChange={e => setImagePrompt(e.target.value)}
                    className="w-full bg-input border border-border rounded-lg px-2.5 py-2 text-white text-[11px] focus:outline-none focus:border-primary resize-none leading-relaxed transition-colors" />
                </div>

                {/* Transition + Duration */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Transition</label>
                    <select value={transitionStyle} onChange={e => setTransitionStyle(e.target.value as any)}
                      className="w-full bg-input border border-border rounded-lg px-2.5 py-2 text-white text-[11px] focus:outline-none focus:border-primary transition-colors cursor-pointer">
                      <option value="fade">Fade</option>
                      <option value="slide">Slide Pan</option>
                      <option value="none">Cut</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                      Duration <span className="text-violet-400 font-mono">{sceneDuration.toFixed(1)}s</span>
                    </label>
                    <input type="range" min={1} max={10} step={0.5} value={sceneDuration} onChange={e => setSceneDuration(parseFloat(e.target.value))}
                      className="w-full cursor-pointer mt-2" />
                  </div>
                </div>

                {/* Scene action buttons */}
                <div className="flex gap-2">
                  <button onClick={handleSaveSceneChanges} disabled={savingScene}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-secondary hover:bg-zinc-800 border border-border text-white px-3 py-2.5 rounded-xl text-[11px] font-semibold transition-all disabled:opacity-50">
                    {savingScene ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5 text-zinc-400" />}
                    Save
                  </button>
                  <button onClick={handleRegenerateScene} disabled={regeneratingScene || ["PENDING","EXTRACTING"].includes(project.status)}
                    className="flex-1 flex items-center justify-center gap-1.5 bg-secondary hover:bg-zinc-800 border border-border text-white px-3 py-2.5 rounded-xl text-[11px] font-semibold transition-all disabled:opacity-50"
                    title="Regenerate scene media">
                    {regeneratingScene ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 text-violet-400" />}
                    Regen
                  </button>
                </div>
              </>
            ) : (
              <p className="text-[11px] text-muted-foreground italic">Select a scene card to inspect.</p>
            )}
          </div>

          {/* bottom action */}
          <div className="p-4 border-t border-border/50">
            {project.status === "REVIEW_PENDING" && project.current_stage === "storyboard" ? (
              <button onClick={handleApprove} disabled={actionLoading}
                className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-violet-600 text-white font-bold py-3 rounded-xl text-xs uppercase tracking-wider shadow-lg shadow-primary/20 transition-all hover:-translate-y-0.5 disabled:opacity-50">
                {actionLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Rendering...</> : <><CheckCircle className="w-4 h-4" /> Compile Video</>}
              </button>
            ) : project.status === "COMPLETED" ? (
              <button onClick={handleRetryStoryboard}
                className="w-full flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-700 border border-border text-zinc-300 font-semibold py-3 rounded-xl text-xs uppercase tracking-wider transition-all">
                <RefreshCw className="w-4 h-4" /> Recompile
              </button>
            ) : project.status === "FAILED" ? (
              <button onClick={handleRetryStoryboard} disabled={retrying}
                className="w-full flex items-center justify-center gap-2 bg-rose-600/90 hover:bg-rose-600 text-white font-bold py-3 rounded-xl text-xs uppercase tracking-wider transition-all disabled:opacity-50">
                {retrying ? <><Loader2 className="w-4 h-4 animate-spin" /> Retrying...</> : <><RefreshCw className="w-4 h-4" /> Retry Pipeline</>}
              </button>
            ) : (
              <div className="bg-zinc-950/60 border border-border/60 rounded-xl p-3 text-[10px] text-zinc-500 flex items-start gap-2 leading-relaxed">
                <Zap className="w-3.5 h-3.5 text-violet-500 shrink-0 mt-0.5" />
                Pipeline orchestrates Ollama LLM · ComfyUI images · Piper TTS · FFmpeg composition — all locally.
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* ════════════════ IMAGE LIGHTBOX MODAL ════════════════ */}
      <AnimatePresence>
        {previewImage && (
          <motion.div
            key="lightbox"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/92 backdrop-blur-md flex items-center justify-center p-6"
            onClick={() => setPreviewImage(null)}
          >
            <motion.img
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ duration: 0.25 }}
              src={previewImage}
              alt="Preview"
              className="max-w-[90vw] max-h-[90vh] rounded-2xl shadow-2xl object-contain"
              onClick={e => e.stopPropagation()}
            />
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute top-5 right-5 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center text-white transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
