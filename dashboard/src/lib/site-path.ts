const rawBasePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const basePath = rawBasePath.replace(/\/$/, "");

export function sitePath(path: string) {
  if (!basePath || !path.startsWith("/")) return path;
  return `${basePath}${path}`;
}
