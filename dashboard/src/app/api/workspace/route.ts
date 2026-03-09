import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

// Only allow access within workspace/ and memory/ directories
function validatePath(relPath: string): string | null {
  const normalized = path.normalize(relPath);
  if (normalized.includes("..")) return null;

  const allowedPrefixes = ["workspace/", "memory/"];
  if (!allowedPrefixes.some((p) => normalized.startsWith(p))) return null;

  return path.join(WORKSPACE_ROOT, normalized);
}

export async function GET(request: NextRequest) {
  const relPath = request.nextUrl.searchParams.get("path");
  if (!relPath) {
    return NextResponse.json(
      { error: "Missing path parameter" },
      { status: 400 }
    );
  }

  const absPath = validatePath(relPath);
  if (!absPath) {
    return NextResponse.json(
      { error: "Path not allowed" },
      { status: 403 }
    );
  }

  try {
    const stat = await fs.stat(absPath);

    if (stat.isDirectory()) {
      const entries = await fs.readdir(absPath, { withFileTypes: true });
      const items = entries.map((e) => ({
        name: e.name,
        isDirectory: e.isDirectory(),
      }));
      return NextResponse.json({ type: "directory", items });
    }

    const content = await fs.readFile(absPath, "utf-8");
    return NextResponse.json({ type: "file", content });
  } catch {
    return NextResponse.json(
      { error: "File not found" },
      { status: 404 }
    );
  }
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { path: relPath, content } = body as { path: string; content: string };

  if (!relPath || content === undefined) {
    return NextResponse.json(
      { error: "Missing path or content" },
      { status: 400 }
    );
  }

  const absPath = validatePath(relPath);
  if (!absPath) {
    return NextResponse.json(
      { error: "Path not allowed" },
      { status: 403 }
    );
  }

  try {
    await fs.mkdir(path.dirname(absPath), { recursive: true });
    await fs.writeFile(absPath, content, "utf-8");
    return NextResponse.json({ success: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Write failed";
    return NextResponse.json(
      { error: message },
      { status: 500 }
    );
  }
}
