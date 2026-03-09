#!/usr/bin/env node
/**
 * Render Final Executor
 * ======================
 * Renders the enhanced video to a final MP4 using Remotion CLI.
 *
 * Usage:
 *   node executors/enhance/render_final.js --spec <spec_json> --output <output_path> [--codec h264] [--crf 18]
 *
 * Exits:
 *   0 — render completed
 *   1 — error
 *
 * Output (stdout, JSON):
 *   {
 *     "status": "ok",
 *     "output": "<path>",
 *     "size_mb": 42.5,
 *     "elapsed_seconds": 120.3
 *   }
 */

const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

function main() {
  const args = process.argv.slice(2);
  let specPath = null;
  let outputPath = null;
  let codec = "h264";
  let crf = 18;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--spec":
        specPath = args[++i];
        break;
      case "--output":
        outputPath = args[++i];
        break;
      case "--codec":
        codec = args[++i];
        break;
      case "--crf":
        crf = parseInt(args[++i], 10);
        break;
    }
  }

  if (!specPath || !outputPath) {
    console.log(
      JSON.stringify({
        status: "error",
        message:
          "Usage: render_final.js --spec <spec_json> --output <output_path> [--codec h264] [--crf 18]",
      })
    );
    process.exit(1);
  }

  if (!fs.existsSync(specPath)) {
    console.log(
      JSON.stringify({ status: "error", message: `Spec not found: ${specPath}` })
    );
    process.exit(1);
  }

  const remotionDir = path.resolve(__dirname, "../../remotion");
  const absSpecPath = path.resolve(specPath);
  const absOutputPath = path.resolve(outputPath);

  // Ensure output directory exists
  fs.mkdirSync(path.dirname(absOutputPath), { recursive: true });

  // Read spec to pass as input props
  const spec = JSON.parse(fs.readFileSync(absSpecPath, "utf-8"));

  const startTime = Date.now();

  try {
    // Render using Remotion CLI
    const inputProps = JSON.stringify({ spec });
    const cmd = [
      "npx",
      "remotion",
      "render",
      "EnhancedVideo",
      absOutputPath,
      "--codec",
      codec,
      "--crf",
      String(crf),
      "--props",
      `'${inputProps.replace(/'/g, "'\\''")}'`,
    ].join(" ");

    execSync(cmd, {
      cwd: remotionDir,
      stdio: "pipe",
      timeout: 600000, // 10 minutes
      maxBuffer: 50 * 1024 * 1024,
    });

    const elapsed = (Date.now() - startTime) / 1000;
    const stats = fs.statSync(absOutputPath);
    const sizeMb = (stats.size / (1024 * 1024)).toFixed(1);

    console.log(
      JSON.stringify({
        status: "ok",
        output: absOutputPath,
        size_mb: parseFloat(sizeMb),
        elapsed_seconds: Math.round(elapsed * 10) / 10,
      })
    );
    process.exit(0);
  } catch (err) {
    const elapsed = (Date.now() - startTime) / 1000;
    console.log(
      JSON.stringify({
        status: "error",
        message: err.stderr
          ? err.stderr.toString().slice(-500)
          : err.message,
        elapsed_seconds: Math.round(elapsed * 10) / 10,
      })
    );
    process.exit(1);
  }
}

main();
