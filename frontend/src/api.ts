export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    if (response.status === 502) detail = '后端服务不可用（502）：请检查 backend 容器是否 healthy，并查看 docker compose logs backend';
    try { detail = (await response.json()).detail ?? detail; } catch { /* keep status */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const jsonInit = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: {'Content-Type': 'application/json'},
  body: body === undefined ? undefined : JSON.stringify(body),
});

