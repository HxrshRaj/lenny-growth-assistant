const PROVIDER_META = {
  anthropic: { label: "☁️ Anthropic Claude", modelKey: "anthropic_model", readyKey: "anthropic_configured" },
  gemini: { label: "☁️ Google Gemini", modelKey: "gemini_model", readyKey: "gemini_configured" },
  ollama: { label: "💻 Local (Ollama)", modelKey: "ollama_model", readyKey: "ollama_reachable" },
};

export default function ProviderBadge({ config, healthStatus }) {
  if (!config) {
    return <span className="provider-badge provider-badge--unknown">provider: unknown</span>;
  }

  const meta = PROVIDER_META[config.model_provider] ?? PROVIDER_META.ollama;
  const providerReady = Boolean(config[meta.readyKey]);

  return (
    <div className="provider-badge-group">
      <span className={`provider-badge provider-badge--${providerReady ? "ok" : "warn"}`}>
        {meta.label}
        {" · "}
        {config[meta.modelKey]}
        {!providerReady && " (unreachable)"}
      </span>
      {healthStatus && healthStatus !== "ok" && (
        <span className="provider-badge provider-badge--warn">⚠ backend {healthStatus}</span>
      )}
    </div>
  );
}
