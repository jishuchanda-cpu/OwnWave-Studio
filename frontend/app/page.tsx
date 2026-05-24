"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { api, Project } from "@/lib/api";
import {
  Plus, Video, Trash2, Calendar, FileText, Globe, ArrowRight,
  Loader2, Play, RefreshCw, Clapperboard, Cpu, CheckCircle2,
  AlertCircle, XCircle, Activity, Clock, Film, Sparkles, X
} from "lucide-react";

/* ─── helpers ─────────────────────────────────────────────── */
function statusMeta(s: string) {
  switch (s) {
    case "COMPLETED":     return { label: "Completed",  dot: "bg-emerald-400", badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25", icon: CheckCircle2 };
    case "FAILED":        return { label: "Failed",     dot: "bg-rose-400",    badge: "bg-rose-500/10 text-rose-400 border-rose-500/25",       icon: XCircle };
    case "CANCELLED":     return { label: "Cancelled",  dot: "bg-zinc-500",    badge: "bg-zinc-800/60 text-zinc-400 border-zinc-700",           icon: XCircle };
    case "REVIEW_PENDING":return { label: "Reviewing",  dot: "bg-amber-400 animate-pulse", badge: "bg-amber-500/10 text-amber-400 border-amber-500/25", icon: Clock };
    case "PENDING":       return { label: "Pending",    dot: "bg-zinc-600",    badge: "bg-zinc-800/40 text-zinc-500 border-zinc-700",           icon: Clock };
    default:              return { label: s.replace(/_/g," "), dot: "bg-violet-400 animate-pulse", badge: "bg-violet-500/10 text-violet-400 border-violet-500/25", icon: Activity };
  }
}

function sourceIcon(t: string) {
  if (t === "URL") return <Globe className="w-3.5 h-3.5 text-sky-400" />;
  return <FileText className="w-3.5 h-3.5 text-violet-400" />;
}

/* card top-border color by status */
function cardAccent(s: string) {
  if (s === "COMPLETED")      return "from-emerald-500 to-teal-500";
  if (s === "FAILED")         return "from-rose-500 to-pink-600";
  if (s === "CANCELLED")      return "from-zinc-600 to-zinc-700";
  if (s === "REVIEW_PENDING") return "from-amber-400 to-orange-500";
  return "from-violet-600 to-indigo-500";
}

/* skeleton card */
function SkeletonCard() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 h-56 flex flex-col gap-3 overflow-hidden relative">
      <div className="absolute top-0 left-0 right-0 h-[2px] shimmer" />
      <div className="skeleton h-4 w-3/5" />
      <div className="skeleton h-3 w-1/3" />
      <div className="flex-1" />
      <div className="skeleton h-3 w-1/2" />
    </div>
  );
}

/* ─── main component ─────────────────────────────────────── */
export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // form
  const [title,          setTitle]          = useState("");
  const [sourceType,     setSourceType]     = useState<"TEXT"|"PDF"|"URL">("TEXT");
  const [sourceInput,    setSourceInput]    = useState("");
  const [aspectRatio,    setAspectRatio]    = useState<"9:16"|"16:9"|"1:1">("9:16");
  const [durationTarget, setDurationTarget] = useState<string>("30s");
  const [voiceOption,    setVoiceOption]    = useState<string>("english_female");
  const [submitting,     setSubmitting]     = useState(false);

  useEffect(() => { loadProjects(); }, []);

  async function loadProjects() {
    setLoading(true);
    try { setProjects(await api.getProjects()); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!title || !sourceInput) return;
    setSubmitting(true);
    try {
      const p = await api.createProject({ 
        title, 
        source_type: sourceType, 
        source_input: sourceInput, 
        aspect_ratio: aspectRatio, 
        duration_target: durationTarget,
        voice_option: voiceOption
      });
      setIsModalOpen(false);
      setTitle(""); setSourceInput(""); setDurationTarget("30s"); setVoiceOption("english_female");
      await api.generateStoryboard(p.id);
      loadProjects();
    } catch (err) {
      console.error(err);
      alert("Failed to start content creation pipeline.");
    } finally { setSubmitting(false); }
  }

  async function handleDelete(id: string, e: React.MouseEvent) {
    e.preventDefault(); e.stopPropagation();
    if (!confirm("Delete this project and all its media?")) return;
    try { await api.deleteProject(id); loadProjects(); }
    catch (err) { console.error(err); }
  }

  // stats
  const stats = {
    total:     projects.length,
    active:    projects.filter(p => !["COMPLETED","FAILED","CANCELLED","PENDING"].includes(p.status)).length,
    completed: projects.filter(p => p.status === "COMPLETED").length,
    failed:    projects.filter(p => ["FAILED","CANCELLED"].includes(p.status)).length,
  };

  return (
    <div className="relative min-h-screen bg-background text-foreground overflow-hidden">

      {/* ── ambient glow ── */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden z-0">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full gradient-glow opacity-70" />
        <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full gradient-glow opacity-50" />
      </div>

      {/* ── top navbar ── */}
      <header className="sticky top-0 z-30 bg-glass border-b border-border px-6 md:px-10 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* logo mark */}
          <div className="relative w-9 h-9 rounded-xl overflow-hidden border border-violet-500/30 flex items-center justify-center bg-black/40">
            <img src="/logo.png" alt="OwnWave Studio Logo" className="w-full h-full object-cover" />
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-background animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white leading-none tracking-tight">
              OwnWave Studio
            </h1>
            <p className="text-[10px] text-muted-foreground mt-0.5 font-mono">
              local-first · zero api cost
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadProjects}
            className="p-2 rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800 border border-transparent hover:border-border transition-all"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-primary hover:bg-violet-600 text-white font-semibold px-4 py-2.5 rounded-lg text-sm shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40 hover:-translate-y-0.5"
          >
            <Plus className="w-4 h-4" />
            <span>New Project</span>
          </button>
        </div>
      </header>

      {/* ── page content ── */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 md:px-10 py-10">

        {/* hero */}
        <div className="mb-10">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y:  0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight">
              <span className="text-white">Production</span>{" "}
              <span className="gradient-text">Workspace</span>
            </h2>
            <p className="text-muted-foreground mt-2 text-base max-w-xl">
              Fully automated video pipeline — Ollama LLM · ComfyUI images · Piper TTS · FFmpeg render.
            </p>
          </motion.div>

          {/* stats strip */}
          {!loading && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15, duration: 0.4 }}
              className="grid grid-cols-4 gap-3 mt-7"
            >
              {[
                { label: "Total Projects",    val: stats.total,     icon: Film,         color: "text-zinc-300" },
                { label: "Active Pipelines",  val: stats.active,    icon: Activity,     color: "text-violet-400" },
                { label: "Completed Videos",  val: stats.completed, icon: CheckCircle2, color: "text-emerald-400" },
                { label: "Failed / Cancelled",val: stats.failed,    icon: AlertCircle,  color: "text-rose-400" },
              ].map((s) => (
                <div key={s.label} className="bg-card border border-border rounded-xl px-4 py-3.5 flex items-center gap-3">
                  <s.icon className={`w-5 h-5 shrink-0 ${s.color}`} />
                  <div>
                    <div className={`text-xl font-bold leading-none ${s.color}`}>{s.val}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">{s.label}</div>
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </div>

        {/* ── grid header ── */}
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            Your Projects
            {!loading && <span className="text-xs font-normal text-muted-foreground">({projects.length})</span>}
          </h3>
        </div>

        {/* ── states ── */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1,2,3,4,5,6].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : projects.length === 0 ? (
          /* empty state */
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.45 }}
            className="flex flex-col items-center justify-center py-28 gap-6"
          >
            <div className="relative">
              <div className="w-24 h-24 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center animate-float">
                <Video className="w-12 h-12 text-primary/70" />
              </div>
              <Sparkles className="absolute -top-2 -right-2 w-5 h-5 text-amber-400 animate-pulse" />
            </div>
            <div className="text-center">
              <h3 className="text-xl font-bold text-white mb-2">No projects yet</h3>
              <p className="text-muted-foreground text-sm max-w-sm mx-auto leading-relaxed">
                Create your first AI video project. Paste a topic, URL, or text and let the pipeline handle everything.
              </p>
            </div>
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 bg-primary/10 hover:bg-primary/20 border border-primary/30 hover:border-primary/50 text-primary font-semibold px-6 py-3 rounded-xl transition-all text-sm"
            >
              <Plus className="w-4 h-4" /> Start Creating
            </button>
          </motion.div>
        ) : (
          /* project grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <AnimatePresence>
              {projects.map((project, i) => {
                const meta = statusMeta(project.status);
                const accent = cardAccent(project.status);
                const isActive = !["COMPLETED","FAILED","CANCELLED","PENDING","REVIEW_PENDING"].includes(project.status);
                const StatusIcon = meta.icon;
                return (
                  <motion.div
                    key={project.id}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y:  0 }}
                    exit={{ opacity: 0, scale: 0.96 }}
                    transition={{ delay: i * 0.05, duration: 0.35 }}
                  >
                    <Link href={`/project/${project.id}`}>
                      <div className="group relative bg-card border border-border rounded-xl overflow-hidden h-56 flex flex-col cursor-pointer card-lift hover:border-violet-500/40">

                        {/* gradient top border */}
                        <div className={`absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r ${accent} opacity-80 group-hover:opacity-100 transition-opacity`} />

                        {/* inner */}
                        <div className="p-5 flex flex-col flex-1">
                          <div className="flex justify-between items-start gap-2 mb-3">
                            <h4 className="font-semibold text-white text-base leading-tight line-clamp-2 group-hover:text-violet-300 transition-colors">
                              {project.title}
                            </h4>
                            <span className={`shrink-0 flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wider ${meta.badge}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                              {meta.label}
                            </span>
                          </div>

                          {/* meta badges */}
                          <div className="flex items-center gap-2 mb-auto">
                            <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                              {sourceIcon(project.source_type)}
                              {project.source_type}
                            </span>
                            <span className="text-[10px] font-mono bg-zinc-900 text-zinc-400 px-2 py-0.5 rounded border border-border">{project.aspect_ratio}</span>
                            <span className="text-[10px] font-semibold bg-violet-900/20 text-violet-300 border border-violet-800/30 px-2 py-0.5 rounded">{project.duration_target}</span>
                          </div>

                          {/* active animation */}
                          {isActive && (
                            <div className="flex items-center gap-2 mt-3 mb-1">
                              <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
                                <div className="h-full progress-gradient rounded-full w-3/5" />
                              </div>
                              <span className="text-[9px] font-mono text-violet-400 uppercase tracking-wider flex items-center gap-1">
                                <Cpu className="w-2.5 h-2.5" />
                                Processing
                              </span>
                            </div>
                          )}

                          {/* footer */}
                          <div className="flex justify-between items-center pt-3 border-t border-border/40 mt-2">
                            <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                              <Calendar className="w-3 h-3" />
                              {new Date(project.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={(e) => handleDelete(project.id, e)}
                                className="p-1.5 text-zinc-600 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all"
                                title="Delete"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                              <span className="text-xs text-zinc-500 group-hover:text-violet-400 transition-colors flex items-center gap-0.5 font-medium">
                                Open <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* ── premium footer ── */}
      <footer className="relative z-10 border-t border-border/30 bg-black/40 backdrop-blur-md mt-16 px-6 md:px-10 py-12">
        <div className="max-w-7xl mx-auto flex flex-col gap-10">
          
          {/* Top Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
            
            {/* Column 1: Branding & Vision */}
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <div className="relative w-8 h-8 rounded-xl overflow-hidden border border-violet-500/30 flex items-center justify-center bg-black/40">
                  <img src="/logo.png" alt="OwnWave Studio Logo" className="w-full h-full object-cover" />
                </div>
                <span className="text-base font-bold text-white tracking-wider">OwnWave Studio</span>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed max-w-sm">
                Empowering independent creators to realize their imagination. 
                Our local-first AI production workstation puts cinematic storytelling 
                and motion composition directly into your hands.
              </p>
            </div>
            
            {/* Column 2: Emotional Creator Message */}
            <div className="flex flex-col gap-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Creator Freedom</span>
              <p className="text-xs italic text-zinc-500 leading-relaxed max-w-xs">
                "Storytelling is the currency of human connection. OwnWave Studio is built to ensure your creative wave flows freely, powered by local computation, unbound by subscription limits."
              </p>
            </div>
            
            {/* Column 3: Tech stack / features */}
            <div className="flex flex-col gap-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">Local Workshop Specs</span>
              <ul className="text-xs text-zinc-400 space-y-1.5 font-mono">
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-violet-400" />
                  Ollama Large Language Models
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-violet-400" />
                  ComfyUI / Pollinations Engines
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-violet-400" />
                  Piper TTS & FFmpeg Pipeline
                </li>
              </ul>
            </div>
          </div>
          
          {/* Divider */}
          <div className="h-[1px] bg-gradient-to-r from-transparent via-border/50 to-transparent" />
          
          {/* Bottom copyright section with ID */}
          <div id="n3q7vm" className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-zinc-500 border-t border-border/10 pt-4">
            <span className="text-zinc-600">
              &copy; {new Date().getFullYear()} OwnWave Studio. All rights reserved.
            </span>
            <span className="flex items-center gap-1.5 text-zinc-500">
              Created with <span className="text-rose-500 animate-pulse">❤️</span> by Jishu
            </span>
          </div>

        </div>
      </footer>

      {/* ── Create Modal ── */}
      <AnimatePresence>
        {isModalOpen && (
          <motion.div
            key="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={() => setIsModalOpen(false)}
          >
            <motion.div
              key="modal-card"
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 8 }}
              transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
              className="bg-glass-strong border border-border w-full max-w-xl rounded-2xl p-7 shadow-2xl relative"
              onClick={(e) => e.stopPropagation()}
            >
              {/* top accent line */}
              <div className="absolute top-0 left-0 right-0 h-[1.5px] rounded-t-2xl bg-gradient-to-r from-transparent via-primary/70 to-transparent" />

              <div className="flex items-start justify-between mb-5">
                <div>
                  <h3 className="text-xl font-bold text-white">Create New Project</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    The AI pipeline will handle research, scripting, storyboarding and rendering.
                  </p>
                </div>
                <button onClick={() => setIsModalOpen(false)} className="p-1.5 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-500 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreate} className="space-y-4">
                {/* title */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1.5 uppercase tracking-wide">Project Title</label>
                  <input
                    type="text" required
                    placeholder="e.g. History of AI, Shivaji Maharaj story..."
                    value={title} onChange={e => setTitle(e.target.value)}
                    className="w-full bg-input border border-border rounded-lg px-3.5 py-2.5 text-white text-sm focus:outline-none focus:border-primary transition-colors placeholder:text-zinc-600"
                  />
                </div>

                {/* source type */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1.5 uppercase tracking-wide">Source Type</label>
                  <div className="grid grid-cols-3 gap-2">
                    {(["TEXT","URL","PDF"] as const).map(t => (
                      <button key={t} type="button" onClick={() => setSourceType(t)}
                        className={`py-2.5 rounded-lg border text-xs font-semibold transition-all flex items-center justify-center gap-1.5 ${
                          sourceType === t
                            ? "bg-primary/15 border-primary/60 text-primary"
                            : "bg-input border-border text-zinc-400 hover:bg-zinc-800/70"
                        }`}
                      >
                        {sourceIcon(t)} {t}
                      </button>
                    ))}
                  </div>
                </div>

                {/* source input */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1.5 uppercase tracking-wide">
                    {sourceType === "TEXT" ? "Topic / Script / Description" : sourceType === "URL" ? "Article URL" : "PDF Filepath"}
                  </label>
                  <textarea required rows={4}
                    placeholder={sourceType === "TEXT" ? "Paste your topic or script content here..." : sourceType === "URL" ? "https://example.com/article" : "C:/path/to/doc.pdf"}
                    value={sourceInput} onChange={e => setSourceInput(e.target.value)}
                    className="w-full bg-input border border-border rounded-lg px-3.5 py-2.5 text-white text-sm focus:outline-none focus:border-primary transition-colors resize-none placeholder:text-zinc-600"
                  />
                </div>

                {/* ratio + duration */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1.5 uppercase tracking-wide">Aspect Ratio</label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(["9:16","16:9","1:1"] as const).map(r => (
                        <button key={r} type="button" onClick={() => setAspectRatio(r)}
                          className={`py-2 rounded-lg border text-[10px] font-mono font-bold transition-all ${
                            aspectRatio === r ? "bg-primary/15 border-primary/60 text-primary" : "bg-input border-border text-zinc-400 hover:bg-zinc-800"
                          }`}
                        >{r}</button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1.5 uppercase tracking-wide">Duration</label>
                    <div className="grid grid-cols-2 gap-1.5">
                      {[{v:"30s",l:"30s"},{v:"1m",l:"1 min"},{v:"1m30s",l:"1:30"},{v:"3m",l:"3 min"}].map(d => (
                        <button key={d.v} type="button" onClick={() => setDurationTarget(d.v)}
                          className={`py-2 rounded-lg border text-[10px] font-semibold transition-all ${
                            durationTarget === d.v ? "bg-primary/15 border-primary/60 text-primary" : "bg-input border-border text-zinc-400 hover:bg-zinc-800"
                          }`}
                        >{d.l}</button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* voice selection */}
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-2.5 uppercase tracking-wide">
                    Narration Voice
                  </label>
                  <div className="space-y-2">
                    {[
                      {
                        id: "english_female",
                        label: "English Female (Default)",
                        description: "English • Female • Warm narrator fallback tone",
                      },
                      {
                        id: "english_male",
                        label: "English Male Narrator",
                        description: "English • Male • Cinematic documentary tone",
                      },
                      {
                        id: "hindi_male",
                        label: "Hindi-Hinglish Male Narrator",
                        description: "Hinglish • Male • Conversational YouTube storyteller",
                      },
                    ].map((v) => (
                      <button
                        key={v.id}
                        type="button"
                        onClick={() => setVoiceOption(v.id)}
                        className={`w-full p-3 rounded-xl border text-left transition-all flex items-center justify-between ${
                          voiceOption === v.id
                            ? "bg-primary/15 border-primary/60 text-white shadow-md shadow-primary/5"
                            : "bg-input border-border text-zinc-400 hover:bg-zinc-800/60 hover:border-zinc-700"
                        }`}
                      >
                        <div className="flex flex-col gap-0.5">
                          <span className={`text-xs font-semibold ${voiceOption === v.id ? "text-white" : "text-zinc-300"}`}>
                            {v.label}
                          </span>
                          <span className="text-[10px] text-zinc-500">
                            {v.description}
                          </span>
                        </div>
                        <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                          voiceOption === v.id ? "border-primary bg-primary" : "border-zinc-600"
                        }`}>
                          {voiceOption === v.id && (
                            <div className="w-1.5 h-1.5 rounded-full bg-white" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* submit */}
                <div className="flex gap-3 pt-2 border-t border-border/50">
                  <button type="button" onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-2.5 rounded-lg border border-border bg-secondary text-zinc-300 text-sm font-semibold hover:bg-zinc-800 transition-colors">
                    Cancel
                  </button>
                  <button type="submit" disabled={submitting}
                    className="flex-1 py-2.5 rounded-lg bg-primary hover:bg-violet-600 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-primary/25 transition-all disabled:opacity-50">
                    {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : <><Play className="w-3.5 h-3.5 fill-white" /> Launch Pipeline</>}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
