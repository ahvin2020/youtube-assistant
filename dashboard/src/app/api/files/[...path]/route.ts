import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

const MIME_TYPES: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".json": "application/json",
  ".md": "text/markdown",
  ".txt": "text/plain",
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const segments = (await params).path;
  // Path: /api/files/<domain>/<slug>/<filename>
  // Maps to: workspace/output/<domain>/<slug>/<filename>
  const filePath = path.join(WORKSPACE_ROOT, "workspace", "output", ...segments);

  // Security: ensure we don't escape the workspace directory
  const resolved = path.resolve(filePath);
  if (!resolved.startsWith(path.resolve(WORKSPACE_ROOT, "workspace"))) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  try {
    const data = await fs.readFile(resolved);
    const ext = path.extname(resolved).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";
    return new NextResponse(data, {
      headers: { "Content-Type": contentType, "Cache-Control": "public, max-age=60" },
    });
  } catch {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
}
