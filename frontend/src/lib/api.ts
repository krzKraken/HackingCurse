const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });

  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export type ConceptSummary = { slug: string; name: string };

export type LessonContent = {
  concepto: string | null;
  como_funciona: string | null;
  por_que_importa: string | null;
  visualizacion: string | null;
  ejemplo: string | null;
  comandos: string | null;
  errores_frecuentes: string | null;
  regla_mental: string | null;
  perspectiva_ofensiva: string | null;
  perspectiva_defensiva: string | null;
};

export type ConceptDetail = {
  slug: string;
  name: string;
  lesson: LessonContent | null;
  relationships: {
    prerequisites: ConceptSummary[];
    related: ConceptSummary[];
    continues_with: ConceptSummary[];
  };
};

export type DomainSummary = {
  slug: string;
  name: string;
  topics: { slug: string; name: string; concepts: ConceptSummary[] }[];
};

export type Note = {
  id: string;
  title: string;
  body_markdown: string;
  is_global: boolean;
  linked_concept_slug: string | null;
  updated_at: string;
};

export type ReviewItemPrompt = {
  item_id: string;
  concept_slug: string;
  type: "multiple_choice" | "true_false" | "free_explanation";
  prompt_markdown: string;
  options: string[] | null;
};

export type CreateReviewSessionParams = {
  mode: string;
  domain_slug?: string;
  topic_slug?: string;
  concept_slugs?: string[];
  budget_count?: number;
  budget_minutes?: number;
};

export type AnswerResult = {
  outcome?: "correct" | "partial" | "incorrect";
  correct_option_index?: number;
  correct_bool?: boolean;
  evaluation_criteria?: string;
  expected_answer?: string;
};

export type DashboardSummary = {
  global_mastery: number;
  domains: {
    slug: string;
    name: string;
    mastery_percent: number;
    studied_count: number;
    total_count: number;
  }[];
  reviews_due_count: number;
  weak_concepts: { slug: string; name: string; mastery_score: number }[];
  overdue_concepts: { slug: string; name: string; next_due_at: string }[];
  recent_activity: { concept_slug: string; concept_name: string; outcome: string; answered_at: string }[];
};

export const api = {
  login: (username: string, password: string) =>
    request<{ mfa_required: boolean }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  verifyMfa: (code: string) =>
    request<{ id: string; username: string }>("/auth/mfa/verify", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),
  me: () => request<{ id: string; username: string }>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  listDomains: () => request<DomainSummary[]>("/content/domains"),
  getConcept: (slug: string) => request<ConceptDetail>(`/content/concepts/${slug}`),
  listNotes: () => request<Note[]>("/notes"),
  createNote: (title: string, body_markdown: string) =>
    request<Note>("/notes", { method: "POST", body: JSON.stringify({ title, body_markdown }) }),
  getNote: (id: string) => request<Note>(`/notes/${id}`),
  updateNote: (id: string, title: string, body_markdown: string) =>
    request<Note>(`/notes/${id}`, { method: "PUT", body: JSON.stringify({ title, body_markdown }) }),
  deleteNote: (id: string) => request<void>(`/notes/${id}`, { method: "DELETE" }),
  getNoteByConcept: (slug: string) => request<Note>(`/notes/by-concept/${slug}`),
  putNoteByConcept: (slug: string, title: string, body_markdown: string) =>
    request<Note>(`/notes/by-concept/${slug}`, {
      method: "PUT",
      body: JSON.stringify({ title, body_markdown }),
    }),
  createReviewSession: (params: CreateReviewSessionParams) =>
    request<{ session_id: string; items: ReviewItemPrompt[] }>("/reviews/sessions", {
      method: "POST",
      body: JSON.stringify(params),
    }),
  answerReviewItem: (itemId: string, user_response: string, confidence_declared?: string) =>
    request<AnswerResult>(`/reviews/items/${itemId}/answer`, {
      method: "POST",
      body: JSON.stringify({ user_response, confidence_declared }),
    }),
  selfRateReviewItem: (itemId: string, outcome: string) =>
    request<{ outcome: string }>(`/reviews/items/${itemId}/self-rate`, {
      method: "POST",
      body: JSON.stringify({ outcome }),
    }),
  getDashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),
};
