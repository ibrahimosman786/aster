"use client";

import { useEffect, useMemo, useState } from "react";
import { EMPLOYEES, agentView, type EmployeeId, type OfficeEvent, type Skill } from "@/lib/company/office";
import styles from "./company.module.css";
import { OfficeMascot } from "./mascot";
import { OfficeFloor, type FloorPin } from "./officeFloor";

const SETUP_KEY = "aster-company-setup";
const SKILL_KEY = "aster-company-skill";
const OFFICE = "http://127.0.0.1:8911";

type OfficeSnapshot = {
  model: string;
  connected: boolean;
  blocked: boolean;
  passed: boolean;
  running: boolean;
  status: string;
  events: OfficeEvent[];
  files: Record<string, string>;
  skill: Skill | null;
};

const MODELS = [
  { id: "aster-desk", name: "Aster desk", note: "Runs the checks in this browser. Nothing is sent away." },
  { id: "openai", name: "OpenAI", note: "Recorded as the preferred model. The checks still run on the Aster desk." },
  { id: "claude", name: "Claude", note: "Recorded as the preferred model. The checks still run on the Aster desk." },
  { id: "grok", name: "Grok", note: "Recorded as the preferred model. The checks still run on the Aster desk." },
  { id: "gemini", name: "Gemini", note: "Recorded as the preferred model. The checks still run on the Aster desk." },
];

type Setup = { company: string; model: string; hired: boolean };

function readSetup(): Setup | null {
  if (typeof window === "undefined") return null;
  const saved = window.localStorage.getItem(SETUP_KEY);
  if (!saved) return null;
  try {
    const parsed = JSON.parse(saved) as Setup;
    if (!parsed.company || !parsed.model || !parsed.hired) return null;
    return parsed;
  } catch {
    return null;
  }
}

async function readOffice(): Promise<OfficeSnapshot | null> {
  try {
    const response = await fetch(`${OFFICE}/state`);
    if (!response.ok) return null;
    return (await response.json()) as OfficeSnapshot;
  } catch {
    return null;
  }
}

function readSkill(): Skill | null {
  if (typeof window === "undefined") return null;
  const saved = window.localStorage.getItem(SKILL_KEY);
  if (!saved) return null;
  try {
    return JSON.parse(saved) as Skill;
  } catch {
    return null;
  }
}

export default function CompanyPage() {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [ready, setReady] = useState(false);
  const [step, setStep] = useState(0);
  const [company, setCompany] = useState("Aster Studio");
  const [model, setModel] = useState("aster-desk");
  const [brief, setBrief] = useState("");
  const [events, setEvents] = useState<OfficeEvent[]>([]);
  const [shown, setShown] = useState(0);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<EmployeeId>("nova");
  const [status, setStatus] = useState("The floor is empty.");
  const [connection, setConnection] = useState("The office has not connected.");
  const [running, setRunning] = useState(false);
  const [skill, setSkill] = useState<Skill | null>(null);
  const [pins, setPins] = useState<FloorPin[]>([]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    const saved = readSetup();
    if (saved) {
      setSetup(saved);
      setCompany(saved.company);
      setModel(saved.model);
    }
    setSkill(readSkill());
    setReady(true);
    void readOffice().then((snapshot) => {
      if (!snapshot) return;
      applySnapshot(snapshot);
    });
  }, []);

  const visible = events.slice(0, shown);
  const employee = EMPLOYEES.find((member) => member.id === selected) ?? EMPLOYEES[0];
  const view = useMemo(() => agentView(visible, selected), [visible, selected]);
  const opened = openIndex !== null ? view.trace[openIndex] : undefined;
  const openedBody = opened ? (files[opened.target] ?? opened.detail) : "";

  function hire() {
    const next = { company, model, hired: true };
    window.localStorage.setItem(SETUP_KEY, JSON.stringify(next));
    setSetup(next);
    setStatus(`${company} is open. Give the team a job.`);
  }

  function applySnapshot(snapshot: OfficeSnapshot) {
    setEvents(snapshot.events);
    setShown(snapshot.events.length);
    setFiles(snapshot.files);
    setStatus(snapshot.status);
    setConnection(snapshot.connected && snapshot.model ? `Connected to ${snapshot.model}` : snapshot.connected ? "Connected to the office" : snapshot.status);
    if (snapshot.skill) {
      window.localStorage.setItem(SKILL_KEY, JSON.stringify(snapshot.skill));
      setSkill(snapshot.skill);
    }
  }

  async function start(keepSkill: boolean) {
    if (running) return;
    setRunning(true);
    setEvents([]);
    setShown(0);
    setFiles({});
    setOpenIndex(null);
    if (!keepSkill) {
      window.localStorage.removeItem(SKILL_KEY);
      setSkill(null);
    }
    let started: Response;
    try {
      started = await fetch(`${OFFICE}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief, keepSkill }),
      });
    } catch {
      setStatus("Blocked: the office is not running. Start it with aster company serve.");
      setConnection("Blocked: the office is not running.");
      setRunning(false);
      return;
    }
    if (!started.ok && started.status !== 202) {
      const payload = (await started.json().catch(() => null)) as OfficeSnapshot | null;
      if (payload) applySnapshot(payload);
      setRunning(false);
      return;
    }
    let live = true;
    while (live) {
      const snapshot = await readOffice();
      if (!snapshot) {
        setStatus("Blocked: the office stopped answering.");
        setRunning(false);
        return;
      }
      applySnapshot(snapshot);
      live = snapshot.running;
      if (live) await new Promise((resolve) => setTimeout(resolve, 400));
    }
    setRunning(false);
  }

  if (!ready) return <main className={styles.company} />;

  if (!setup) {
    return (
      <main className={styles.company}>
        <div className={styles.wizard}>
          <OfficeMascot name="michael" moving={false} />
          {step === 0 && (
            <section>
              <p className={styles.kicker}>Step 1 of 4</p>
              <h1>Start the company</h1>
              <p>You are opening a floor of employees. Each employee is an agent. They hand work to each other, and a skill stays only when the checks pass.</p>
              <button type="button" onClick={() => setStep(1)}>Begin</button>
            </section>
          )}
          {step === 1 && (
            <section>
              <p className={styles.kicker}>Step 2 of 4</p>
              <h1>Name the company</h1>
              <label htmlFor="company-name">Company name</label>
              <input id="company-name" value={company} onChange={(event) => setCompany(event.target.value)} />
              <button type="button" disabled={!company.trim()} onClick={() => setStep(2)}>Continue</button>
            </section>
          )}
          {step === 2 && (
            <section>
              <p className={styles.kicker}>Step 3 of 4</p>
              <h1>Choose the model</h1>
              <p>The Aster desk runs the checks on this page. The other names are recorded as the preferred model. Their keys are not sent from the browser.</p>
              <div className={styles.models}>
                {MODELS.map((item) => (
                  <label key={item.id} className={model === item.id ? styles.picked : ""}>
                    <input type="radio" name="model" checked={model === item.id} onChange={() => setModel(item.id)} />
                    <strong>{item.name}</strong>
                    <span>{item.note}</span>
                  </label>
                ))}
              </div>
              <button type="button" onClick={() => setStep(3)}>Continue</button>
            </section>
          )}
          {step === 3 && (
            <section>
              <p className={styles.kicker}>Step 4 of 4</p>
              <h1>Hire the floor</h1>
              <ul className={styles.roster}>
                {EMPLOYEES.map((member) => (
                  <li key={member.id}><strong>{member.name}</strong> · {member.title}<span>{member.responsibility}</span></li>
                ))}
              </ul>
              <button type="button" onClick={hire}>Open {company}</button>
            </section>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className={styles.company}>
      <section className={styles.app}>
        <header className={styles.bar}>
          <div>
            <h1>{setup.company}</h1>
            <p>{connection} One assistant writes a file. This company discusses the job, splits it, and keeps a lesson only when the check passes.</p>
          </div>
          <p>{status}</p>
        </header>
        <div className={styles.work}>
          <aside className={styles.people}>
            {EMPLOYEES.map((member) => {
              const mode = agentView(visible, member.id).mode;
              return (
                <button key={member.id} type="button" className={selected === member.id ? styles.picked : ""} onClick={() => { setSelected(member.id); setOpenIndex(null); }}>
                  <span className={`${styles.dot} ${styles[`mode_${mode}`] ?? ""}`} />
                  <span><strong>{member.name}</strong><small>{member.title}</small></span>
                  <span className={styles.mode}>{mode}</span>
                </button>
              );
            })}
          </aside>
          <div className={styles.stage}>
            <OfficeFloor events={visible} selected={selected} onSelect={(id) => { setSelected(id); setOpenIndex(null); }} skillKept={Boolean(skill)} onPins={setPins} />
            {pins.map((pin) => (
              <button key={pin.id} type="button" className={`${styles.pin} ${selected === pin.id ? styles.pickedPin : ""}`} style={{ left: `${pin.x * 100}%`, top: `${pin.y * 100}%` }} onClick={() => { setSelected(pin.id); setOpenIndex(null); }}>
                {pin.chip ? <span className={styles.chip}>{pin.chip}</span> : null}
                <span className={styles.nameTag}>{pin.name}</span>
              </button>
            ))}
          </div>
          <aside className={styles.card}>
            <p className={styles.kicker}>{employee.title}</p>
            <strong>{employee.name}</strong>
            <p>{employee.responsibility}</p>
            <p className={styles.mode}>{view.mode}</p>
            <h2>Now</h2>
            <p>{view.chip || "Waiting for a task."}</p>
            <h2>Session</h2>
            <div className={styles.session}>
              {view.discussion.length === 0 && <p className={styles.empty}>Send a job. The team will talk here, in the order they speak.</p>}
              {view.discussion.map((line, index) => {
                const speaker = EMPLOYEES.find((member) => member.id === line.speaker);
                const name = speaker?.name ?? line.speaker;
                const said = line.line.startsWith(`${name}:`) ? line.line.slice(name.length + 1).trim() : line.line.startsWith(name) ? line.line.slice(name.length).replace(/^:\s*/, "").trim() : line.line;
                const mine = line.speaker === selected;
                return (
                  <article key={`${line.speaker}-${index}`} className={mine ? styles.mine : styles.theirs}>
                    <header><strong>{name}</strong> <span>{speaker?.title}</span></header>
                    <p>{said}</p>
                  </article>
                );
              })}
            </div>
            <h2>Tools</h2>
            <div className={styles.trace}>
              {view.trace.length === 0 && <p>No tool yet. Give the company a job.</p>}
              {view.trace.map((step, index) => (
                <button key={`${step.tool}-${step.target}-${index}`} type="button" className={openIndex === index ? styles.picked : ""} onClick={() => setOpenIndex(index)}>
                  <span>{step.tool}</span>
                  <span>{step.target}</span>
                </button>
              ))}
            </div>
            {opened ? <pre className={styles.files}>{openedBody}</pre> : null}
            <h2>Plan</h2>
            <ol className={styles.plan}>
              {view.plan.map((item) => (
                <li key={item.id} className={styles[item.state]}>{item.label}</li>
              ))}
            </ol>
            <h2>Learning</h2>
            <p>{skill ? `Aster kept this lesson: ${skill.procedure}` : "No lesson yet. Sage keeps one only after Pixel’s check passes."}</p>
          </aside>
        </div>
        <form className={styles.brief} onSubmit={(event) => { event.preventDefault(); void start(true); }}>
          <input value={brief} onChange={(event) => setBrief(event.target.value)} aria-label="Message" placeholder="Ask the company to build or discuss something" />
          <button type="submit" disabled={running || !brief.trim()}>Send</button>
          <button type="button" disabled={running} onClick={() => void start(false)}>Forget the skill</button>
        </form>
      </section>
    </main>
  );
}
