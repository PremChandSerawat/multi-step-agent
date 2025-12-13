import { NextRequest, NextResponse } from "next/server";

// Proxy sync chat requests to the FastAPI backend
export async function POST(req: NextRequest) {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  const targetUrl = `${apiBase}/chat/sync`;

  try {
    const body = await req.json();

    const targetResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Forward auth headers if present
        ...(req.headers.get("authorization")
          ? { authorization: req.headers.get("authorization")! }
          : {}),
      },
      body: JSON.stringify(body),
    });

    if (!targetResponse.ok) {
      return NextResponse.json(
        { error: "Backend error", status: targetResponse.status },
        { status: targetResponse.status }
      );
    }

    // Non-streaming JSON response
    const data = await targetResponse.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Sync Chat API error:", error);
    return NextResponse.json(
      { error: "Failed to reach backend", detail: String(error) },
      { status: 502 }
    );
  }
}


