export default function ProviderBadge({ config, healthStatus }) {
  if (!config) {
    return <span className="provider-badge provider-badge--unknown">provider: unknown</span>;
  }

  const providerReady =
    config.model_provider === "anthropic" ? config.anthropic_configured : config.ollama_reachable;

  return (
    <div className="provider-badge-group">
      <span className={`provider-badge provider-badge--${providerReady ? "ok" : "warn"}`}>
        {config.model_provider === "anthropic" ? "☁️ Anthropic Claude" : "💻 Local (Ollama)"}
        {" · "}
        {config.model_provider === "anthropic" ? config.anthropic_model : config.ollama_model}
        {!providerReady && " (unreachable)"}
      </span>
      {healthStatus && healthStatus !== "ok" && (
        <span className="provider-badge provider-badge--warn">⚠ backend {healthStatus}</span>
      )}
    </div>
  );
}
