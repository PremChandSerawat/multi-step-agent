import { NextRequest, NextResponse } from "next/server";

// Proxy Vercel AI SDK chat requests to the FastAPI backend.
export async function POST(req: NextRequest) {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  const targetUrl = `${apiBase}/chat`;

  try {
    const targetResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Forward auth/custom headers if present.
        ...(req.headers.get("authorization")
          ? { authorization: req.headers.get("authorization")! }
          : {}),
      },
      body: req.body,
      // Keep streaming intact.
      duplex: "half",
    });

    return new NextResponse(targetResponse.body, {
      status: targetResponse.status,
      headers: targetResponse.headers,
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to reach backend /chat", detail: String(error) },
      { status: 502 },
    );
  }
}
