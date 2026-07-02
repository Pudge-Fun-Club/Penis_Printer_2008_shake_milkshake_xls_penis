async function fail(res: Response): Promise<never> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail ?? detail;
  } catch {
    /* ignore */
  }
  throw new Error(detail);
}

export async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: "same-origin", ...opts });
  if (!res.ok) await fail(res);
  return res.json() as Promise<T>;
}

/** Like {@link req} for binary endpoints (previews, originals, exports). */
export async function reqBlob(url: string, opts?: RequestInit): Promise<Blob> {
  const res = await fetch(url, { credentials: "same-origin", ...opts });
  if (!res.ok) await fail(res);
  return res.blob();
}

export async function reqArrayBuffer(url: string, opts?: RequestInit): Promise<ArrayBuffer> {
  const res = await fetch(url, { credentials: "same-origin", ...opts });
  if (!res.ok) await fail(res);
  return res.arrayBuffer();
}
