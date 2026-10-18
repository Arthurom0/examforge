import { useState } from "react";
import type { Problem } from "../api";
import Markdown from "./Markdown";
import { Badge, Button } from "./ui";

export const TYPE_LABEL: Record<Problem["type"], string> = {
  mcq: "MCQ",
  numerical: "Numerical",
  derivation: "Derivation",
  conceptual: "Conceptual",
};
export const DIFF_LABEL: Record<Problem["difficulty"], string> = { easy: "Easy", medium: "Medium", exam: "Exam-level" };

export function GivenTable({ items }: { items: Problem["given_data"] }) {
  if (!items.length) return null;
  return (
    <table className="my-2 text-sm">
      <tbody>
        {items.map((g, i) => (
          <tr key={i}>
            <td className="py-0.5 pr-3">
              <Markdown compact>{`$${g.symbol} = ${g.value}${g.unit ? `\\ \\mathrm{${g.unit}}` : ""}$`}</Markdown>
            </td>
            <td className="py-0.5 text-slate-500">{g.description}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ProblemStatement({ p, index }: { p: Problem; index: number }) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">
          {index + 1}. {p.title}
        </h3>
        <Badge>{TYPE_LABEL[p.type]}</Badge>
        <Badge>{DIFF_LABEL[p.difficulty]}</Badge>
        {p.topic_tags.map((t) => (
          <Badge key={t} color="indigo">
            {t}
          </Badge>
        ))}
      </div>
      <Markdown>{p.statement}</Markdown>
      <GivenTable items={p.given_data} />
      {p.choices.length > 0 && (
        <ul className="mt-2 space-y-1">
          {p.choices.map((c) => (
            <li key={c.label} className="flex items-baseline gap-2">
              <span className="font-semibold">{c.label}.</span>
              <Markdown compact>{c.text}</Markdown>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Solution({ p }: { p: Problem }) {
  const fr = p.language === "fr";
  return (
    <div className="space-y-3">
      {p.solution_steps.map((s, i) => (
        <div key={i}>
          <div className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">
            {fr ? "Étape" : "Step"} {i + 1} · {s.title}
          </div>
          <Markdown>{s.content}</Markdown>
        </div>
      ))}
      <div className="rounded-lg bg-emerald-50 px-3 py-2 dark:bg-emerald-950">
        <span className="text-sm font-semibold">{fr ? "Réponse" : "Answer"} : </span>
        <Markdown compact className="inline-block">{p.answer}</Markdown>
      </div>
    </div>
  );
}

/** Step-by-step reveal: one step at a time, or everything at once. */
export function SolutionReveal({ p }: { p: Problem }) {
  const [shown, setShown] = useState(0);
  const total = p.solution_steps.length;
  const fr = p.language === "fr";
  if (shown === 0)
    return (
      <div className="flex gap-2">
        <Button onClick={() => setShown(1)}>{fr ? "Indice : première étape" : "Hint: first step"}</Button>
        <Button onClick={() => setShown(total + 1)}>{fr ? "Voir la solution complète" : "Show full solution"}</Button>
      </div>
    );
  const steps = p.solution_steps.slice(0, Math.min(shown, total));
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800">
      {steps.map((s, i) => (
        <div key={i}>
          <div className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">
            {fr ? "Étape" : "Step"} {i + 1}/{total} · {s.title}
          </div>
          <Markdown>{s.content}</Markdown>
        </div>
      ))}
      {shown > total ? (
        <>
          <div className="rounded-lg bg-emerald-50 px-3 py-2 dark:bg-emerald-950">
            <span className="text-sm font-semibold">{fr ? "Réponse" : "Answer"} : </span>
            <Markdown compact className="inline-block">{p.answer}</Markdown>
          </div>
          {p.self_check && (
            <details className="text-xs text-slate-500">
              <summary className="cursor-pointer">Model self-check</summary>
              <p className="mt-1">{p.self_check}</p>
            </details>
          )}
        </>
      ) : (
        <div className="flex gap-2">
          <Button onClick={() => setShown((s) => s + 1)}>{fr ? "Étape suivante" : "Next step"}</Button>
          <Button variant="ghost" onClick={() => setShown(total + 1)}>
            {fr ? "Tout afficher" : "Show all"}
          </Button>
        </div>
      )}
    </div>
  );
}
