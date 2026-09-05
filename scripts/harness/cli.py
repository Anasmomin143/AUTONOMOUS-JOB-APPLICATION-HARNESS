"""Command-line entry point for the harness.

Each subcommand is thin — the heavy lifting lives in the sibling modules.
Slash commands under `.claude/commands/*.md` shell into this file.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from . import batch as batch_mod
from . import discovery
from . import modes
from . import paths as P
from . import scoring as scoring_mod
from .config import Config
from .profile import load_profile
from .resume import decide as decide_mod
from .resume import render as render_mod
from .resume import tailor as tailor_mod
from .resume import validate as validate_mod
from .state import read_json, write_json
from .tracker import activity, excel as excel_mod


# ---------------------------------------------------------------- helpers

def _load_apps() -> dict:
    return read_json(P.APPLICATIONS_JSON, {"applications": []})


def _save_apps(data: dict) -> None:
    write_json(P.APPLICATIONS_JSON, data)


def _load_jobs(kind: str) -> list[dict]:
    path = {
        "discovered": P.DISCOVERED_JOBS,
        "qualified":  P.QUALIFIED_JOBS,
        "rejected":   P.REJECTED_JOBS,
        "archive":    P.ARCHIVE_JOBS,
    }[kind]
    return read_json(path, [])


def _save_jobs(kind: str, jobs: list[dict]) -> None:
    path = {
        "discovered": P.DISCOVERED_JOBS,
        "qualified":  P.QUALIFIED_JOBS,
        "rejected":   P.REJECTED_JOBS,
        "archive":    P.ARCHIVE_JOBS,
    }[kind]
    write_json(path, jobs)


def _sync_excel() -> None:
    data = _load_apps().get("applications", [])
    counts = _dashboard_counts(data)
    excel_mod.rewrite(data, counts)


def _dashboard_counts(apps: list[dict]) -> dict:
    def _has(status: str) -> int:
        return sum(1 for a in apps if (a.get("status") or "").upper() == status)
    total_jobs = len(_load_jobs("discovered"))
    qualified = len(_load_jobs("qualified"))
    submitted = _has("APPLIED") + _has("SUBMITTED")
    failed = _has("FAILED")
    prepared = sum(1 for a in apps if a.get("status") in ("READY_FOR_APPROVAL", "PREPARED"))
    return {
        "Total Jobs":           total_jobs,
        "Qualified Jobs":       qualified,
        "Applications Prepared": prepared,
        "Applications Submitted": submitted,
        "Applications Failed":  failed,
        "Assessments":          _has("ASSESSMENT"),
        "Interviews":           _has("INTERVIEW"),
        "Offers":               _has("OFFER"),
        "Rejections":           _has("REJECTED"),
        "Follow-ups Due":       sum(1 for a in apps if a.get("followup_date") and a["followup_date"] <= dt.date.today().isoformat()),
        "Response Rate":         _rate(_has("INTERVIEW") + _has("ASSESSMENT") + _has("REJECTED"), submitted),
        "Interview Conversion Rate": _rate(_has("INTERVIEW"), submitted),
        "Offer Conversion Rate":     _rate(_has("OFFER"), submitted),
        "Rejection Rate":            _rate(_has("REJECTED"), submitted),
    }


def _rate(num: int, denom: int) -> str:
    return f"{(100 * num / denom):.1f}%" if denom else ""


def _preflight_profile() -> tuple[bool, list[str]]:
    profile = load_profile()
    return profile.is_ready()


# ---------------------------------------------------------------- commands

def cmd_bootstrap(args) -> int:
    P.ensure_dirs()
    # Seed empty JSON files if missing
    for path, default in [
        (P.DISCOVERED_JOBS, []),
        (P.QUALIFIED_JOBS, []),
        (P.REJECTED_JOBS, []),
        (P.ARCHIVE_JOBS, []),
        (P.APPLICATIONS_JSON, {"applications": []}),
        (P.FOLLOWUPS_JSON, {"followups": []}),
        (P.INTERVIEWS_JSON, {"interviews": []}),
        (P.COUNTERS_JSON, {"app_seq": {}, "batch_seq": {}}),
    ]:
        if not path.exists():
            write_json(path, default)
    _sync_excel()
    activity.log(None, "BOOTSTRAP", "harness initialized")

    # Report
    print("=" * 60)
    print("BOOTSTRAP REPORT")
    print("=" * 60)
    print(f"Root:           {P.R}")
    print(f"Config:         {P.CONFIG_DIR}/(settings|scoring|automation-policy).yaml")
    print(f"Profile:        {'OK' if P.MASTER_PROFILE_MD.exists() else 'MISSING'} — {P.MASTER_PROFILE_MD}")
    print(f"Master resume:  {'OK' if P.MASTER_RESUME_PDF.exists() else 'MISSING (drop your PDF here)'}")
    print(f"Tracker:        {P.EXCEL_TRACKER}")

    ready, problems = _preflight_profile()
    print()
    if ready:
        print("Profile check: READY")
    else:
        print("Profile check: NOT READY — resolve these before /find-jobs or /apply:")
        for p in problems:
            print(f"  - {p}")

    cfg = Config.load()
    ms = modes.status(cfg)
    print()
    print(f"Mode: {ms.effective}  (policy.mode={ms.policy_mode}, "
          f"submission_allowed={ms.submission_allowed}, session_confirmed={ms.session_confirmed})")
    print(f"Playwright browser: {'/opt/pw-browsers/chromium'}"
          f" ({'FOUND' if Path('/opt/pw-browsers/chromium').exists() else 'MISSING'})")
    return 0


def cmd_status(args) -> int:
    cfg = Config.load()
    apps = _load_apps().get("applications", [])
    dash = _dashboard_counts(apps)
    print("STATUS")
    for k in ["Total Jobs", "Qualified Jobs", "Applications Prepared",
              "Applications Submitted", "Applications Failed",
              "Assessments", "Interviews", "Offers", "Rejections",
              "Follow-ups Due"]:
        print(f"  {k:<26} {dash[k]}")
    print()
    # Highest-priority opportunities: qualified jobs sorted by score
    qual = _load_jobs("qualified")
    if qual:
        top = sorted(qual, key=lambda j: -int(j.get("match_score", 0)))[:5]
        print("TOP OPPORTUNITIES")
        for j in top:
            print(f"  {j.get('match_score','?'):>3}% · {j.get('company','?')} — {j.get('role','?')}")
    # Required actions
    pending = [a for a in apps if a.get("status") == "READY_FOR_APPROVAL"]
    if pending:
        print("\nAWAITING APPROVAL")
        for a in pending:
            print(f"  {a['application_id']} · {a.get('company')} — {a.get('role')}")
    ms = modes.status(cfg)
    print(f"\nMode: {ms.effective} (policy={ms.policy_mode}, submission={ms.submission_allowed}, session={ms.session_confirmed})")
    return 0


def cmd_find_jobs(args) -> int:
    cfg = Config.load()
    n = int(args.count)
    activity.log(None, "DISCOVER_START", f"target={n}")
    jobs, warnings = discovery.discover_all(cfg, n)
    # Dedupe against archive + existing discovered
    seen = { (j.get("job_hash") or j.get("job_url")) for j in _load_jobs("archive") + _load_jobs("discovered") }
    fresh = [j for j in jobs if (j.get("job_hash") or j.get("job_url")) not in seen]
    all_discovered = _load_jobs("discovered") + fresh
    _save_jobs("discovered", all_discovered)
    activity.log(None, "DISCOVER_DONE", f"new={len(fresh)} total={len(all_discovered)}")
    print(f"Discovered {len(fresh)} new jobs (total pool: {len(all_discovered)}).")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
    return 0


def cmd_score(args) -> int:
    cfg = Config.load()
    profile = load_profile()
    ready, problems = profile.is_ready()
    if not ready:
        print("Cannot score — profile not ready:")
        for p in problems: print(f"  - {p}")
        return 2

    jobs = _load_jobs("discovered")
    target_hash = args.job
    updated = 0
    qualified = _load_jobs("qualified")
    rejected  = _load_jobs("rejected")
    qual_hashes = {j.get("job_hash") for j in qualified}
    rej_hashes = {j.get("job_hash") for j in rejected}

    for j in jobs:
        if target_hash and j.get("job_hash") != target_hash and j.get("requisition_id") != target_hash:
            continue
        s = scoring_mod.score_job(j, cfg, profile)
        j["match_score"] = s.total
        j["score_breakdown"] = s.breakdown
        j["score_rationale"] = s.rationale
        j["classification"] = s.classification
        updated += 1
        # Move into qualified / rejected buckets by threshold
        if s.total >= int(cfg.scoring.get("thresholds", {}).get("low", 70)):
            if j.get("job_hash") not in qual_hashes:
                qualified.append(j); qual_hashes.add(j.get("job_hash"))
        else:
            if j.get("job_hash") not in rej_hashes:
                rejected.append(j); rej_hashes.add(j.get("job_hash"))

    _save_jobs("discovered", jobs)
    _save_jobs("qualified", qualified)
    _save_jobs("rejected", rejected)
    activity.log(None, "SCORE_DONE", f"updated={updated}")
    print(f"Scored {updated} jobs. Qualified: {len(qualified)}. Rejected: {len(rejected)}.")
    return 0


def cmd_research(args) -> int:
    from .research import offline_brief
    b = offline_brief(args.company)
    print(json.dumps(b.__dict__, indent=2))
    return 0


def _find_qualified(job_id: str) -> dict | None:
    for j in _load_jobs("qualified"):
        if j.get("job_hash") == job_id or j.get("requisition_id") == job_id:
            return j
    return None


def cmd_prepare(args) -> int:
    cfg = Config.load()
    profile = load_profile()
    ready, problems = profile.is_ready()
    if not ready:
        print("Cannot prepare — profile not ready:")
        for p in problems: print(f"  - {p}")
        return 2

    job = _find_qualified(args.job_id)
    if not job:
        print(f"Job {args.job_id!r} not found in qualified list.")
        return 3

    resume_type, resume_reason = decide_mod.decide(job, int(job.get("match_score", 0)), cfg, profile)
    print(f"Resume decision: {resume_type.upper()} — {resume_reason}")

    resume_path: Path
    if resume_type == "master":
        resume_path = P.MASTER_RESUME_PDF
    else:
        tr = tailor_mod.tailor(job, profile)
        vr = validate_mod.validate(tr.markdown, profile)
        if not vr.ok:
            print(vr.report())
            return 4
        app_id_placeholder = batch_mod.mint_application_id()
        fname = f"{_slug(job.get('company','x'))}_{_slug(job.get('role','x'))}_{app_id_placeholder}.pdf"
        out = P.RESUMES_DIR / "tailored" / fname
        resume_path = render_mod.render(tr.markdown, out)
        job["_tailored_app_id"] = app_id_placeholder

    # Register application
    apps = _load_apps()
    app_id = job.get("_tailored_app_id") or batch_mod.mint_application_id()
    record = {
        "application_id":  app_id,
        "batch_id":        None,
        "company":         job.get("company"),
        "role":            job.get("role"),
        "job_url":         job.get("job_url"),
        "job_source":      job.get("source"),
        "location":        job.get("location"),
        "work_mode":       job.get("work_mode"),
        "match_score":     job.get("match_score"),
        "job_posted_date": job.get("posted_date"),
        "date_discovered": job.get("discovered_at"),
        "date_prepared":   dt.datetime.now().isoformat(timespec="seconds"),
        "date_applied":    None,
        "resume_type":     resume_type,
        "resume_file":     str(resume_path.name),
        "status":          "READY_FOR_APPROVAL",
        "ats_status":      None,
        "email_status":    None,
        "interview_stage": None,
        "recruiter":       None,
        "recruiter_url":   None,
        "followup_date":   None,
        "last_update":     dt.datetime.now().isoformat(timespec="seconds"),
        "next_action":     "AWAIT_APPROVAL",
        "notes":           resume_reason,
        "error_reason":    None,
        "candidate_name":  profile.name,
    }
    apps["applications"].append(record)
    _save_apps(apps)
    _sync_excel()
    activity.log(app_id, "PREPARED", f"resume={resume_type} file={resume_path.name}")
    print(f"Prepared {app_id} → status READY_FOR_APPROVAL.")
    print(f"Resume: {resume_path}")
    return 0


def cmd_apply(args) -> int:
    cfg = Config.load()
    ms = modes.status(cfg)
    qualified = _load_jobs("qualified")

    # Apply hard filters/policy
    min_score = args.score or cfg.min_score
    pool = [j for j in qualified if int(j.get("match_score", 0)) >= min_score]

    if args.role:
        import re as _re
        rx = _re.compile(args.role, _re.I)
        pool = [j for j in pool if rx.search(j.get("role", ""))]
    if args.location:
        import re as _re
        rx = _re.compile(args.location, _re.I)
        pool = [j for j in pool if rx.search(j.get("location", ""))]

    # Never re-apply
    applied_urls = { (a.get("job_url") or "") for a in _load_apps().get("applications", []) }
    pool = [j for j in pool if j.get("job_url") not in applied_urls]

    count = int(args.count)
    selected = (batch_mod.diversified_sample(pool, count) if args.random
                else sorted(pool, key=lambda j: -int(j.get("match_score", 0)))[:count])

    batch_id = batch_mod.mint_batch_id()
    print(f"Batch {batch_id}: {len(selected)} of {count} requested (pool={len(pool)}).")

    # Prepare each — the actual browser+approval loop is emitted as a
    # sequence of HARNESS_REQUEST envelopes the slash-command wrapper
    # handles. Here we do the resume prep and record READY_FOR_APPROVAL.
    prepared = 0
    for j in selected:
        r = _prepare_one(j, cfg, batch_id)
        prepared += 1 if r == 0 else 0

    print(f"Prepared {prepared} applications in {batch_id}.")
    print(f"Mode: {ms.effective}. Autosubmit: "
          f"{'ENABLED' if (ms.effective == 'autonomous' and cfg.submission_allowed) else 'DISABLED (supervised approval required)'}.")
    return 0


def _prepare_one(job: dict, cfg: Config, batch_id: str) -> int:
    class NS:  # tiny shim to reuse cmd_prepare
        pass
    ns = NS(); ns.job_id = job.get("job_hash") or job.get("requisition_id")
    rc = cmd_prepare(ns)
    if rc == 0:
        apps = _load_apps()
        for a in apps["applications"]:
            if a.get("application_id") and a.get("batch_id") is None \
               and a.get("job_url") == job.get("job_url"):
                a["batch_id"] = batch_id
        _save_apps(apps)
        _sync_excel()
    return rc


def cmd_sync(args) -> int:
    from .email.sync import build_search_requests, ingest_mailbox
    if args.ingest:
        r = ingest_mailbox(Path(args.ingest))
        print(json.dumps(r, indent=2))
        _sync_excel()
        activity.log(None, "SYNC_INGEST", json.dumps(r))
        return 0
    apps = _load_apps().get("applications", [])
    reqs = build_search_requests(apps)
    # Emit request envelopes; the slash-command wrapper handles them.
    for r in reqs:
        print(f"HARNESS_REQUEST: gmail_search {json.dumps(r)}")
    print(f"\nEmitted {len(reqs)} Gmail-search requests. Wrapper: collect results into a JSON "
          f"file (schema: {{\"messages\": [{{...}}]}}) and re-run `harness sync --ingest <path>`.")
    return 0


def cmd_followup(args) -> int:
    cfg = Config.load()
    apps = _load_apps().get("applications", [])
    today = dt.date.today().isoformat()
    due = [a for a in apps if a.get("followup_date") and a["followup_date"] <= today
           and a.get("status") in ("APPLIED", "SUBMITTED", "CONFIRMED")]
    for a in due:
        print(f"HARNESS_REQUEST: gmail_draft_followup {json.dumps({'app_id': a['application_id']})}")
    print(f"\n{len(due)} follow-ups due. Drafts must be reviewed and sent manually "
          f"(policy.allow_followups={cfg.policy.get('allow_followups')}).")
    return 0


def cmd_retry(args) -> int:
    apps = _load_apps()
    for a in apps["applications"]:
        if a.get("application_id") == args.app_id:
            a["status"] = "RETRY_PENDING"
            a["last_update"] = dt.datetime.now().isoformat(timespec="seconds")
            _save_apps(apps)
            _sync_excel()
            activity.log(args.app_id, "RETRY", "requested")
            print(f"Marked {args.app_id} for retry.")
            return 0
    print(f"{args.app_id!r} not found.")
    return 3


def cmd_stop(args) -> int:
    P.STATE_DIR.mkdir(parents=True, exist_ok=True)
    P.STOP_SENTINEL.write_text(dt.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    activity.log(None, "STOP", "sentinel written")
    print("STOP requested. The driver will halt at the next boundary.")
    return 0


def cmd_mode(args) -> int:
    cfg = Config.load()
    if args.action == "status":
        ms = modes.status(cfg)
        print(f"Effective: {ms.effective}")
        print(f"Policy mode: {ms.policy_mode}")
        print(f"Submission allowed (config): {ms.submission_allowed}")
        print(f"Session-confirmed autonomous: {ms.session_confirmed}")
        print(f"Daily cap: {ms.daily_used} / {ms.daily_limit}")
        print()
        print("Restrictions ALWAYS on:")
        print("  - stop_on_captcha / mfa / otp / login_verification")
        print("  - allow_interview_acceptance: false (hard-coded)")
        print("  - allow_offer_acceptance: false (hard-coded)")
        return 0
    if args.action == "supervised":
        modes.set_supervised()
        print("Mode → supervised. Session autonomous confirmation cleared.")
        return 0
    if args.action == "autonomous":
        # Enforce both locks BEFORE printing the prompt.
        if cfg.mode != "autonomous" or not cfg.submission_allowed:
            print("Refused. `automation-policy.yaml` must have BOTH `mode: autonomous` "
                  "AND `allow_application_submission: true` before this command can run.")
            print(f"Current: mode={cfg.mode}, allow_application_submission={cfg.submission_allowed}")
            return 5
        if args.confirm != "YES":
            print("AUTONOMOUS MODE will let the harness submit applications and send")
            print("approved messages without asking for each confirmation. It still stops for:")
            print("  CAPTCHA / MFA / OTP / login verification / unknown answers /")
            print("  salary or visa questions without a configured answer /")
            print("  legal attestations / demographic questions / any policy violation.")
            print()
            print("Confirm fully autonomous mode?")
            print("Re-run: `harness mode autonomous --confirm YES` to enable.")
            return 6
        modes.confirm_session_autonomous()
        print("Mode → autonomous (session-confirmed). Two locks satisfied.")
        return 0
    print(f"unknown mode action: {args.action!r}")
    return 2


# ---------------------------------------------------------------- utility

def _slug(s: str) -> str:
    import re as _re
    return _re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:40] or "x"


# ---------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("harness")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap").set_defaults(func=cmd_bootstrap)
    sub.add_parser("status").set_defaults(func=cmd_status)

    d = sub.add_parser("discover"); d.add_argument("--count", type=int, default=100); d.set_defaults(func=cmd_find_jobs)

    s = sub.add_parser("score"); s.add_argument("--job", default=None); s.set_defaults(func=cmd_score)

    r = sub.add_parser("research"); r.add_argument("company"); r.set_defaults(func=cmd_research)

    pr = sub.add_parser("prepare"); pr.add_argument("--job-id", dest="job_id", required=True); pr.set_defaults(func=cmd_prepare)

    ap = sub.add_parser("apply")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--random", action="store_true")
    ap.add_argument("--score", type=int, default=None)
    ap.add_argument("--role", default=None)
    ap.add_argument("--location", default=None)
    ap.set_defaults(func=cmd_apply)

    sy = sub.add_parser("sync"); sy.add_argument("--ingest", default=None); sy.set_defaults(func=cmd_sync)
    sub.add_parser("followup").set_defaults(func=cmd_followup)
    rt = sub.add_parser("retry"); rt.add_argument("app_id"); rt.set_defaults(func=cmd_retry)
    sub.add_parser("stop").set_defaults(func=cmd_stop)

    md = sub.add_parser("mode")
    md.add_argument("action", choices=["supervised", "autonomous", "status"])
    md.add_argument("--confirm", default=None)
    md.set_defaults(func=cmd_mode)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e!r}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
