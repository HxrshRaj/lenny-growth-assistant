import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import ChatPanel from "./components/ChatPanel";
import ArtifactViewer from "./components/ArtifactViewer";
import ProviderBadge from "./components/ProviderBadge";
import "./App.css";

const SESSION_STORAGE_KEY = "lenny.session_id";

export default function App() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [artifact, setArtifact] = useState(null);
  const [banner, setBanner] = useState(null);
  const [bootError, setBootError] = useState(null);

  const refreshConfig = useCallback(() => {
    api
      .getConfig()
      .then(setConfig)
      .catch(() => setConfig(null));
    api
      .getHealth()
      .then((h) => setHealthStatus(h.status))
      .catch(() => setHealthStatus("unreachable"));
  }, []);

  const startNewSession = useCallback(async () => {
    setBootError(null);
    try {
      const session = await api.createSession();
      localStorage.setItem(SESSION_STORAGE_KEY, session.id);
      setSessionId(session.id);
      setMessages([]);
      setArtifact(null);
    } catch (e) {
      setBootError(e instanceof ApiError ? e.message : "Could not reach the API.");
    }
  }, []);

  // Boot: resume an existing session if we have one, else create a new one.
  useEffect(() => {
    refreshConfig();
    const existing = localStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) {
      api
        .getSession(existing)
        .then(async () => {
          setSessionId(existing);
          const msgs = await api.listMessages(existing);
          setMessages(msgs);
        })
        .catch(() => startNewSession());
    } else {
      startNewSession();
    }
    const interval = setInterval(refreshConfig, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSend(content) {
    if (!sessionId) return;
    setBanner(null);
    const optimisticUser = {
      id: `optimistic-${Date.now()}`,
      role: "user",
      content,
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setLoading(true);
    try {
      const assistantMessage = await api.postMessage(sessionId, content);
      const fullHistory = await api.listMessages(sessionId);
      setMessages(fullHistory);
      if (assistantMessage.error) {
        setBanner(`Model provider error: ${assistantMessage.error}`);
      }
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id));
      setBanner(e instanceof ApiError ? e.message : "Something went wrong sending your message.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__title">
          <span className="app__logo">🌱</span>
          <span>Lenny Growth Assistant</span>
        </div>
        <div className="app__header-right">
          <ProviderBadge config={config} healthStatus={healthStatus} />
          <button className="app__new-session" onClick={startNewSession}>
            + New chat
          </button>
        </div>
      </header>

      {bootError && <div className="app__banner app__banner--error">{bootError}</div>}
      {banner && <div className="app__banner app__banner--warn">{banner}</div>}

      <main className={`app__main${artifact ? " app__main--split" : ""}`}>
        <ChatPanel messages={messages} onSend={handleSend} loading={loading} onViewArtifact={setArtifact} />
        {artifact && <ArtifactViewer artifact={artifact} onClose={() => setArtifact(null)} />}
      </main>
    </div>
  );
}
