/**
 * Adapter runner for agent-toolkit (P1). Executed with P1's own tsx binary, so P1's code and
 * its pinned dependencies are used exactly as they are in that repo. Nothing in P1 is modified.
 *
 *   echo '{"cases":[...]}' | $P1/node_modules/.bin/tsx evals/adapters/p1_runner.mts $P1
 *
 * Reads tool_failure cases on stdin, prints one JSON line per case on stdout.
 * The scripted model steps come from the frozen dataset. Final answers are computed from the
 * tool results the agent actually returned in this run, never copied from the dataset.
 */
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import { readFileSync } from "node:fs";

const repo = process.argv[2];
if (!repo) {
  console.error("usage: tsx p1_runner.mts <agent-toolkit repo path>  (cases as JSON on stdin)");
  process.exit(2);
}
const imp = (p: string) => import(pathToFileURL(join(repo, p)).href);
const { runAgent } = await imp("src/agent.ts");
const { RunLog } = await imp("src/log.ts");
const { setup } = await imp("src/setup.ts");
const { ScriptedModel, call, toolResults } = await imp("src/model/scripted.ts");

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Detail = { id: string; name: string; city: string; certifications: string[]; lead_time_days: number; contact_email: string };

const parsedResults = (t: Json[]): Json[] =>
  toolResults(t).filter((r: Json) => !r.isError).map((r: Json) => JSON.parse(r.content));
const details = (t: Json[]): Detail[] => parsedResults(t).filter((r) => "lead_time_days" in r);
const lastSearch = (t: Json[]) => parsedResults(t).filter((r) => "results" in r).at(-1) as { results: { id: string }[] } | undefined;

const insufficient = (answer: string, ids: string[] = []) =>
  call("final_answer", { status: "insufficient_evidence", answer, supplier_ids: ids, evidence_ids: [] });

function finalFromRule(rule: Json, t: Json[]) {
  const ds = details(t);
  switch (rule.rule) {
    case "fastest_with_cert": {
      const ok = ds.filter((d) => d.certifications.includes(rule.cert) && d.city === rule.city).sort((a, b) => a.lead_time_days - b.lead_time_days);
      const best = ok[0];
      if (!best) return insufficient(`No fetched supplier in ${rule.city} is ${rule.cert} certified.`);
      return call("final_answer", {
        status: "answered",
        answer: `${best.name} (${best.id}) has the shortest lead time among ${rule.cert} suppliers in ${rule.city}: ${best.lead_time_days} days.`,
        supplier_ids: [best.id],
        evidence_ids: ok.map((d) => d.id),
      });
    }
    case "lead_time_of":
    case "lead_time_of_first_fetched": {
      const d = rule.rule === "lead_time_of" ? ds.find((x) => x.id === rule.id) : ds[0];
      if (!d) return insufficient(`No supplier record could be fetched${rule.id ? ` for ${rule.id}` : ""}; the lead time is unknown.`, rule.id ? [rule.id] : []);
      return call("final_answer", { status: "answered", answer: `${d.name} (${d.id}) quotes ${d.lead_time_days} days lead time.`, supplier_ids: [d.id], evidence_ids: [d.id] });
    }
    case "contact_of": {
      const d = ds.find((x) => x.id === rule.id);
      if (!d) return insufficient(`The record for ${rule.id} could not be fetched; the contact is unknown.`, [rule.id]);
      return call("final_answer", { status: "answered", answer: `Contact ${d.name} (${d.id}) at ${d.contact_email}.`, supplier_ids: [d.id], evidence_ids: [d.id] });
    }
    default:
      throw new Error(`unknown final rule ${rule.rule}`);
  }
}

function stepFn(step: Json) {
  return (t: Json[]) => {
    if (step.text !== undefined) return { text: step.text, calls: [] };
    if (step.calls) return { calls: step.calls.map((c: Json) => call(c.name, c.args)) };
    if (step.fetch_search_results) return { calls: (lastSearch(t)?.results ?? []).map((r) => call("get_supplier", { id: r.id })) };
    if (step.final_literal) return { calls: [call("final_answer", step.final_literal)] };
    if (step.final) return { calls: [finalFromRule(step.final, t)] };
    throw new Error(`unknown script step ${JSON.stringify(step)}`);
  };
}

const input = JSON.parse(readFileSync(0, "utf8")) as { cases: { id: string; question: string; script: Json }[] };

for (const c of input.cases) {
  const s = c.script;
  const { registry, svc } = await setup({ faults: s.faults, timeoutMs: s.timeout_ms });
  try {
    const log = new RunLog(); // in memory only, nothing is written into the P1 repo
    const model = new ScriptedModel(s.steps.map(stepFn), `agent-evals:${c.id}`, Boolean(s.repeat_last));
    const r = await runAgent(c.question, { model, registry, log, maxSteps: s.max_steps });
    const ev = log.events as Json[];
    const toolEv = ev.filter((e) => e.type === "tool_call");
    console.log(JSON.stringify({
      id: c.id,
      run_status: r.status,
      steps: r.steps,
      final: r.answer ?? null,
      tool_calls: r.toolCalls,
      tool_error_codes: toolEv.filter((e) => !e.ok).map((e) => e.error.code),
      fetched_ids: toolEv.filter((e) => e.ok && e.tool === "get_supplier").map((e) => e.args.id),
      final_rejections: ev.filter((e) => e.type === "final_rejected").length,
      model_id: model.id,
    }));
  } catch (e) {
    console.log(JSON.stringify({ id: c.id, harness_error: (e as Error).message }));
  } finally {
    await svc.close();
  }
}
