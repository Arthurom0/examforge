import { useEffect, useState } from "react";
import { api, AppSettings, desktop } from "../api";
import { Badge, Button, Card, ErrorBox, Field, inputCls, Spinner } from "../components/ui";

const MODELS = [
  ["claude-opus-5-5", "Claude Opus 5.5 (best quality, default)"],
  ["claude-sonnet-5-5", "Claude Sonnet 5.5 (faster, cheaper)"],
  ["claude-haiku-5-5", "Claude Haiku 5.5 (fastest, cheapest)"],
];

export default function Settings() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [key, setKey] = useState("");
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const apply = (r: AppSettings) => {
    setS(r);
    setModel(r.model);
    setEffort(r.effort);
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

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Anthropic API key</h2>
          {s.api_key_configured ? <Badge color="green">Configured {s.api_key_hint}</Badge> : <Badge color="amber">Not set</Badge>}
        </div>
        <p className="text-sm text-slate-500">
          Needed to generate problems, variants and solutions. Create one at{" "}
          <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer" className="underline">
            console.anthropic.com
          </a>
          . It is stored only on this computer, in <code className="text-xs">{s.env_file}</code>.
        </p>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (key.trim()) save({ api_key: key.trim() });
          }}
        >
          <input
            type="password"
            autoComplete="off"
            className={inputCls}
            placeholder={s.api_key_configured ? "Paste a new key to replace it" : "sk-ant-…"}
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          <Button type="submit" variant="primary" loading={busy} disabled={!key.trim()}>
            Save key
          </Button>
          {s.api_key_configured && (
            <Button variant="danger" onClick={() => confirm("Remove the saved API key?") && save({ api_key: "" })}>
              Remove
            </Button>
          )}
        </form>
      </Card>

      <Card className="space-y-4">
        <h2 className="font-semibold">Generation</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Model">
            <select className={inputCls} value={model} onChange={(e) => setModel(e.target.value)}>
              {!MODELS.some(([id]) => id === model) && <option value={model}>{model}</option>}
              {MODELS.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Effort" hint="Higher = more careful self-checking, slower and pricier.">
            <select className={inputCls} value={effort} onChange={(e) => setEffort(e.target.value)}>
              {["low", "medium", "high", "xhigh", "max"].map((x) => (
                <option key={x} value={x}>
                  {x}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button loading={busy} disabled={model === s.model && effort === s.effort} onClick={() => save({ model, effort })}>
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
