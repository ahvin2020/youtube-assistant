export interface ExecuteResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exitCode?: number;
  error?: string;
}

export async function runExecutor(
  executor: string,
  args: string[],
  python: string = "python3"
): Promise<ExecuteResult> {
  const response = await fetch("/api/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ executor, args, python }),
  });
  return response.json();
}

export function parseExecutorJson<T>(result: ExecuteResult): T | null {
  if (!result.success || !result.stdout) return null;
  try {
    return JSON.parse(result.stdout) as T;
  } catch {
    return null;
  }
}
