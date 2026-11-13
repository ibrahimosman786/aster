"""Run and display one real, feedback-driven harness update on a routing task."""

import difflib
import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml
from reef_client import ReefClient

from harness.routing import expected, grade, task


def main():
    root = Path(__file__).resolve().parent
    existing = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    os.chdir(root)
    work = root / "work" / ("routing-" + time.strftime("%Y%m%d-%H%M%S"))
    work.mkdir(parents=True)
    config = yaml.safe_load((root / "configs/serve.yaml").read_text())
    config["aster"]["port"] = 8902
    config["aster"]["run-dir"] = str(work / "stack")
    evolution = config["recipe"]["config"]["evolution"]
    evolution["state_dir"] = str(work / "harness")
    validation = [task("CA", "enterprise", False), task("UK", "standard", True)]
    evolution["evaluation"]["tasks"] = validation
    evolution["evaluation"]["scorer"] = "tutorials.evolve-your-harness.harness.routing:RoutingScorer"
    for field, folder in {
        "agent-record-dir": "agent-record", "artifact-repository": "artifacts.git",
        "artifact-work-dir": "artifact-work", "artifact-cache-dir": "artifact-cache",
    }.items():
        config["storage"][field] = str(work / folder)
    config_path = work / "serve.yaml"
    config_path.write_text(yaml.safe_dump(config))
    if existing is not None:
        config_path.unlink()
        work.rmdir()
        work = existing
        config_path = work / "serve.yaml"
    process_env = dict(os.environ, PYTHONPATH=str(root.parents[1]))
    with (work / "service.log").open("w") as log:
        service = subprocess.Popen(
            [sys.executable, "-m", "aster", "serve", "-c", str(config_path)],
            stdout=log, stderr=subprocess.STDOUT, env=process_env,
        )
        try:
            run(work, service, existing is not None)
        finally:
            service.terminate()
            try:
                service.wait(timeout=20)
            except subprocess.TimeoutExpired:
                service.kill()
                service.wait()


def run(work, service, resume=False):
    url = "http://127.0.0.1:8902"
    for _ in range(90):
        if service.poll() is not None:
            raise RuntimeError(f"Service failed. Inspect {work / 'service.log'} locally.")
        try:
            if httpx.get(url + "/healthz", timeout=1).is_success:
                break
        except httpx.TransportError:
            pass
        time.sleep(1)
    else:
        raise TimeoutError("Service did not become healthy")
    scenario = "aster-routing"
    client = ReefClient(url, token=os.environ.get("ASTER_TOKEN") or None, timeout_s=300)
    client.post("/aster/scenarios", scenario, {"name": scenario})
    for _ in range(180):
        state = client.get(f"/aster/scenarios/{scenario}/inference/status")["state"]
        if state == "ready":
            break
        if state == "failed":
            raise RuntimeError("Scenario startup failed")
        time.sleep(1)
    else:
        raise TimeoutError("Scenario did not become ready")
    model = os.environ["ASTER_UPSTREAM_MODEL"]
    if resume:
        result = json.loads((work / "result.json").read_text())
        verify_and_render(work, result, client, model, scenario)
        return
    prompt = task("US", "enterprise", True)
    response, receipt = client.inference_with_record(scenario, "/v1/chat/completions", {
        "model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048,
    })
    answer = response["choices"][0]["message"].get("content") or ""
    score = grade(prompt, answer)
    feedback = (
        "Our internal convention is lowercase region, then E for enterprise or S for standard, "
        "then now when urgent is true or queue when false. Separate the three fields with ::. "
        "For this request the required final line is " + expected(prompt) + "."
    )
    result = dict(task=prompt, before=answer, before_score=score, feedback=feedback)
    print(f"Original response score: {score}; submitting actual feedback", flush=True)
    client.report(scenario, {"score": score, "feedback": feedback}, references=[receipt])
    headers = {"x-aster-scenario": scenario}
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        rows = client.get("/aster/harness/artifacts", extra_headers=headers)["artifacts"]
        training = [row for row in rows if row.get("operation") == "training"]
        if training:
            result["training"] = training
            break
        time.sleep(3)
    manifest = client.get("/aster/harness", extra_headers=headers)
    result["manifest"] = manifest
    (work / "result.json").write_text(json.dumps(result, indent=2))
    print("Training record saved: " + str(work / "result.json"), flush=True)
    verify_and_render(work, result, client, model, scenario)


def verify_and_render(work, result, client, model, scenario):
    manifest = client.get("/aster/harness", extra_headers={"x-aster-scenario": scenario})
    rules = manifest["files"]["plugin/rules.md"]
    prompt = task("DE", "standard", False)
    response, receipt = client.inference_with_record(scenario, "/v1/chat/completions", {
        "model": model,
        "messages": [{"role": "system", "content": rules}, {"role": "user", "content": prompt}],
        "max_tokens": 2048,
    })
    answer = response["choices"][0]["message"].get("content") or ""
    result["fresh_task"] = dict(task=prompt, reply=answer, score=grade(prompt, answer), receipt=receipt,
                                artifact_id=manifest["artifact_id"])
    (work / "result.json").write_text(json.dumps(result, indent=2))
    metrics = result["training"][-1]["metrics"]
    count = metrics["evaluation_task_count"]
    seed = Path("seeds/pi/rules.md").read_text()
    changes = "".join(difflib.unified_diff(seed.splitlines(True), rules.splitlines(True),
                                         fromfile="Original instructions", tofile="Learned instructions"))
    rows = "".join(
        f"<tr><td>{html.escape(row['task'].split('Request: ')[1])}</td>"
        f"<td>{html.escape(row['reply'] or '(empty)')}</td><td>{row['score']:.0f}</td></tr>"
        for row in metrics["candidate_runs"]
    )
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Aster · Learning run</title>
<style>body{{background:#101820;color:#e8eef2;font:17px/1.65 system-ui;margin:0;padding:40px}}
main{{max-width:1000px;margin:auto}}h1{{font-size:42px;letter-spacing:-1px}}h2{{font-size:22px}}
section{{background:#192630;padding:24px;border-radius:16px;margin:24px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#101820;padding:18px;border-radius:8px}}
.score{{font-size:36px;color:#80e7bc}}a{{color:#80e7bc}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #40515c}}table{{width:100%;border-collapse:collapse}}p{{max-width:850px}}</style>
<main><p>ASTER / RECORDED EXPERIMENT</p><h1>One feedback report. A learned routing rule.</h1>
<p>This controlled example teaches an organization-specific convention through feedback. It updates the agent's instructions. The hosted model's weights stay fixed.</p>
<section><h2>Paired evaluation on two separate requests</h2><p class="score">{metrics['current_score']:.0f}/{count} before → {metrics['candidate_score']:.0f}/{count} after</p>
<p>Published: {str(metrics['selected']).lower()}. {html.escape(metrics['selection']['reason'])}.</p>
<p>Small demonstration with one run per request. These results do not establish broader performance.</p></section>
<section><h2>1. Original attempt</h2><pre>{html.escape(result['task'])}</pre><pre>{html.escape(result['before'] or '(No final answer within the response budget.)')}</pre>
<p>Score: {result['before_score']:.0f}. The blank response is recorded as a failure.</p></section>
<section><h2>2. Feedback supplied by the evaluator</h2><pre>{html.escape(result['feedback'])}</pre></section>
<section><h2>3. Instructions written by the model</h2><pre>{html.escape(changes)}</pre></section>
<section><h2>4. Candidate evaluation</h2><table><tr><th>Request</th><th>Answer</th><th>Score</th></tr>{rows}</table></section>
<section><h2>5. Fresh request after publication</h2><p>The client pulled the published instructions and included them in a new request through Aster.</p>
<pre>{html.escape(prompt)}</pre><pre>{html.escape(answer or '(No final answer)')}</pre><p>Score: {result['fresh_task']['score']:.0f}/1.</p>
<p>Artifact: {html.escape(manifest['artifact_id'])}</p></section>
<p><a href="result.json">Inspect the recorded results</a></p></main></html>'''
    (work / "learning.html").write_text(page)
    print(f"Fresh task score: {result['fresh_task']['score']}. View {work / 'learning.html'}", flush=True)


if __name__ == "__main__":
    main()
