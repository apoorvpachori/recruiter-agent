import { useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import "./AshbyApplication.css";

type ApplicationField = {
  id: string;
  label: string;
  kind: "text" | "email" | "phone" | "url" | "textarea" | "select" | "checkbox" | "file";
  required: boolean;
  value: string | boolean | null;
  options: string[];
  source: "profile" | "user" | "unanswered";
  file_name: string | null;
};

type ApplicationDraft = {
  id: string;
  job_id: number;
  job_title: string | null;
  company: string | null;
  application_url: string;
  state: "ready_for_review" | "blocked" | "submitting" | "submitted" | "uncertain";
  fields: ApplicationField[];
  review_token: string | null;
  expires_at: string;
  message: string | null;
  ready_to_submit: boolean;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/applications${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the response status when the API returns no JSON body.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

function valueFor(field: ApplicationField, answers: Record<string, string | boolean | null>) {
  return Object.hasOwn(answers, field.id) ? answers[field.id] : field.value;
}

function isAnswered(field: ApplicationField, value: string | boolean | null): boolean {
  if (!field.required) return true;
  if (field.kind === "checkbox") return value === true;
  if (field.kind === "file") return Boolean(field.file_name);
  return typeof value === "string" && value.trim().length > 0;
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read the selected file."));
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      if (comma < 0) reject(new Error("Could not encode the selected file."));
      else resolve(result.slice(comma + 1));
    };
    reader.readAsDataURL(file);
  });
}

function AshbyApplication() {
  const [url, setUrl] = useState("");
  const [application, setApplication] = useState<ApplicationDraft | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | boolean | null>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = useMemo(
    () => application?.fields.every((field) => isAnswered(field, valueFor(field, answers))) ?? false,
    [application, answers],
  );

  async function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await request<ApplicationDraft>("/prepare", {
        method: "POST",
        body: JSON.stringify({ application_url: url }),
      });
      setApplication(result);
      setAnswers({});
      setDirty(new Set());
      setConfirmed(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not prepare this Ashby form.");
    } finally {
      setBusy(false);
    }
  }

  function changeAnswer(field: ApplicationField, value: string | boolean) {
    setAnswers((current) => ({ ...current, [field.id]: value }));
    setDirty((current) => new Set(current).add(field.id));
    setConfirmed(false);
  }

  async function saveAnswers() {
    if (!application || dirty.size === 0) return;
    setBusy(true);
    setError(null);
    try {
      const values = Object.fromEntries(
        Array.from(dirty, (fieldId) => [fieldId, answers[fieldId]]),
      );
      const result = await request<ApplicationDraft>(`/${application.id}/answers`, {
        method: "PATCH",
        body: JSON.stringify({ values }),
      });
      setApplication(result);
      setDirty(new Set());
      setAnswers({});
      setConfirmed(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save those answers.");
    } finally {
      setBusy(false);
    }
  }

  async function attachFile(field: ApplicationField, event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file || !application) return;
    if (file.size > 10 * 1024 * 1024) {
      setError("Choose a file smaller than 10 MB.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await request<ApplicationDraft>(`/${application.id}/fields/${field.id}/file`, {
        method: "POST",
        body: JSON.stringify({
          name: file.name,
          content_type: file.type || "application/octet-stream",
          content_base64: await toBase64(file),
        }),
      });
      setApplication(result);
      setConfirmed(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not attach that file.");
    } finally {
      setBusy(false);
      input.value = "";
    }
  }

  async function submitAfterReview() {
    if (!application?.review_token || !ready || dirty.size > 0 || !confirmed) return;
    setBusy(true);
    setError(null);
    try {
      const result = await request<ApplicationDraft>(`/${application.id}/confirm`, {
        method: "POST",
        body: JSON.stringify({ review_token: application.review_token, user_confirmed: true }),
      });
      setApplication(result);
    } catch (cause) {
      try {
        const latest = await request<ApplicationDraft>(`/${application.id}`);
        setApplication(latest);
        setAnswers({});
        setDirty(new Set());
      } catch {
        // Keep the current review when the draft itself is unavailable.
      }
      setError(cause instanceof Error ? cause.message : "Could not submit the application.");
    } finally {
      setBusy(false);
      setConfirmed(false);
    }
  }

  const terminal = application?.state === "submitted" || application?.state === "uncertain";

  return (
    <section className="application-page" aria-labelledby="application-heading">
      <div className="application-heading">
        <div className="application-eyebrow">ASHBY APPLICATIONS</div>
        <h1 id="application-heading">Prepare an application</h1>
        <p>We’ll fill only supported fields from your local profile, then show every answer for review.</p>
      </div>

      {!application && (
        <form className="application-start" onSubmit={prepare}>
          <label htmlFor="ashby-job-url">Ashby job URL</label>
          <input
            id="ashby-job-url"
            type="url"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://jobs.ashbyhq.com/company/job-id"
          />
          <p>Only public pages hosted on <code>jobs.ashbyhq.com</code> are supported.</p>
          <button className="application-primary" type="submit" disabled={busy || !url.trim()}>
            {busy ? "Loading application…" : "Prepare application"}
          </button>
        </form>
      )}

      {error && <div className="application-error" role="alert">{error}</div>}

      {application && (
        <div className="application-review">
          <div className="application-target">
            <span>APPLICATION TARGET</span>
            <strong>{application.job_title || application.company || "Ashby-hosted job"}</strong>
            <a href={application.application_url} target="_blank" rel="noreferrer">
              {application.application_url}
            </a>
          </div>

          {application.message && (
            <div className={`application-result ${application.state}`} role="status">
              {application.message}
            </div>
          )}
          {application.state === "submitted" && !application.message && (
            <div className="application-result submitted" role="status">
              Ashby confirmed the application. The job is marked as applied in your tracker.
            </div>
          )}

          {!terminal && (
            <>
              <div className="application-review-intro">
                <h2>Review every answer</h2>
                <p>Profile answers are marked. Unanswered fields need your input. Nothing is submitted until you confirm below.</p>
              </div>
              <div className="application-fields">
                {application.fields.map((field) => {
                  const value = valueFor(field, answers);
                  const unsaved = dirty.has(field.id);
                  return (
                    <div className="application-field" key={field.id}>
                      {field.kind !== "checkbox" && (
                        <label htmlFor={`application-${field.id}`}>
                          {field.label}{field.required && <span aria-label="required"> *</span>}
                        </label>
                      )}
                      {field.kind === "textarea" ? (
                        <textarea
                          id={`application-${field.id}`}
                          value={typeof value === "string" ? value : ""}
                          onChange={(event) => changeAnswer(field, event.target.value)}
                          disabled={busy}
                          rows={4}
                        />
                      ) : field.kind === "select" ? (
                        <select
                          id={`application-${field.id}`}
                          value={typeof value === "string" ? value : ""}
                          onChange={(event) => changeAnswer(field, event.target.value)}
                          disabled={busy}
                        >
                          <option value="">Choose an answer</option>
                          {field.options.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      ) : field.kind === "checkbox" ? (
                        <label className="application-checkbox" htmlFor={`application-${field.id}`}>
                          <input
                            id={`application-${field.id}`}
                            type="checkbox"
                            checked={value === true}
                            onChange={(event) => changeAnswer(field, event.target.checked)}
                            disabled={busy}
                          />
                          <span>{field.label}</span>
                        </label>
                      ) : field.kind === "file" ? (
                        <div className="application-file">
                          <input
                            id={`application-${field.id}`}
                            type="file"
                            accept=".pdf,.doc,.docx"
                            onChange={(event) => void attachFile(field, event)}
                            disabled={busy}
                          />
                          {field.file_name && <span>Attached: {field.file_name}</span>}
                        </div>
                      ) : (
                        <input
                          id={`application-${field.id}`}
                          type={field.kind === "phone" ? "tel" : field.kind}
                          value={typeof value === "string" ? value : ""}
                          onChange={(event) => changeAnswer(field, event.target.value)}
                          disabled={busy}
                        />
                      )}
                      {field.kind !== "checkbox" && (
                        <small className="application-source">
                          {unsaved ? "Your edit · save before review" : field.source === "profile" ? "From local profile" : field.source === "user" ? "Current form value" : "Needs your answer"}
                        </small>
                      )}
                    </div>
                  );
                })}
              </div>

              {dirty.size > 0 && (
                <button className="application-secondary" type="button" onClick={() => void saveAnswers()} disabled={busy}>
                  Save answers and refresh review
                </button>
              )}

              <div className="application-confirmation">
                <div className="application-warning">
                  Check the destination, every answer, and any attached file. Confirming submits this application to Ashby.
                </div>
                <label className="application-confirm-check">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(event) => setConfirmed(event.target.checked)}
                    disabled={busy || !ready || dirty.size > 0}
                  />
                  I reviewed this application and want to submit it now.
                </label>
                {!ready && <p className="application-missing">Complete every required field before submitting.</p>}
                <button
                  className="application-submit"
                  type="button"
                  onClick={() => void submitAfterReview()}
                  disabled={busy || !ready || dirty.size > 0 || !confirmed}
                >
                  {busy ? "Submitting…" : "Submit application to Ashby"}
                </button>
              </div>
            </>
          )}
          {terminal && (
            <button className="application-secondary" type="button" onClick={() => {
              setApplication(null);
              setAnswers({});
              setDirty(new Set());
            }}>
              Prepare another application
            </button>
          )}
        </div>
      )}
    </section>
  );
}

export default AshbyApplication;
