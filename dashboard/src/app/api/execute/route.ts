import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

export const dynamic = "force-dynamic";
export const maxDuration = 300; // 5 min timeout for long-running executors

const WORKSPACE_ROOT = path.resolve(process.cwd(), "..");

// Whitelist of allowed executor paths
const ALLOWED_EXECUTORS = new Set([
  "ideas/youtube_ideas.py",
  "ideas/google_trends_ideas.py",
  "ideas/reddit_ideas.py",
  "ideas/twitter_ideas.py",
  "ideas/export_ideas_sheet.py",
  "research/fetch_transcript.py",
  "research/export_google_doc.py",
  "thumbnail/cross_niche_research.py",
  "thumbnail/match_headshot.py",
  "thumbnail/replace_face.py",
  "thumbnail/build_grid.py",
  "thumbnail/export_research_sheet.py",
  "video/transcribe.py",
  "video/validate_cut_spec.py",
  "video/apply_cuts.py",
  "enhance/validate_spec.py",
  "enhance/prepare_assets.py",
  "analyze/fetch_channel_data.py",
  "analyze/export_analysis_sheet.py",
]);

interface ExecuteRequest {
  executor: string;
  args: string[];
  python?: string;
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as ExecuteRequest;
  const { executor, args, python = "python3" } = body;

  // Validate executor is whitelisted
  if (!ALLOWED_EXECUTORS.has(executor)) {
    return NextResponse.json(
      { success: false, error: `Executor not allowed: ${executor}` },
      { status: 403 }
    );
  }

  // Validate python path
  const allowedPythons = ["python3", "/opt/homebrew/bin/python3"];
  if (!allowedPythons.includes(python)) {
    return NextResponse.json(
      { success: false, error: `Python path not allowed: ${python}` },
      { status: 403 }
    );
  }

  const executorPath = path.join(WORKSPACE_ROOT, "executors", executor);

  return new Promise<NextResponse>((resolve) => {
    const proc = spawn(python, [executorPath, ...args], {
      cwd: WORKSPACE_ROOT,
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      resolve(
        NextResponse.json({
          success: code === 0,
          stdout,
          stderr,
          exitCode: code,
        })
      );
    });

    proc.on("error", (err) => {
      resolve(
        NextResponse.json(
          { success: false, error: err.message, stderr },
          { status: 500 }
        )
      );
    });
  });
}
