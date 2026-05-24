export const API_BASE = "http://127.0.0.1:8000/api/v1";
export const MEDIA_BASE = "http://127.0.0.1:8000/media";
export const WS_BASE = "ws://127.0.0.1:8000/api/v1/ws";

export interface Scene {
  id: string;
  project_id: string;
  scene_index: number;
  narration_text: string;
  image_prompt: string;
  subtitle_text: string;
  image_path: string | null;
  image_path_1: string | null;
  image_path_2: string | null;
  selected_image_index: number;
  transition_style: "fade" | "slide" | "none" | null;
  scene_duration: number | null;
  audio_path: string | null;
  audio_duration: number | null;
  status: "PENDING" | "GENERATING" | "COMPLETED" | "FAILED";
}

export interface Project {
  id: string;
  title: string;
  status: "PENDING" | "EXTRACTING" | "RESEARCHING" | "STRATEGIZING" | "WRITING" | "STORYBOARDING" | "REVIEW_PENDING" | "GENERATING" | "RENDERING" | "COMPLETED" | "FAILED" | "CANCELLED";
  source_type: "TEXT" | "PDF" | "URL";
  raw_content: string | null;
  summary: string | null;
  viral_hooks: string | null; // JSON String
  viral_cta: string | null;
  script: string | null;
  aspect_ratio: "9:16" | "16:9" | "1:1";
  duration_target: "30s" | "1m" | "1m30s" | "3m";
  voice_option: string | null;
  current_stage: "ingest" | "research" | "viral_strategy" | "script" | "storyboard" | "completed";
  stage_approved: boolean;
  stage_metadata: string | null; // JSON String
  created_at: string;
  updated_at: string;
  scenes: Scene[];
}

export const api = {
  async getProjects(): Promise<Project[]> {
    const res = await fetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error("Failed to fetch projects");
    return res.json();
  },

  async getProject(id: string): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    if (!res.ok) throw new Error("Failed to fetch project details");
    return res.json();
  },

  async createProject(data: {
    title: string;
    source_type: string;
    source_input: string;
    aspect_ratio: string;
    duration_target: string;
    voice_option?: string;
  }): Promise<Project> {
    const res = await fetch(`${API_BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to create project");
    return res.json();
  },

  async generateStoryboard(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/generate-storyboard`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to trigger storyboard generation");
  },

  async updateScenes(
    id: string,
    scenes: {
      id: string;
      narration_text: string;
      image_prompt: string;
      subtitle_text: string;
      image_path_1?: string | null;
      image_path_2?: string | null;
      selected_image_index?: number;
      transition_style?: string | null;
      scene_duration?: number | null;
    }[]
  ): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/scenes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenes }),
    });
    if (!res.ok) throw new Error("Failed to save storyboard scenes");
  },

  async approveStage(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/approve-stage`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to approve stage");
  },

  async rerunStage(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/rerun-stage`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to rerun stage");
  },

  async editStage(
    id: string,
    data: {
      content_text?: string | null;
      prompt_override?: string | null;
      tone_override?: string | null;
    }
  ): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/edit-stage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to submit stage edits");
  },

  async cancelProject(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/cancel`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to cancel project pipeline");
  },

  async approveAndGenerate(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}/approve`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to approve and start render");
  },

  async regenerateScene(projectId: string, sceneId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/regenerate-scene/${sceneId}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to trigger scene regeneration");
  },

  async deleteProject(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete project");
  },

  connectWS(
    projectId: string,
    onMessage: (data: { project_id: string; status: string; progress: number; message: string; type?: string; stage?: string }) => void,
    onError?: (err: Event) => void
  ): WebSocket {
    const ws = new WebSocket(`${WS_BASE}/${projectId}`);
    
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        onMessage(payload);
      } catch (e) {
        console.error("Error parsing WS packet:", e);
      }
    };
    
    if (onError) {
      ws.onerror = (err) => {
        if (ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED) {
          return;
        }
        onError(err);
      };
    }
    
    ws.onclose = () => {
      console.log(`WS connection closed for project: ${projectId}`);
    };

    return ws;
  }
};
