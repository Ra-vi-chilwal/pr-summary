import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, login, signup } from "../api";
import { ProductShot } from "../components/ProductShot";
import { useSession } from "../session";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const GITHUB_ERRORS: Record<string, string> = {
  github_failed: "GitHub sign-in didn't complete. Nothing was changed; try again.",
  github_unavailable: "GitHub sign-in isn't set up on this server yet. Use your email instead.",
};

/** Same rule as the server (security.password_problem), shown as a hint while typing. */
export function passwordStrength(pw: string, email = ""): { level: 0 | 1 | 2 | 3; text: string } {
  if (!pw) return { level: 0, text: "At least 10 characters. A short sentence works well." };
  if (pw.length < 10) return { level: 1, text: `${10 - pw.length} more characters needed.` };
  if (new Set(pw).size < 4 || (email && pw.toLowerCase() === email.toLowerCase()))
    return { level: 1, text: "Too easy to guess. Try a short sentence." };
  const variety = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  if (pw.length >= 16 || variety >= 3) return { level: 3, text: "Strong password." };
  return { level: 2, text: "Good. Longer is even better." };
}

function nextPath(params: URLSearchParams): string {
  const n = params.get("next") ?? "";
  return n.startsWith("/") && !n.startsWith("//") ? n : "/dashboard";
}

export function Login() {
  return <AuthPage mode="login" />;
}

export function Signup() {
  return <AuthPage mode="signup" />;
}

function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { me, refresh } = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(GITHUB_ERRORS[params.get("error") ?? ""] ?? null);
  const [busy, setBusy] = useState(false);
  const next = nextPath(params);
  const isSignup = mode === "signup";
  const strength = passwordStrength(password, email);

  function validate(): Record<string, string> {
    const e: Record<string, string> = {};
    if (isSignup && !name.trim()) e.name = "Tell us what to call you.";
    if (!EMAIL.test(email.trim())) e.email = "Enter an email address like name@example.com.";
    if (!password) e.password = "Enter your password.";
    else if (isSignup && strength.level < 2) e.password = strength.text;
    if (isSignup && confirm !== password) e.confirm = "The two passwords don't match.";
    return e;
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    const e = validate();
    setErrors(e);
    setFormError(null);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      if (isSignup) await signup(name.trim(), email.trim(), password);
      else await login(email.trim(), password);
      await refresh();
      navigate(next, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fields);
        if (!Object.keys(err.fields).length || err.status === 429) setFormError(err.detail);
      } else {
        setFormError("Couldn't reach the server. Check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  const field = (id: string) => ({
    id,
    "aria-invalid": Boolean(errors[id]) || undefined,
    "aria-describedby": errors[id] ? `${id}-error` : undefined,
  });

  return (
    <div className="auth">
      <main className="auth-form-side" id="main">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            PR
          </span>
          PR Summary
        </Link>

        <div className="auth-form-wrap">
          <h1>{isSignup ? "Create your account" : "Welcome back"}</h1>
          <p className="lead">
            {isSignup
              ? "Then connect one repository and get a summary on your next pull request."
              : "Sign in to see your summaries and connected repositories."}
          </p>

          {me.github_login_configured && (
            <>
              <a className="btn btn-lg btn-block" href={`/api/auth/github/start?next=${encodeURIComponent(next)}`}>
                <GitHubMark /> Continue with GitHub
              </a>
              <p className="divider" role="separator">
                <span>or with email</span>
              </p>
            </>
          )}

          {formError && (
            <div className="notice error" role="alert">
              <p>{formError}</p>
            </div>
          )}

          <form className="auth-form" onSubmit={submit} noValidate>
            {isSignup && (
              <Field label="Name" error={errors.name} id="name">
                <input className="input" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} {...field("name")} />
              </Field>
            )}
            <Field label="Email" error={errors.email} id="email">
              <input
                className="input"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                {...field("email")}
              />
            </Field>
            <Field
              label="Password"
              error={errors.password}
              id="password"
              aside={
                !isSignup && (
                  <Link className="small" to="/forgot-password">
                    Forgot password?
                  </Link>
                )
              }
            >
              <input
                className="input"
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                {...field("password")}
                aria-describedby={
                  [errors.password && "password-error", isSignup && "password-strength"].filter(Boolean).join(" ") ||
                  undefined
                }
              />
              {isSignup && (
                <div className="strength" id="password-strength" data-level={strength.level}>
                  <span className="strength-bars" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="field-hint">{strength.text}</span>
                </div>
              )}
            </Field>
            {isSignup && (
              <Field label="Confirm password" error={errors.confirm} id="confirm">
                <input
                  className="input"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  {...field("confirm")}
                />
              </Field>
            )}
            <button className="btn btn-primary btn-lg btn-block" type="submit" disabled={busy}>
              {busy ? (isSignup ? "Creating your account…" : "Signing in…") : isSignup ? "Create account" : "Sign in"}
            </button>
          </form>

          <p className="small muted">
            {isSignup ? (
              <>
                Already have an account? <Link to={`/login${params.toString() ? `?${params}` : ""}`}>Sign in</Link>
              </>
            ) : (
              <>
                New here? <Link to={`/signup${params.toString() ? `?${params}` : ""}`}>Create an account</Link>
              </>
            )}
          </p>
        </div>
      </main>

      <aside className="auth-shot-side" aria-label="What PR Summary posts">
        <div className="auth-shot">
          <p className="eyebrow">What your reviewers will see</p>
          <ProductShot />
        </div>
      </aside>
    </div>
  );
}

function Field({
  label,
  id,
  error,
  aside,
  children,
}: {
  label: string;
  id: string;
  error?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="field">
      <div className="field-row">
        <label className="field-label" htmlFor={id}>
          {label}
        </label>
        {aside}
      </div>
      {children}
      {error && (
        <span className="field-error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
  );
}

function GitHubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

export function ForgotPassword() {
  return (
    <div className="page">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/login">Sign in</Link>
      </nav>
      <h1>Reset your password</h1>
      <div className="empty" style={{ marginTop: "var(--space-6)" }}>
        <h3>Password reset isn&apos;t available yet</h3>
        <p className="muted">
          We don&apos;t send email yet, so we can&apos;t reset passwords from here. If you connected
          GitHub, use “Continue with GitHub” to sign in instead.
        </p>
        <Link className="btn" to="/login">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
