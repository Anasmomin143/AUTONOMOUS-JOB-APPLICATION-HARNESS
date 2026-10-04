"""Generic application-form engine (spec §12–13).

Scans the application form's visible controls with their question text,
fills each from the profile (identity fields), the recorded resume, or
messages/screening-answers.yaml, and verifies every fill by reading the
value back. Anything it cannot answer from those sources is returned as
unresolved — never guessed.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..profile import ProfileFacts
from . import answers as answers_mod

# Marks every control with data-harness-id and returns a descriptor per
# control inside the application form (the <form> holding a file input or
# the most fields; the whole document if there is no <form>).
_SCAN_JS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const textOf = el => el ? norm(el.innerText || el.textContent) : '';
  const controlsIn = r => Array.from(r.querySelectorAll('input, select, textarea'))
      .filter(c => (c.type || '') !== 'hidden');
  const forms = Array.from(document.forms).filter(f => controlsIn(f).length);
  let root = document;
  if (forms.length) {
    const withFile = forms.filter(f => f.querySelector('input[type=file]'));
    const pool = withFile.length ? withFile : forms;
    root = pool.reduce((a, b) => controlsIn(b).length > controlsIn(a).length ? b : a);
  }
  document.querySelectorAll('[data-harness-root]').forEach(e => e.removeAttribute('data-harness-root'));
  document.querySelectorAll('[data-harness-id]').forEach(e => e.removeAttribute('data-harness-id'));
  if (root !== document) root.setAttribute('data-harness-root', '1');

  const shown = el => {
    if (!el || el.getAttribute('aria-hidden') === 'true') return false;
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0
        && r.width > 1 && r.height > 1;
  };
  const ownLabel = el => {
    if (el.labels && el.labels.length) {
      const l = el.labels[0].cloneNode(true);
      l.querySelectorAll('input, select, textarea').forEach(n => n.remove());
      const t = textOf(l);
      if (t) return t;
    }
    const al = el.getAttribute('aria-label');
    if (al) return norm(al);
    const lb = el.getAttribute('aria-labelledby');
    if (lb) return norm(lb.split(/\s+/).map(id => textOf(document.getElementById(id))).join(' '));
    return '';
  };
  // Nearest label/legend in an ancestor that is not tied to another control.
  const contextLabel = el => {
    let a = el.parentElement;
    for (let i = 0; i < 4 && a && a !== root.parentElement; i++, a = a.parentElement) {
      for (const l of a.querySelectorAll('label, legend')) {
        if (l.contains(el)) continue;
        if (l.control && l.control !== el) continue;
        const t = textOf(l);
        if (t) return t;
      }
    }
    return '';
  };
  const groupQuestion = el => {
    const fs = el.closest('fieldset');
    if (fs) { const lg = fs.querySelector('legend'); if (lg && textOf(lg)) return textOf(lg); }
    const g = el.closest('[role=radiogroup], [role=group]');
    if (g && ownLabel(g)) return ownLabel(g);
    let a = el.parentElement;
    for (let i = 0; i < 4 && a; i++, a = a.parentElement) {
      for (const l of a.querySelectorAll('label, legend')) {
        if (l.contains(el) || (l.control && ['radio', 'checkbox'].includes(l.control.type))) continue;
        const t = textOf(l);
        if (t) return t;
      }
    }
    return '';
  };

  const out = [];
  let n = 0;
  for (const el of root.querySelectorAll('input, select, textarea')) {
    const type = (el.tagName === 'INPUT' ? (el.getAttribute('type') || 'text') : el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image', 'search'].includes(type) || el.disabled) continue;
    const choice = type === 'radio' || type === 'checkbox';
    const visible = shown(el) || (choice && el.labels && el.labels.length && shown(el.labels[0]));
    if (type !== 'file' && !visible) continue;
    const hid = String(n++);
    el.setAttribute('data-harness-id', hid);
    const d = {
      hid, type, tag: el.tagName.toLowerCase(), name: el.name || '', id: el.id || '',
      required: el.required || el.getAttribute('aria-required') === 'true',
      label: ownLabel(el) || contextLabel(el) || norm(el.placeholder) || '',
      combobox: el.getAttribute('role') === 'combobox' || el.hasAttribute('aria-autocomplete'),
    };
    if (choice) {
      d.question = groupQuestion(el);
      d.checked = el.checked;
      d.group_size = el.name ? root.querySelectorAll(`input[type=${type}][name="${CSS.escape(el.name)}"]`).length : 1;
    } else if (el.tagName === 'SELECT') {
      d.options = Array.from(el.options).map(o => ({value: o.value, label: norm(o.text)}));
      d.value = el.value;
    } else if (type === 'file') {
      d.files = Array.from(el.files || []).map(f => f.name);
    } else {
      d.value = el.value;
    }
    out.push(d);
  }
  return out;
}
"""

_PLACEHOLDER_RX = re.compile(r"^(select|choose|please select|--|—|-)", re.I)
_RESUME_RX = re.compile(r"(?i)resume|\bcv\b|curriculum")
_COVER_RX = re.compile(r"(?i)cover")
CONFIRM_RX = re.compile(
    r"(?i)(thank(s| you) for (applying|your application|submitting)|"
    r"application (has been |was )?(received|submitted|sent)|"
    r"we('ve| have) received your application|successfully (applied|submitted))"
)


@dataclass
class Question:
    key: str              # stable across scans: kind + id / name / label
    kind: str             # text | textarea | select | radio | checkbox | checkbox_group | file | combobox
    label: str
    required: bool
    hids: list[str]       # one per control (one per option for radio / checkbox groups)
    name: str = ""
    id: str = ""
    options: list[str] = field(default_factory=list)  # select / radio / checkbox-group labels
    values: list[str] = field(default_factory=list)   # select option values
    current: str = ""     # human-readable current value; "" = empty

    @property
    def ident(self) -> str:
        return f"{self.label} {self.name} {self.id}"


@dataclass
class Row:
    label: str
    value: str
    source: str


@dataclass
class FormResult:
    rows: list[Row]
    unresolved: list[dict]


def _norm(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def scan(page) -> list[Question]:
    questions: list[Question] = []
    groups: dict[str, Question] = {}
    for c in page.evaluate(_SCAN_JS):
        t = c["type"]
        ident = c["id"] or c["name"] or c["label"] or c["hid"]
        if t == "radio" or (t == "checkbox" and c.get("group_size", 1) > 1):
            kind = "radio" if t == "radio" else "checkbox_group"
            key = f"{kind}:{c['name'] or c['hid']}"
            q = groups.get(key)
            if q is None:
                q = Question(key, kind, c.get("question") or c["name"], False, [], c["name"], "")
                groups[key] = q
                questions.append(q)
            q.hids.append(c["hid"])
            q.options.append(c["label"])
            q.required = q.required or c["required"]
            if c["checked"]:
                q.current = ", ".join(filter(None, [q.current, c["label"]]))
        elif t == "checkbox":
            questions.append(Question(f"checkbox:{ident}", "checkbox", c["label"] or c.get("question", ""),
                                      c["required"], [c["hid"]], c["name"], c["id"],
                                      current="checked" if c["checked"] else ""))
        elif c["tag"] == "select":
            opts = c.get("options") or []
            current = next((o["label"] for o in opts if o["value"] == c.get("value")), "")
            if not c.get("value") or _PLACEHOLDER_RX.match(current):
                current = ""
            questions.append(Question(f"select:{ident}", "select", c["label"], c["required"], [c["hid"]],
                                      c["name"], c["id"], [o["label"] for o in opts],
                                      [o["value"] for o in opts], current))
        elif t == "file":
            questions.append(Question(f"file:{ident}", "file", c["label"], c["required"], [c["hid"]],
                                      c["name"], c["id"], current=", ".join(c.get("files") or [])))
        else:
            kind = "combobox" if c.get("combobox") else ("textarea" if c["tag"] == "textarea" else "text")
            questions.append(Question(f"{kind}:{ident}", kind, c["label"], c["required"], [c["hid"]],
                                      c["name"], c["id"], current=c.get("value") or ""))
    return questions


def standard_key(q: Question) -> str | None:
    """Identity fields answered from the profile."""
    label = _norm(q.label)
    both = _norm(q.ident)
    if re.search(r"\bfirst[\s_-]*name\b|\bgiven[\s_-]*name\b|\bfname\b", both):
        return "first_name"
    if re.search(r"\blast[\s_-]*name\b|\bsurname\b|\bfamily[\s_-]*name\b|\blname\b", both):
        return "last_name"
    if re.match(r"(full |legal |your )?name\b", label) or q.name.lower() in ("name", "full_name", "fullname"):
        return "full_name"
    if re.search(r"e-?mail", both):
        return "email"
    if re.search(r"\b(phone|mobile|tel)\b", both):
        return "phone"
    if re.search(r"linked\s*in", both):
        return "linkedin"
    if re.search(r"git\s*hub|\bwebsite\b|\bportfolio\b", both):
        return "github"
    return None


def _profile_value(key: str, profile: ProfileFacts) -> str:
    return {
        "first_name": profile.first_name, "last_name": profile.last_name, "full_name": profile.name,
        "email": profile.email, "phone": profile.phone,
        "linkedin": profile.linkedin_url, "github": profile.github_url,
    }[key]


def pick_option(answer: str, options: list[str]) -> int | None:
    """Index of the one option that `answer` selects, else None. Tries an
    exact match, then answer-starts-with-option ("Yes — for roles outside
    India." picks "Yes"), then option-starts-with-answer. Ambiguity is None."""
    a = _norm(answer)
    cands = [(i, _norm(o)) for i, o in enumerate(options) if _norm(o) and not _PLACEHOLDER_RX.match(_norm(o))]
    tiers = [
        [i for i, o in cands if o == a],
        [i for i, o in cands if a.startswith(o) and not a[len(o):len(o) + 1].isalnum()],
        [i for i, o in cands if o.startswith(a) and not o[len(a):len(a) + 1].isalnum()],
    ]
    for tier in tiers:
        if len(tier) == 1:
            return tier[0]
        if len(tier) > 1:
            return None
    return None


def _resolve(q: Question, profile: ProfileFacts, rules, resume: Path) -> tuple[str | None, str | None, str]:
    """(source, answer, reason-if-unanswerable)."""
    if q.kind == "file":
        if _RESUME_RX.search(q.ident):
            return "resume", str(resume), ""
        if _COVER_RX.search(q.ident):
            return None, None, "cover-letter upload (allow_cover_letters is off)"
        return None, None, "file upload with no configured answer"
    if q.kind in ("text", "textarea"):
        key = standard_key(q)
        if key:
            value = _profile_value(key, profile)
            return ("profile", value, "") if value else (None, None, f"master-profile.md has no {key}")
    answer = answers_mod.match(q.label or q.ident, rules)
    if answer is None:
        return None, None, "no answer in screening-answers.yaml"
    if answer == answers_mod.STOP_FOR_USER:
        return None, None, "screening-answers.yaml says always ask you"
    return "screening-answers.yaml", answer, ""


def _check(loc) -> None:
    try:
        loc.check(timeout=3000)
    except Exception:
        loc.check(force=True)  # custom-styled inputs hide the native control


def _apply(page, q: Question, answer: str) -> tuple[bool, str]:
    """Fill `q` and verify by reading back. (ok, display value or reason)."""
    def loc(hid: str):
        return page.locator(f'[data-harness-id="{hid}"]')

    try:
        if q.kind == "file":
            loc(q.hids[0]).set_input_files(answer)
            ok = loc(q.hids[0]).evaluate("e => e.files.length") == 1
            return ok, (Path(answer).name if ok else "upload did not register")
        if q.kind in ("text", "textarea"):
            loc(q.hids[0]).fill(answer)
            ok = loc(q.hids[0]).input_value() == answer
            return ok, (answer if ok else "value did not stick after filling")
        if q.kind == "combobox":
            return False, "custom dropdown — set it in the browser, then reply CONTINUE"
        if q.kind == "select":
            i = pick_option(answer, q.options)
            if i is None:
                return False, f"answer {answer!r} matches none of the options {q.options}"
            loc(q.hids[0]).select_option(value=q.values[i])
            ok = loc(q.hids[0]).input_value() == q.values[i]
            return ok, (q.options[i] if ok else "selection did not stick")
        if q.kind in ("radio", "checkbox_group"):
            i = pick_option(answer, q.options)
            if i is None:
                return False, f"answer {answer!r} matches none of the options {q.options}"
            _check(loc(q.hids[i]))
            ok = loc(q.hids[i]).is_checked()
            return ok, (q.options[i] if ok else "option did not stay checked")
        if q.kind == "checkbox":
            a = _norm(answer)
            if a.startswith(("yes", "true")):
                _check(loc(q.hids[0]))
                ok = loc(q.hids[0]).is_checked()
                return ok, ("checked" if ok else "box did not stay checked")
            if a.startswith(("no", "false")):
                return True, "left unchecked"
            return False, f"answer {answer!r} is not yes/no for a checkbox"
    except Exception as e:
        return False, f"could not fill: {e.__class__.__name__}"
    return False, f"unsupported field type {q.kind}"


def fill_form(page, profile: ProfileFacts, rules, resume: Path, *,
              accept_blank: bool = False, sources: dict[str, str] | None = None,
              max_passes: int = 4) -> FormResult:
    """Fill every empty control it can answer; re-scan after changes so
    follow-up questions revealed by an answer are handled too. Fields that
    already hold a value (ours, the page's, or the user's) are never
    overwritten. With `accept_blank`, empty optional fields and custom
    dropdowns the user was asked to set are accepted as they are."""
    sources = sources if sources is not None else {}
    for _ in range(max_passes):
        rows: list[Row] = []
        unresolved: list[dict] = []
        changed = False
        for q in scan(page):
            if q.current:
                rows.append(Row(q.label, q.current, sources.get(q.key, "already on the page")))
                continue
            source, answer, reason = _resolve(q, profile, rules, resume)
            if answer is not None:
                ok, detail = _apply(page, q, answer)
                if ok:
                    sources[q.key] = source
                    rows.append(Row(q.label, detail, source))
                    changed = True
                    continue
                reason = detail
            if accept_blank and q.kind == "combobox":
                rows.append(Row(q.label, "(set by you in the browser — not verified)", "you"))
            elif accept_blank and not q.required:
                rows.append(Row(q.label, "(left blank — optional)", "you"))
            else:
                unresolved.append({"question": q.label or q.ident.strip(), "reason": reason,
                                   "required": q.required})
        if not changed:
            break
    return FormResult(rows, unresolved)


def has_form(page) -> bool:
    return any(q.kind == "file" or standard_key(q) == "email" for q in scan(page))


def find_submit(page):
    scope = page.locator("[data-harness-root]") if page.locator("[data-harness-root]").count() else page
    # Explicit submit controls and "Submit" labels before untyped buttons,
    # which forms also use for "Attach", "Add another", etc.
    for sel in ("button[type=submit]", "input[type=submit]",
                "button:has-text('Submit application')", "button:has-text('Submit')",
                "[role=button]:has-text('Submit')", "button:not([type])"):
        loc = scope.locator(sel)
        for i in range(loc.count()):
            if loc.nth(i).is_visible():
                return loc.nth(i)
    return None


def click_apply_button(page) -> bool:
    """Open the form from a job-description page ("Apply", "Apply now")."""
    loc = page.get_by_role("link", name=re.compile(r"^\s*apply( now| for this (job|position))?\s*$", re.I))
    if not loc.count():
        loc = page.get_by_role("button", name=re.compile(r"^\s*apply( now| for this (job|position))?\s*$", re.I))
    for i in range(loc.count()):
        if loc.nth(i).is_visible():
            loc.nth(i).click()
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            return True
    return False


def page_text(page) -> str:
    try:
        return page.evaluate("() => document.body ? document.body.innerText.slice(0, 20000) : ''") or ""
    except Exception:
        return ""


def confirmation(page, before_text: str, before_url: str) -> tuple[bool, str]:
    """Did the submit land on a confirmation? Text that was already on
    the form page doesn't count unless the page changed."""
    text = page_text(page)
    m = CONFIRM_RX.search(text)
    if m and (not CONFIRM_RX.search(before_text) or page.url != before_url):
        return True, f"confirmation text {m.group(0)!r} at {page.url}"
    still_form = has_form(page)
    return False, (f"no confirmation found at {page.url}"
                   + ("; the application form is still showing (validation errors?)" if still_form else ""))
