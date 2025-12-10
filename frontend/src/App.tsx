import { useState } from "react";
import { runQuery, streamAgent, type StreamEvent } from "./api";

type Step = {
  node?: string;
  summary: string;
};

export default function App() {
  const [question, setQuestion] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [answer, setAnswer] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setSteps([]);
    setAnswer(null);
    setError(null);
  };

  const handleSubmit = async (evt: React.FormEvent) => {
    evt.preventDefault();
    if (!question.trim()) return;
    reset();
    setLoading(true);

    const close = streamAgent(question, (event: StreamEvent) => {
      if (event.type === "step") {
        setSteps((prev) => [
          ...prev,
          {
            node: event.node,
            summary: `Step complete: ${event.node ?? "unknown"}`
          }
        ]);
      }
      if (event.type === "final") {
        const finalAnswer =
          (event.result as any)?.data?.answer ??
          "No answer generated. Please try again.";
        setAnswer(finalAnswer);
        setLoading(false);
      }
    });

    // Fallback to non-streaming in case SSE disconnects early.
    try {
      const result = await runQuery(question);
      if (!answer) {
        setAnswer(result.answer ?? "No answer generated.");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      close();
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <div className="card">
        <h1>Production Line Agent</h1>
        <p className="sub">
          Ask anything about stations, OEE, bottlenecks, or maintenance. The
          agent will reason step-by-step using MCP tools.
        </p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the bottleneck and current OEE?"
          />
          <button type="submit" disabled={loading}>
            {loading ? "Running..." : "Ask"}
          </button>
        </form>

        {error && <div style={{ color: "red" }}>{error}</div>}

        <h3>Steps</h3>
        <ul className="steps">
          {steps.map((step, idx) => (
            <li key={idx}>
              <strong>{step.node ?? "Step"}</strong> — {step.summary}
            </li>
          ))}
          {loading && steps.length === 0 && <li>Preparing agent...</li>}
        </ul>

        <h3>Answer</h3>
        <div className="answer">
          {answer ?? "Ask a question to see the answer here."}
        </div>
      </div>
    </div>
  );
}

