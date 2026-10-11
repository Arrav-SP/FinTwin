export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  } catch {
    throw new ApiError(0, "Cannot reach the FinTwin server. Start it with: python -m uvicorn backend.app.main:app");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : `The server answered with status ${response.status}.`;
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const apiGet = <T>(path: string) => request<T>(path);
export const apiPost = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });
