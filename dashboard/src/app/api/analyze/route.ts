import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const ALLOWED_MODELS = [
  "claude-haiku-4-5-20251001",
  "claude-sonnet-4-20250514",
  "claude-opus-4-20250514",
];

interface AnalyzeRequest {
  model: string;
  system?: string;
  messages: { role: "user" | "assistant"; content: string }[];
  max_tokens?: number;
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { success: false, error: "ANTHROPIC_API_KEY not configured" },
      { status: 500 }
    );
  }

  const body = (await request.json()) as AnalyzeRequest;
  const { model, system, messages, max_tokens = 8192 } = body;

  if (!ALLOWED_MODELS.includes(model)) {
    return NextResponse.json(
      { success: false, error: `Model not allowed: ${model}` },
      { status: 403 }
    );
  }

  try {
    const client = new Anthropic({ apiKey });
    const response = await client.messages.create({
      model,
      max_tokens,
      ...(system ? { system } : {}),
      messages,
    });

    const content = response.content
      .filter((block) => block.type === "text")
      .map((block) => {
        if (block.type === "text") return block.text;
        return "";
      })
      .join("");

    return NextResponse.json({
      success: true,
      content,
      usage: response.usage,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
