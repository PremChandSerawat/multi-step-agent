import { useState } from "react";
import { streamAgent, type StreamEvent, type TimelineEntry } from "./api";

export default function App() {
  const [question, setQuestion] = useState("");
  const [steps, setSteps] = useState<TimelineEntry[]>([]);
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
        const timeline = (event.state?.timeline as TimelineEntry[]) ?? [];
        if (timeline.length) {
          setSteps(timeline);
        } else {
          setSteps((prev) => [
            ...prev,
            {
              phase: event.phase ?? event.node ?? "step",
              message: `Step complete: ${event.node ?? "unknown"}`
            }
          ]);
        }
      }
      if (event.type === "final") {
        const finalAnswer =
          (event.result as any)?.data?.answer ??
          "No answer generated. Please try again.";
        const finalTimeline =
          ((event.result as any)?.timeline as TimelineEntry[]) ?? [];
        if (finalTimeline.length) {
          setSteps(finalTimeline);
        }
        setAnswer(finalAnswer);
        setLoading(false);
        close();
      }
    });

    // Keep the stream open until we receive the final event.
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
              <div className="step-row">
                <span className="step-phase">{step.phase ?? "step"}</span>
                <div className="step-body">
                  <div className="step-message">{step.message}</div>
                  {step.timestamp && (
                    <div className="step-time">
                      {new Date(step.timestamp).toLocaleTimeString()}
                    </div>
                  )}
                </div>
              </div>
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



