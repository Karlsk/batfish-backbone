import openapiFetch from "openapi-fetch";
import type { paths, components } from "./schema";
import { getSession, setSession, sessionGeneration } from "../app/session";
const messages: Record<string, string> = {
  UNAUTHORIZED: "会话已过期，请重新登录。",
  FORBIDDEN: "当前账号没有操作权限。",
  VALIDATION_ERROR: "请检查填写的参数。",
  NOT_FOUND: "资源不存在或已被移除。",
  CONFLICT: "资源状态已变化，请刷新后重试。",
  NOT_READY: "服务尚未就绪，请稍后重试。",
  RATE_LIMITED: "操作过于频繁，请稍后重试。",
  ENGINE_STATE_UNKNOWN: "引擎状态待确认，请联系管理员。",
  ENGINE_QUERY_FAILED: "分析执行失败，请检查参数与快照诊断。",
  UPLOAD_TOO_LARGE: "文件超过上传限制。",
};
export class ApiError extends Error {
  constructor(
    public code: string,
    public requestId = "",
    public fieldErrors: components["schemas"]["FieldError"][] = [],
  ) {
    super(messages[code] ?? "服务暂时不可用，请稍后重试。");
  }
}
export function createClient(fetcher?: typeof fetch) {
  const generations = new WeakMap<Request, number>();
  const client = openapiFetch<paths>({
    baseUrl: window.location.origin,
    credentials: "same-origin",
    fetch: fetcher,
  });
  client.use({
    onRequest({ request }) {
      if (new URL(request.url).origin !== window.location.origin)
        throw new Error("Cross-origin API requests are forbidden");
      generations.set(request, sessionGeneration());
      if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
        const token = getSession()?.csrf_token;
        if (token) request.headers.set("X-CSRF-Token", token);
      }
      return request;
    },
    onResponse({ request, response }) {
      if (
        response.status === 401 &&
        generations.get(request) === sessionGeneration()
      )
        setSession(null);
      return response;
    },
  });
  return client;
}
export const api = createClient();
export async function unwrap<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result;
  try {
    result = await request;
  } catch {
    throw new ApiError("NETWORK_ERROR");
  }
  if (result.error !== undefined || !result.response.ok) {
    const body = result.error;
    const detail =
      typeof body === "object" && body !== null && "error" in body
        ? body.error
        : null;
    const safe =
      typeof detail === "object" && detail !== null
        ? (detail as Partial<components["schemas"]["ErrorDetail"]>)
        : {};
    throw new ApiError(
      typeof safe.code === "string" ? safe.code : "INTERNAL_ERROR",
      typeof safe.request_id === "string" ? safe.request_id : "",
      Array.isArray(safe.field_errors) ? safe.field_errors : [],
    );
  }
  return result.data as T;
}
