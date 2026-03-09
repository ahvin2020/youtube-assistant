export interface AnalyzeResult {
  success: boolean;
  content?: string;
  usage?: { input_tokens: number; output_tokens: number };
  error?: string;
}

export async function callClaude(
  model: string,
  system: string,
  messages: { role: "user" | "assistant"; content: string }[],
  maxTokens: number = 8192
): Promise<AnalyzeResult> {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      system,
      messages,
      max_tokens: maxTokens,
    }),
  });
  return response.json();
}

export interface WorkspaceReadResult {
  type: "file" | "directory";
  content?: string;
  items?: { name: string; isDirectory: boolean }[];
  error?: string;
}

export async function readWorkspaceFile(path: string): Promise<WorkspaceReadResult> {
  const response = await fetch(`/api/workspace?path=${encodeURIComponent(path)}`);
  return response.json();
}

export async function writeWorkspaceFile(path: string, content: string): Promise<{ success: boolean; error?: string }> {
  const response = await fetch("/api/workspace", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content }),
  });
  return response.json();
}
