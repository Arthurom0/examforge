export type Kind = "lecture" | "exam" | "booklet";
export type ProblemType = "mcq" | "numerical" | "derivation" | "conceptual";
export type Difficulty = "easy" | "medium" | "exam";
export type Lang = "fr" | "en";
export type Result = "correct" | "partial" | "wrong";

export interface Chapter {
  id: number;
  course_id: number;
  name: string;
  position: number;
  documents?: number;
  exercises?: number;
}
export interface Course {
  id: number;
  name: string;
  chapters: Chapter[];
  documents: number;
  exercises: number;
  problems: number;
  attempts: number;
}
export interface Doc {
  id: number;
  course_id: number;
  chapter_id: number | null;
  kind: Kind;
  filename: string;
  page_count: number;
  ocr_used: boolean;
  ocr_pages: number;
  status: "pending" | "ready" | "error";
  error: string | null;
  char_count: number;
  created_at: string;
}
export interface SubQuestion {
  label: string;
  text: string;
}
export interface Exercise {
  id: number;
  document_id: number;
  course_id: number;
  chapter_id: number | null;
  label: string;
  position: number;
  raw_text: string;
  statement: string;
  given_data: string;
  sub_questions: SubQuestion[];
  correction: string | null;
  correction_source: "none" | "booklet" | "ai";
  page_start: number;
  page_end: number;
  topic_tags: string[];
  reviewed: boolean;
  attempts?: number;
  last_result?: Result | null;
}
export interface GivenItem {
  symbol: string;
  value: string;
  unit: string;
  description: string;
}
export interface Problem {
  id: number;
  set_id: number;
  type: ProblemType;
  difficulty: Difficulty;
  language: Lang;
  title: string;
  statement: string;
  given_data: GivenItem[];
  choices: { label: string; text: string }[];
  answer: string;
  solution_steps: { title: string; content: string }[];
  topic_tags: string[];
  self_check: string;
  last_result: Result | null;
}
export interface ProblemSet {
  id: number;
  course_id: number;
  chapter_id: number | null;
  mode: "standard" | "weak_spot" | "variant";
  title: string;
  params: Record<string, unknown>;
  created_at: string;
  course_name?: string;
  chapter_name?: string | null;
  source_exercise?: Exercise | null;
  problems?: Problem[];
  problem_count?: number;
  attempted?: number;
}
export interface Agg {
  attempts: number;
  success_rate: number | null;
  correct: number;
  partial: number;
  wrong: number;
}
export interface CourseStats extends Agg {
  course_id: number;
  name: string;
  generated: Agg;
  booklet: Agg;
  chapters: (Agg & { chapter_id: number | null; name: string; generated: Agg; booklet: Agg })[];
}
export interface Timeline {
  periods: string[];
  series: { key: string; name: string; points: { period: string; attempts: number; success_rate: number }[] }[];
}
export interface TopicStat {
  topic: string;
  attempts: number;
  success_rate: number;
  smoothed: number;
}
export interface AppSettings {
  api_key_configured: boolean;
  api_key_hint: string;
  model: string;
  effort: "low" | "medium" | "high" | "xhigh" | "max";
  env_file: string;
  data_dir: string;
  ocr_available: boolean;
  tesseract_path: string | null;
}

/** Exposed by the Electron preload script; undefined in a normal browser. */
export interface DesktopBridge {
  savePDF: (suggestedName: string) => Promise<{ saved: boolean; path?: string }>;
  openDataFolder: () => Promise<void>;
  version: string;
}
declare global {
  interface Window {
    examforge?: DesktopBridge;
  }
}
export const desktop = (): DesktopBridge | undefined => window.examforge;

export interface Health {
  ok: boolean;
  api_key_configured: boolean;
  model: string;
  ocr_available: boolean;
  ocr_langs: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const qs = (params: Record<string, string | number | null | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<Health>("/api/health"),
  settings: () => request<AppSettings>("/api/settings"),
  saveSettings: (body: { api_key?: string; model?: string; effort?: string }) =>
    request<AppSettings>("/api/settings", json("PUT", body)),

  courses: () => request<Course[]>("/api/courses"),
  createCourse: (name: string) => request<Course>("/api/courses", json("POST", { name })),
  renameCourse: (id: number, name: string) => request<Course>(`/api/courses/${id}`, json("PATCH", { name })),
  deleteCourse: (id: number) => request(`/api/courses/${id}`, json("DELETE")),
  createChapter: (courseId: number, name: string) =>
    request<Chapter>(`/api/courses/${courseId}/chapters`, json("POST", { name })),
  updateChapter: (id: number, name: string, position?: number) =>
    request<Chapter>(`/api/courses/chapters/${id}`, json("PATCH", { name, position })),
  deleteChapter: (id: number) => request(`/api/courses/chapters/${id}`, json("DELETE")),

  documents: (courseId?: number) => request<Doc[]>(`/api/documents${qs({ course_id: courseId })}`),
  document: (id: number) => request<Doc & { chunks: number; preview: { page: number; text: string }[] }>(`/api/documents/${id}`),
  upload: (courseId: number, kind: Kind, chapterId: number | null, file: File) => {
    const fd = new FormData();
    fd.set("file", file);
    fd.set("course_id", String(courseId));
    fd.set("kind", kind);
    if (chapterId) fd.set("chapter_id", String(chapterId));
    return request<Doc>("/api/documents", { method: "POST", body: fd });
  },
  updateDocument: (id: number, body: Partial<Pick<Doc, "chapter_id" | "kind">>) =>
    request<Doc>(`/api/documents/${id}`, json("PATCH", body)),
  reprocess: (id: number) => request(`/api/documents/${id}/reprocess`, json("POST")),
  deleteDocument: (id: number) => request(`/api/documents/${id}`, json("DELETE")),
  pageImageUrl: (docId: number, page: number) => `/api/documents/${docId}/pages/${page}.png`,
  fileUrl: (docId: number) => `/api/documents/${docId}/file`,

  exercises: (p: { course_id?: number; chapter_id?: number | null; document_id?: number }) =>
    request<Exercise[]>(`/api/exercises${qs(p)}`),
  exercise: (id: number) => request<Exercise>(`/api/exercises/${id}`),
  updateExercise: (id: number, body: Partial<Exercise>) => request<Exercise>(`/api/exercises/${id}`, json("PATCH", body)),
  splitExercise: (id: number, offset: number) => request(`/api/exercises/${id}/split`, json("POST", { offset })),
  mergeNext: (id: number) => request(`/api/exercises/${id}/merge-next`, json("POST")),
  createExercise: (documentId: number, afterPosition: number) =>
    request<Exercise>("/api/exercises", json("POST", { document_id: documentId, after_position: afterPosition })),
  deleteExercise: (id: number) => request(`/api/exercises/${id}`, json("DELETE")),
  solveExercise: (id: number) => request<Exercise>(`/api/exercises/${id}/solve`, json("POST")),
  transcribeExercise: (id: number) => request<Exercise>(`/api/exercises/${id}/transcribe`, json("POST")),
  tagExercises: (body: { document_id?: number; course_id?: number; overwrite?: boolean }) =>
    request<{ tagged: number }>("/api/exercises/tag", json("POST", body)),
  variants: (id: number, count: number, kinds: string[], language?: Lang) =>
    request<ProblemSet>(`/api/exercises/${id}/variants`, json("POST", { count, kinds, language })),

  generate: (body: {
    course_id: number;
    chapter_id: number | null;
    difficulty: Difficulty;
    types: ProblemType[];
    language: Lang;
    count: number;
    weak_spot: boolean;
    focus?: string;
  }) => request<ProblemSet>("/api/generate", json("POST", body)),
  sets: (courseId?: number) => request<ProblemSet[]>(`/api/sets${qs({ course_id: courseId })}`),
  set: (id: number) => request<ProblemSet>(`/api/sets/${id}`),
  deleteSet: (id: number) => request(`/api/sets/${id}`, json("DELETE")),

  attempt: (body: { result: Result; problem_id?: number; exercise_id?: number }) =>
    request("/api/attempts", json("POST", body)),

  overview: () => request<CourseStats[]>("/api/stats/overview"),
  timeline: (p: { course_id?: number; origin?: string; granularity?: string }) =>
    request<Timeline>(`/api/stats/timeline${qs(p)}`),
  topics: (courseId: number, origin?: string) => request<TopicStat[]>(`/api/stats/topics${qs({ course_id: courseId, origin })}`),
  weakTopics: (courseId: number, chapterId?: number | null) =>
    request<TopicStat[]>(`/api/stats/weak-topics${qs({ course_id: courseId, chapter_id: chapterId })}`),
};
