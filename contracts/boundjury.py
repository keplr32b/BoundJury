# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
BoundJury — evidence-gated agent bounds for GenLayer (Projects).

Seal plain-English bounds. Anyone submits public HTTPS evidence of an action.
Consensus on IN_BOUND | OUT_OF_BOUND | INCONCLUSIVE.
Only OUT_OF_BOUND sets is_out_of_bound(action_id).
Challenge: only IN_BOUND (or owner_clear_out) lifts an out-flag;
INCONCLUSIVE on challenge preserves the out-flag.
"""

from genlayer import *
import json
import time

try:
    _UserError = gl.vm.UserError
except Exception:
    _UserError = Exception

CHALLENGE_SECS = 300


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise _UserError(msg)


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def parse_json_response(text: str) -> dict:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1:
        t = t[start : end + 1]
    return json.loads(t)


def _now() -> u256:
    return u256(int(time.time()))


def _host_of(url: str) -> str:
    u = (url or "").strip().lower()
    require(u.startswith("https://"), "only https urls allowed")
    rest = u[8:]
    host = rest.split("/")[0].split("?")[0].split("#")[0]
    require(len(host) > 0, "empty host")
    require("@" not in host, "userinfo not allowed")
    require(not host.replace(".", "").isdigit(), "ip literal hosts rejected")
    require("localhost" not in host, "localhost rejected")
    require(not host.endswith(".local"), "local tld rejected")
    return host


def _parse_urls(raw: str) -> list:
    url_list = [u.strip() for u in (raw or "").split(",") if u.strip()]
    require(1 <= len(url_list) <= 2, "need 1 or 2 comma-separated https urls")
    seen = {}
    for u in url_list:
        require(u not in seen, "duplicate url")
        seen[u] = True
        _host_of(u)
    return url_list


class BoundJury(gl.Contract):
    owner: Address
    allowed_hosts: TreeMap[str, bool]

    # agent_id -> registered / bounds / optional watch
    registered: TreeMap[str, bool]
    bounds_of: TreeMap[str, str]
    watch_url_of: TreeMap[str, str]

    # action_id -> case state
    action_agent_of: TreeMap[str, str]
    evidence_csv_of: TreeMap[str, str]
    has_evidence: TreeMap[str, bool]
    verdict_of: TreeMap[str, str]
    note_of: TreeMap[str, str]
    out_of_bound_of: TreeMap[str, bool]
    adjudicated_of: TreeMap[str, bool]
    challenge_open_of: TreeMap[str, bool]
    challenge_deadline_of: TreeMap[str, u256]
    finalized_of: TreeMap[str, bool]

    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.write
    def allow_host(self, host: str) -> None:
        require(gl.message.sender_address == self.owner, "only owner")
        h = (host or "").strip().lower()
        require(len(h) > 0, "empty host")
        require("://" not in h, "pass host only, not url")
        require("@" not in h, "userinfo not allowed")
        require(not h.replace(".", "").isdigit(), "ip literal rejected")
        self.allowed_hosts[h] = True

    @gl.public.write
    def register_agent(self, agent_id: str, bounds_text: str, watch_url: str) -> None:
        require(gl.message.sender_address == self.owner, "only owner")
        aid = (agent_id or "").strip()
        bounds = (bounds_text or "").strip()
        require(1 <= len(aid) <= 64, "bad agent_id")
        require(len(bounds) >= 20, "bounds too short")
        require(self.registered.get(aid, False) is not True, "already registered")
        w = (watch_url or "").strip()
        if len(w) > 0:
            host = _host_of(w)
            require(self.allowed_hosts.get(host, False) is True, "watch host not allowed: " + host)
            self.watch_url_of[aid] = w
        else:
            self.watch_url_of[aid] = ""
        self.registered[aid] = True
        self.bounds_of[aid] = bounds

    def _require_hosts_allowed(self, url_list: list) -> None:
        for u in url_list:
            host = _host_of(u)
            require(self.allowed_hosts.get(host, False) is True, "host not allowed: " + host)

    def _run_judgment(self, bounds: str, url_list: list) -> dict:
        urls_csv = ",".join(url_list)
        total = len(url_list)

        def judge() -> str:
            parts = []
            ok = 0
            for i, u in enumerate(url_list):
                try:
                    content = gl.nondet.web.render(u, mode="text")
                    snippet = (content[:3000] if content else "")
                    if snippet.strip():
                        ok += 1
                    else:
                        snippet = "[EMPTY PAGE]"
                except Exception as e:
                    snippet = ("[FETCH FAILED: " + str(e) + "]")[:240]
                parts.append("SOURCE " + str(i + 1) + " (" + u + "):\n---\n" + snippet + "\n---")
            block = "\n\n".join(parts)
            prompt = (
                "You adjudicate whether PUBLIC EVIDENCE shows an agent action "
                "stayed INSIDE or went OUTSIDE sealed bounds.\n\n"
                "SEALED BOUNDS:\n"
                + bounds
                + "\n\nEVIDENCE URLS: "
                + urls_csv
                + "\n\nEVIDENCE CONTENT:\n"
                + block
                + "\n\n"
                "Return ONLY strict JSON:\n"
                '{ "verdict": "IN_BOUND" or "OUT_OF_BOUND" or "INCONCLUSIVE", '
                '"note": "<short reason>" }\n'
                "Rules:\n"
                "- OUT_OF_BOUND only if readable evidence clearly shows a violation "
                "of the sealed bounds.\n"
                "- IN_BOUND if readable evidence clearly supports compliance with bounds.\n"
                "- INCONCLUSIVE if fetch failed, empty, unusable, or ambiguous.\n"
                "- If multiple sources, OUT_OF_BOUND only if the set as a whole supports a violation.\n"
            )
            raw = gl.nondet.exec_prompt(prompt)
            data = parse_json_response(raw)
            verdict = str(data.get("verdict", "")).strip().upper()
            if verdict not in ("IN_BOUND", "OUT_OF_BOUND", "INCONCLUSIVE"):
                verdict = "INCONCLUSIVE"
            if ok == 0 and verdict == "OUT_OF_BOUND":
                verdict = "INCONCLUSIVE"
            note = str(data.get("note", "")).strip()[:160]
            return canonical({"verdict": verdict, "note": note, "sources_count": total})

        principle = (
            "EQUIVALENT iff 'verdict' is identical (IN_BOUND, OUT_OF_BOUND, or INCONCLUSIVE) "
            "and sources_count is identical. note may differ. "
            "If verdict differs => NOT equivalent."
        )
        agreed = gl.eq_principle.prompt_comparative(judge, principle)
        parsed = json.loads(agreed)
        verdict = str(parsed["verdict"]).strip().upper()
        note = str(parsed.get("note", "")).strip()[:160]
        require(verdict in ("IN_BOUND", "OUT_OF_BOUND", "INCONCLUSIVE"), "bad verdict")
        require(int(parsed["sources_count"]) == total, "sources_count mismatch")
        return {"verdict": verdict, "note": note}

    def _apply_verdict(self, action_id: str, verdict: str, note: str, open_challenge: bool) -> str:
        self.verdict_of[action_id] = verdict
        self.note_of[action_id] = note
        self.adjudicated_of[action_id] = True
        if verdict == "OUT_OF_BOUND":
            self.out_of_bound_of[action_id] = True
            if open_challenge:
                self.challenge_open_of[action_id] = True
                self.challenge_deadline_of[action_id] = _now() + u256(CHALLENGE_SECS)
                self.finalized_of[action_id] = False
            else:
                self.challenge_open_of[action_id] = False
                self.finalized_of[action_id] = True
        else:
            self.out_of_bound_of[action_id] = False
            self.challenge_open_of[action_id] = False
            self.finalized_of[action_id] = False
        return verdict

    def _apply_challenge_verdict(self, action_id: str, verdict: str, note: str) -> str:
        """Only IN_BOUND lifts an existing out-flag. INCONCLUSIVE preserves it."""
        self.verdict_of[action_id] = verdict
        self.note_of[action_id] = note
        self.adjudicated_of[action_id] = True
        if verdict == "IN_BOUND":
            self.out_of_bound_of[action_id] = False
            self.challenge_open_of[action_id] = False
            self.finalized_of[action_id] = False
        elif verdict == "OUT_OF_BOUND":
            self.out_of_bound_of[action_id] = True
            self.challenge_open_of[action_id] = False
            self.finalized_of[action_id] = True
        else:
            self.out_of_bound_of[action_id] = True
            # challenge window unchanged
        return verdict

    @gl.public.write
    def submit_evidence(self, action_id: str, agent_id: str, urls_csv: str) -> None:
        aid = (action_id or "").strip()
        ag = (agent_id or "").strip()
        require(1 <= len(aid) <= 64, "bad action_id")
        require(self.registered.get(ag, False) is True, "unknown agent")
        require(self.out_of_bound_of.get(aid, False) is not True, "already out of bound")
        url_list = _parse_urls(urls_csv)
        self._require_hosts_allowed(url_list)
        self.action_agent_of[aid] = ag
        self.evidence_csv_of[aid] = ",".join(url_list)
        self.has_evidence[aid] = True
        self.adjudicated_of[aid] = False
        self.verdict_of[aid] = ""
        self.note_of[aid] = ""
        self.out_of_bound_of[aid] = False
        self.challenge_open_of[aid] = False
        self.finalized_of[aid] = False

    @gl.public.write
    def adjudicate(self, action_id: str) -> str:
        aid = (action_id or "").strip()
        require(self.has_evidence.get(aid, False) is True, "no evidence")
        require(self.adjudicated_of.get(aid, False) is not True, "already adjudicated")
        ag = self.action_agent_of.get(aid, "")
        require(self.registered.get(ag, False) is True, "unknown agent")
        url_list = _parse_urls(self.evidence_csv_of.get(aid, ""))
        self._require_hosts_allowed(url_list)
        bounds = self.bounds_of.get(ag, "")
        result = self._run_judgment(bounds, url_list)
        return self._apply_verdict(aid, result["verdict"], result["note"], open_challenge=True)

    @gl.public.write
    def challenge(self, action_id: str, url: str) -> str:
        aid = (action_id or "").strip()
        require(self.out_of_bound_of.get(aid, False) is True, "not out of bound")
        require(self.challenge_open_of.get(aid, False) is True, "challenge closed")
        require(self.finalized_of.get(aid, False) is not True, "already finalized")
        require(_now() <= self.challenge_deadline_of.get(aid, u256(0)), "challenge window elapsed")
        u = (url or "").strip()
        host = _host_of(u)
        require(self.allowed_hosts.get(host, False) is True, "host not allowed: " + host)
        ag = self.action_agent_of.get(aid, "")
        bounds = self.bounds_of.get(ag, "")
        result = self._run_judgment(bounds, [u])
        return self._apply_challenge_verdict(aid, result["verdict"], result["note"])

    @gl.public.write
    def finalize_out(self, action_id: str) -> None:
        aid = (action_id or "").strip()
        require(self.out_of_bound_of.get(aid, False) is True, "not out of bound")
        require(self.challenge_open_of.get(aid, False) is True, "challenge not open")
        require(_now() > self.challenge_deadline_of.get(aid, u256(0)), "window still open")
        self.challenge_open_of[aid] = False
        self.finalized_of[aid] = True

    @gl.public.write
    def recheck(self, action_id: str) -> str:
        aid = (action_id or "").strip()
        ag = self.action_agent_of.get(aid, "")
        require(self.registered.get(ag, False) is True, "unknown agent")
        require(self.out_of_bound_of.get(aid, False) is not True, "already out of bound")
        w = self.watch_url_of.get(ag, "")
        require(len(w) > 0, "no watch url")
        host = _host_of(w)
        require(self.allowed_hosts.get(host, False) is True, "host not allowed: " + host)
        bounds = self.bounds_of.get(ag, "")
        result = self._run_judgment(bounds, [w])
        return self._apply_verdict(aid, result["verdict"], result["note"], open_challenge=True)

    @gl.public.write
    def owner_clear_out(self, action_id: str) -> None:
        require(gl.message.sender_address == self.owner, "only owner")
        aid = (action_id or "").strip()
        require(self.out_of_bound_of.get(aid, False) is True, "not out of bound")
        self.out_of_bound_of[aid] = False
        self.verdict_of[aid] = "CLEARED_BY_OWNER"
        self.note_of[aid] = "owner cleared out-of-bound flag"
        self.challenge_open_of[aid] = False
        self.finalized_of[aid] = False

    @gl.public.view
    def is_out_of_bound(self, action_id: str) -> bool:
        aid = (action_id or "").strip()
        return self.out_of_bound_of.get(aid, False) is True

    @gl.public.view
    def read_case(self, action_id: str) -> str:
        aid = (action_id or "").strip()
        require(self.has_evidence.get(aid, False) is True or self.adjudicated_of.get(aid, False) is True, "unknown action")
        return canonical(
            {
                "action_id": aid,
                "agent_id": self.action_agent_of.get(aid, ""),
                "has_evidence": bool(self.has_evidence.get(aid, False)),
                "evidence_csv": self.evidence_csv_of.get(aid, ""),
                "adjudicated": bool(self.adjudicated_of.get(aid, False)),
                "verdict": self.verdict_of.get(aid, ""),
                "note": self.note_of.get(aid, ""),
                "out_of_bound": bool(self.out_of_bound_of.get(aid, False)),
                "challenge_open": bool(self.challenge_open_of.get(aid, False)),
                "challenge_deadline": int(self.challenge_deadline_of.get(aid, u256(0))),
                "finalized": bool(self.finalized_of.get(aid, False)),
            }
        )

    @gl.public.view
    def get_owner(self) -> Address:
        return self.owner

    @gl.public.view
    def is_host_allowed(self, host: str) -> bool:
        h = (host or "").strip().lower()
        return self.allowed_hosts.get(h, False) is True