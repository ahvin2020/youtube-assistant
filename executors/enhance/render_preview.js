#!/usr/bin/env node
/**
 * Render Preview Executor
 * ========================
 * Starts the Remotion editor UI dev server for interactive enhancement preview.
 *
 * Usage:
 *   node executors/enhance/render_preview.js --spec <spec_json> [--port 3100]
 *
 * Exits:
 *   0 — server started successfully
 *   1 — error
 *
 * Output (stdout, JSON):
 *   { "status": "running", "url": "http://localhost:3100", "spec": "<path>" }
 */

const { execSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

function main() {
  const args = process.argv.slice(2);
  let specPath = null;
  let port = 3100;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--spec" && args[i + 1]) {
      specPath = args[i + 1];
      i++;
    } else if (args[i] === "--port" && args[i + 1]) {
      port = parseInt(args[i + 1], 10);
      i++;
    }
  }

  if (!specPath) {
    console.log(
      JSON.stringify({
        status: "error",
        message: "Usage: render_preview.js --spec <spec_json> [--port 3100]",
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

  // Check if node_modules exists
  if (!fs.existsSync(path.join(remotionDir, "node_modules"))) {
    try {
      execSync("npm install", { cwd: remotionDir, stdio: "pipe" });
    } catch (e) {
      console.log(
        JSON.stringify({
          status: "error",
          message: "Failed to install Remotion dependencies",
        })
      );
      process.exit(1);
    }
  }

  // Start Vite dev server for the editor UI
  const url = `http://localhost:${port}?spec=${encodeURIComponent(path.resolve(specPath))}`;

  const child = spawn("npx", ["vite", "dev", "--port", String(port)], {
    cwd: remotionDir,
    stdio: "pipe",
    detached: true,
    env: { ...process.env, SPEC_PATH: path.resolve(specPath) },
  });

  // Wait briefly for server to start, then report
  setTimeout(() => {
    console.log(
      JSON.stringify({
        status: "running",
        url,
        spec: path.resolve(specPath),
        port,
        pid: child.pid,
      })
    );
    // Detach so the server keeps running after this script exits
    child.unref();
    process.exit(0);
  }, 3000);

  child.on("error", (err) => {
    console.log(
      JSON.stringify({
        status: "error",
        message: `Failed to start editor: ${err.message}`,
      })
    );
    process.exit(1);
  });
}

main();
