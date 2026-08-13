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
};
