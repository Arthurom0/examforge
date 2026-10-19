import { useEffect, useState } from "react";
import { api, AppSettings, desktop } from "../api";
import { Badge, Button, Card, ErrorBox, Field, inputCls, Spinner } from "../components/ui";

export default function Settings() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [key, setKey] = useState("");
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const apply = (r: AppSettings) => {
    setS(r);
    setModel(r.model);
    setEffort(r.effort);
    setBaseUrl(r.providers.find((p) => p.id === r.provider)?.base_url ?? "");
  };
  useEffect(() => {
    api.settings().then(apply).catch(setErr);
  }, []);

  const save = async (body: Parameters<typeof api.saveSettings>[0]) => {
    setBusy(true);
    setErr(null);
    setSaved(false);
    try {
      apply(await api.saveSettings(body));
      window.dispatchEvent(new Event("examforge:settings-changed"));
      setKey("");
      setSaved(true);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  if (!s) return err ? <ErrorBox error={err} /> : <Spinner />;
  const bridge = desktop();
  const active = s.providers.find((p) => p.id === s.provider) ?? s.providers[0];

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card className="space-y-4">
        <h2 className="font-semibold">AI provider</h2>
        <Field label="Provider" hint="Used for generating problems, variants, solutions and tags. Keys are kept per provider.">
          <select
            className={inputCls}
            value={s.provider}
            disabled={busy}
            onChange={(e) => {
              setKey("");
              save({ provider: e.target.value });
            }}
          >
            {s.providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
                {p.needs_key && p.key_configured ? "  (key saved)" : ""}
              </option>
            ))}
          </select>
        </Field>
        {!active.vision && (
          <p className="text-sm text-slate-500">
            {active.label.split(" (")[0]} can't read page images, so "Re-transcribe from page images" needs another provider.
          </p>
        )}
      </Card>

      {active.needs_key ? (
        <Card className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{active.label} API key</h2>
            {active.key_configured ? <Badge color="green">Configured {active.key_hint}</Badge> : <Badge color="amber">Not set</Badge>}
          </div>
          <p className="text-sm text-slate-500">
            Create one at{" "}
            <a href={active.key_url} target="_blank" rel="noreferrer" className="underline">
              {active.key_url.replace(/^https:\/\//, "").split("/")[0]}
            </a>
            . It is stored only on this computer, in <code className="text-xs">{s.env_file}</code>.
          </p>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (key.trim()) save({ provider: active.id, api_key: key.trim() });
            }}
          >
            <input
              type="password"
              autoComplete="off"
              className={inputCls}
              placeholder={active.key_configured ? "Paste a new key to replace it" : "Paste your API key"}
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <Button type="submit" variant="primary" loading={busy} disabled={!key.trim()}>
              Save key
            </Button>
            {active.key_configured && (
              <Button variant="danger" onClick={() => confirm(`Remove the saved ${active.label} key?`) && save({ provider: active.id, api_key: "" })}>
                Remove
              </Button>
            )}
          </form>
        </Card>
      ) : (
        <Card className="space-y-4">
          <h2 className="font-semibold">Ollama on this computer</h2>
          <p className="text-sm text-slate-500">
            No key needed, and nothing leaves your Mac. Install Ollama from{" "}
            <a href="https://ollama.com/download" target="_blank" rel="noreferrer" className="underline">
              ollama.com
            </a>
            , then run <code className="text-xs">ollama pull {active.model}</code> once. Local models are slower and less reliable than the cloud
            ones for exam-level problems; ExamForge still checks every answer it gets back.
          </p>
          <Field label="Server URL" hint={`Default: ${active.default_base_url}`}>
            <div className="flex gap-2">
              <input className={inputCls} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
              <Button loading={busy} disabled={baseUrl === active.base_url} onClick={() => save({ provider: active.id, base_url: baseUrl })}>
                Save
              </Button>
            </div>
          </Field>
        </Card>
      )}

      <Card className="space-y-4">
        <h2 className="font-semibold">Model</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Model" hint={`Default: ${active.default_model}. You can type any model name ${active.label.split(" (")[0]} offers.`}>
            <input className={inputCls} list="model-suggestions" value={model} onChange={(e) => setModel(e.target.value)} />
            <datalist id="model-suggestions">
              {active.suggested_models.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </Field>
          {active.effort_supported && (
            <Field label="Effort" hint="Higher = more careful self-checking, slower and pricier.">
              <select className={inputCls} value={effort} onChange={(e) => setEffort(e.target.value)}>
                {["low", "medium", "high", "xhigh", "max"].map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>
        <Button
          loading={busy}
          disabled={model.trim() === active.model && effort === s.effort}
          onClick={() => save({ provider: active.id, model: model.trim(), ...(active.effort_supported ? { effort } : {}) })}
        >
          Save
        </Button>
      </Card>

      <Card className="space-y-2 text-sm">
        <h2 className="font-semibold">Scanned PDFs (OCR)</h2>
        {s.ocr_available ? (
          <p>
            <Badge color="green">Tesseract found</Badge> <code className="text-xs">{s.tesseract_path}</code>
          </p>
        ) : (
          <p className="text-slate-600 dark:text-slate-400">
            <Badge color="amber">Tesseract not found</Badge> Text PDFs work without it. For scanned booklets, install it with{" "}
            <code className="text-xs">brew install tesseract tesseract-lang</code>, then restart ExamForge.
          </p>
        )}
      </Card>

      <Card className="space-y-2 text-sm">
        <h2 className="font-semibold">Your data</h2>
        <p className="text-slate-600 dark:text-slate-400">
          Courses, PDFs and progress are stored in <code className="text-xs">{s.data_dir}</code>. Back up this folder to keep your history.
        </p>
        {bridge && <Button onClick={() => bridge.openDataFolder()}>Show in Finder</Button>}
        {bridge && <p className="text-xs text-slate-500">ExamForge {bridge.version}</p>}
      </Card>

      {saved && <p className="text-sm text-emerald-600">Saved.</p>}
      <ErrorBox error={err} />
    </div>
  );
}
