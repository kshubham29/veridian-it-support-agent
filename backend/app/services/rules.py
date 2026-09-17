"""Deterministic policy engine (a.k.a. Demo / Mock mode agent).

This module is the *decision core* of the agent. It is used:
  * as the full agent when no LLM API key is configured (Demo Mode), and
  * as the guardrail/fallback validator when an LLM is configured.

Every decision it makes is grounded in an article from data/knowledge_base.json.
It never invents a policy: if no policy covers the request, it says so and
routes the case to a human.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import retrieval

SECURITY_EMAIL = "security@veridian-corp.example"

AFFIRMATIVE = {"yes", "yep", "yeah", "y", "correct", "true", "it is", "yes it is", "sure", "affirmative", "yes please"}
NEGATIVE = {"no", "nope", "n", "not yet", "no i haven't", "negative", "havent", "haven't"}

# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

CATEGORY_PATTERNS: List[tuple] = [
    (
        "Security Incident",
        [
            r"phish", r"malware", r"ransomware", r"\bvirus\b", r"unauthori[sz]ed access",
            r"suspicious (email|login|link|message|activity)", r"\bhacked\b", r"spoof",
            r"(email|mail|message).{0,40}(asking|asks|requesting).{0,20}(login|password|credential)",
            r"someone (logged|signed) in", r"security incident",
        ],
    ),
    (
        "Guest Wi-Fi",
        [r"guest (wi-?fi|wifi|network|internet)", r"(wi-?fi|wifi).{0,25}(guest|visitor)", r"visitor.{0,20}(wi-?fi|wifi|internet)"],
    ),
    (
        "Finance/Expense",
        [r"expense (tool|system|software|app|management)", r"expense", r"reimbursement"],
    ),
    (
        "WFH Equipment",
        [
            r"work(ing)? from home", r"\bwfh\b", r"home office", r"remote.{0,25}(monitor|chair|equipment)",
            r"(monitor|chair).{0,30}(home|remote|wfh)",
        ],
    ),
    (
        "Access Request",
        [
            r"admin (access|rights|privileg)", r"administrator (access|rights)", r"root access",
            r"elevated (access|privileg)", r"access to the .{0,30}server", r"privileged access",
        ],
    ),
    ("VPN", [r"\bvpn\b", r"remote access client"]),
    (
        "Password",
        [
            r"password", r"locked out", r"lock(ed)? out of my account", r"account (is )?locked",
            r"reset my (password|credentials)", r"can'?t (log|sign) in to my (account|laptop|computer)",
        ],
    ),
    (
        "Printer",
        [r"printer", r"printing", r"print(er)? queue", r"paper jam", r"spooler"],
    ),
    (
        "Email/Mailbox",
        [
            r"mailbox", r"mail box", r"(email|mail).{0,20}(quota|full|storage|space)",
            r"can'?t send (email|mail)", r"outlook.{0,20}(full|quota)", r"archive (old )?mail",
        ],
    ),
    (
        "Laptop/Hardware",
        [
            r"laptop", r"\bmachine\b", r"\bdevice\b", r"computer", r"\bscreen\b", r"keyboard",
            r"\bdock(ing)? station\b", r"hardware",
        ],
    ),
    (
        "Software",
        [
            r"install", r"installation", r"software", r"application", r"browser extension",
            r"plugin", r"catalog", r"licen[cs]e",
        ],
    ),
]


def classify(text: str) -> str:
    t = text.lower()
    for category, patterns in CATEGORY_PATTERNS:
        if not patterns:
            continue
        for pattern in patterns:
            if re.search(pattern, t):
                return category
    return "Unknown"


# --------------------------------------------------------------------------- #
# Slot extraction
# --------------------------------------------------------------------------- #

HARDWARE_FAILURE_HINTS = [
    r"won'?t turn on", r"will not turn on", r"not turning on", r"\bdead\b", r"no power",
    r"doesn'?t boot", r"won'?t boot", r"flicker", r"cracked", r"broken", r"blue screen",
    r"overheat", r"not charging", r"battery (dead|swollen|failed)", r"hardware failure",
]


def _is_affirmative(msg: str) -> Optional[bool]:
    m = msg.strip().lower().rstrip(".!")
    if m in AFFIRMATIVE or m.startswith("yes"):
        return True
    if m in NEGATIVE or m.startswith("no ") or m == "no" or m.startswith("not "):
        return False
    return None


def extract_slots(text: str, slots: Dict) -> Dict:
    """Pull structured facts out of the whole conversation text."""
    t = text.lower()

    # employment type
    if re.search(r"contractor|contract staff|consultant|vendor staff|new joiner.{0,30}contractor", t):
        slots["employment_type"] = "contractor"
    elif re.search(r"full[- ]?time|permanent employee|\bfte\b|i am an employee|full time", t):
        slots.setdefault("employment_type", "full-time")

    # laptop age in years
    age = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?|yr)\b", t)
    if age:
        slots["laptop_age_years"] = float(age.group(1))

    # hardware failure
    for pattern in HARDWARE_FAILURE_HINTS:
        if re.search(pattern, t):
            slots["hardware_failure"] = True
            break

    # VPN symptom
    if re.search(r"credential[s]? (have )?expired|expired credential|password expired|expiry|expired", t) and "vpn" in t:
        slots["vpn_expired"] = True

    # software catalog status
    if re.search(r"not in the (approved )?(software )?catalog|non[- ]catalog|isn'?t in the catalog|not listed in the catalog", t):
        slots["in_catalog"] = False
    elif re.search(r"(it'?s|is) in the (approved )?catalog|listed in the catalog|standard software", t):
        slots["in_catalog"] = True

    # printer troubleshooting
    if re.search(r"restarted the (print )?spooler|restarted the spooler|already restarted|tried restarting", t):
        slots["spooler_restarted"] = True
    tag = re.search(r"asset tag[:\s#]*([a-z0-9\-]{3,})", t)
    if tag:
        slots["asset_tag"] = tag.group(1).upper()

    # mailbox
    if re.search(r"increase|more space|raise (the )?quota|bigger mailbox|extend (the )?quota|50 ?gb", t):
        slots["wants_quota_increase"] = True

    # remote days per week
    days = re.search(r"(\d)\s*(?:days?)\s*(?:a|per)?\s*week", t)
    if days:
        slots["remote_days"] = int(days.group(1))

    # expense account
    if re.search(r"(i )?(already )?have an account|account already exists|my account works|i had an account", t):
        slots["expense_account_exists"] = True
    elif re.search(r"(i )?(don'?t|do not) have an account|no account|never had an account|new access", t):
        slots["expense_account_exists"] = False

    # forwarding a suspicious email
    if re.search(r"forward(ing|ed)?", t):
        slots["mentions_forwarding"] = True

    return slots


def apply_pending_answer(pending_slot: str, message: str, slots: Dict) -> None:
    """Interpret a short answer (e.g. 'yes') in the context of the last question."""
    answer = _is_affirmative(message)
    if pending_slot == "employment_type":
        if re.search(r"contract", message.lower()):
            slots["employment_type"] = "contractor"
        elif re.search(r"full|permanent|fte", message.lower()):
            slots["employment_type"] = "full-time"
    elif pending_slot == "vpn_expired" and answer is not None:
        slots["vpn_expired"] = answer
    elif pending_slot == "hardware_failure" and answer is not None:
        slots["hardware_failure"] = answer
    elif pending_slot == "in_catalog" and answer is not None:
        slots["in_catalog"] = answer
    elif pending_slot == "spooler_restarted" and answer is not None:
        slots["spooler_restarted"] = answer
    elif pending_slot == "expense_account_exists" and answer is not None:
        slots["expense_account_exists"] = answer
    elif pending_slot == "wants_quota_increase" and answer is not None:
        slots["wants_quota_increase"] = answer
    elif pending_slot == "asset_tag":
        tag = re.search(r"([a-z0-9]{2,}-?[a-z0-9]{2,})", message.lower())
        if tag:
            slots["asset_tag"] = tag.group(1).upper()


# --------------------------------------------------------------------------- #
# Decision helpers
# --------------------------------------------------------------------------- #


def _decision(**kwargs) -> Dict:
    base = {
        "category": "Unknown",
        "intent": "unclassified",
        "response": "",
        "action": "FOLLOW_UP",
        "priority": "MEDIUM",
        "source_ids": [],
        "needs_follow_up": False,
        "follow_up_question": None,
        "ticket_required": False,
        "escalation_required": False,
        "assigned_team": "IT Service Desk",
        "confidence": 0.8,
        "policy_conflict": None,
        "precedent_ticket_ids": [],
        "pending_slot": None,
        "ticket_status": None,
        "issue_summary": None,
    }
    base.update(kwargs)
    return base


def _follow_up(category: str, question: str, slot: str, sources: List[str], intent: str) -> Dict:
    return _decision(
        category=category,
        intent=intent,
        response=question,
        action="FOLLOW_UP",
        needs_follow_up=True,
        follow_up_question=question,
        source_ids=sources,
        pending_slot=slot,
        confidence=0.6,
    )


# --------------------------------------------------------------------------- #
# Category rules
# --------------------------------------------------------------------------- #


def rule_security(text: str, slots: Dict) -> Dict:
    forwarding = slots.get("mentions_forwarding")
    lines = [
        "This looks like a suspected security incident, so I am treating it as HIGH priority.",
        f"**Do not forward the email to other employees.** Report it immediately to **{SECURITY_EMAIL}**.",
    ]
    if forwarding:
        lines.insert(
            1,
            "Please stop forwarding it now and ask anyone who already received it not to click any links or reply.",
        )
    lines.append(
        "I have escalated this to the Security team and raised a ticket - Security will contact you. "
        "This is escalated, not resolved."
    )
    return _decision(
        category="Security Incident",
        intent="suspected_phishing",
        response="\n\n".join(lines),
        action="ESCALATE",
        priority="HIGH",
        source_ids=["KB-09"],
        ticket_required=True,
        escalation_required=True,
        assigned_team="Security",
        confidence=0.97,
        ticket_status="Escalated",
        issue_summary="Suspected phishing / security incident reported by employee",
        precedent_ticket_ids=["TK-1048"],
    )


def rule_password(text: str, slots: Dict) -> Dict:
    t = text.lower()
    attempts = re.search(r"(\d+)\s*(?:times|attempts|tries)", t)
    attempt_count = int(attempts.group(1)) if attempts else None
    locked = bool(re.search(r"locked out|account (is )?locked|lock(ed)? me out", t)) or (
        attempt_count is not None and attempt_count >= 5
    )
    if locked:
        detail = f" after {attempt_count} failed attempts" if attempt_count else ""
        return _decision(
            category="Password",
            intent="account_lockout",
            response=(
                f"Your account is locked{detail}. Per policy, an account locked after 5 failed attempts "
                "must be unlocked manually by IT - self-service reset will not clear the lock.\n\n"
                "No approval is required. I have raised a ticket with the IT Service Desk to unlock your account; "
                "once unlocked you can reset your password yourself via the self-service portal."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-01"],
            ticket_required=True,
            assigned_team="IT Service Desk",
            confidence=0.95,
            ticket_status="In Progress",
            issue_summary="Account locked after repeated failed password attempts - manual unlock required",
            precedent_ticket_ids=["TK-1049"],
        )
    return _decision(
        category="Password",
        intent="password_reset_self_service",
        response=(
            "You can reset your password yourself at any time from the self-service portal - no approval or "
            "ticket is needed. Note that after 5 failed sign-in attempts the account locks and IT has to unlock "
            "it manually, so use the portal rather than retrying."
        ),
        action="RESOLVE",
        priority="LOW",
        source_ids=["KB-01"],
        confidence=0.9,
        issue_summary="Password reset guidance",
    )


def rule_vpn(text: str, slots: Dict) -> Dict:
    t = text.lower()
    new_access = bool(
        re.search(r"new (contractor|joiner|hire|starter)|needs? vpn access|get vpn access|grant vpn|request vpn", t)
    )
    employment = slots.get("employment_type")

    if employment == "contractor" or re.search(r"contractor", t):
        return _decision(
            category="VPN",
            intent="contractor_vpn_access",
            response=(
                "Contractors are not granted VPN access automatically. Manager approval is required and must be "
                "submitted via the **access request form**.\n\n"
                "I have raised an access request ticket in *Pending Approval* status. It will move forward once the "
                "manager approval is recorded. Also note VPN credentials expire every 90 days and the contractor "
                "will need to renew them."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-02"],
            ticket_required=True,
            assigned_team="IT Access Management",
            confidence=0.94,
            ticket_status="Pending Approval",
            issue_summary="VPN access request for a contractor - manager approval required",
        )

    if slots.get("vpn_expired"):
        return _decision(
            category="VPN",
            intent="credential_expired",
            response=(
                "VPN credentials expire every 90 days and must be renewed by the employee - that matches the "
                "'credentials expired' message you are seeing. VPN access itself is automatic for full-time "
                "employees, so no approval or new request is needed: renew your credentials and reconnect.\n\n"
                "If renewal fails, tell me and I will raise a ticket with the IT Service Desk."
            ),
            action="RESOLVE",
            priority="MEDIUM",
            source_ids=["KB-02"],
            confidence=0.93,
            issue_summary="VPN credentials expired - self-renewal",
            precedent_ticket_ids=["TK-1042"],
        )

    if new_access and not employment:
        return _follow_up(
            "VPN",
            "Is this for a full-time employee or a contractor? Contractors need manager approval via the access request form.",
            "employment_type",
            ["KB-02"],
            "vpn_access_request",
        )

    if slots.get("vpn_expired") is False:
        return _decision(
            category="VPN",
            intent="vpn_connection_issue",
            response=(
                "Understood - it is not a credential expiry. VPN access is automatic for full-time employees, so "
                "this looks like a technical connection fault rather than an entitlement issue. I have raised a "
                "ticket with the IT Service Desk to investigate."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-02"],
            ticket_required=True,
            assigned_team="IT Service Desk",
            confidence=0.8,
            ticket_status="In Progress",
            issue_summary="VPN not connecting - no credential expiry message",
        )

    return _follow_up(
        "VPN",
        "Is the VPN showing an expired credential message?",
        "vpn_expired",
        ["KB-02"],
        "vpn_triage",
    )


def rule_laptop(text: str, slots: Dict) -> Dict:
    age = slots.get("laptop_age_years")
    failure = slots.get("hardware_failure")

    if age is None:
        return _follow_up(
            "Laptop/Hardware",
            "How old is the laptop (years since it was issued)?",
            "laptop_age_years",
            ["KB-03", "ASSET-01"],
            "laptop_triage",
        )
    if failure is None:
        return _follow_up(
            "Laptop/Hardware",
            "Is there a verified hardware failure (e.g. it will not power on), or is it a software/performance problem?",
            "hardware_failure",
            ["KB-03", "ASSET-01"],
            "laptop_triage",
        )

    if failure and age is not None and 3 <= age < 4:
        return _decision(
            category="Laptop/Hardware",
            intent="laptop_replacement_policy_conflict",
            response=(
                f"Two company policies apply to a {age}-year-old laptop with a hardware failure, and they do not "
                "give the same answer, so I am not deciding this on my own:\n\n"
                "- **KB-03 (Laptop Replacement)** - eligible after 3 years of service, or earlier for a verified "
                "hardware failure. Requests should be raised at least 2 weeks in advance.\n"
                "- **Asset Management Policy** - hardware follows a 4-year refresh cycle; replacement before that "
                "point is an early replacement and needs **Finance sign-off in addition to IT approval**.\n\n"
                "I have raised a replacement ticket in *Pending Approval*, routed for IT approval plus Finance "
                "sign-off, and flagged the hardware failure for verification. Precedent: TK-1043 (3.2 yrs) was "
                "approved and is pending fulfilment. This is not resolved yet - it is awaiting approval."
            ),
            action="CREATE_TICKET",
            priority="HIGH",
            source_ids=["KB-03", "ASSET-01"],
            ticket_required=True,
            assigned_team="IT Hardware + Finance",
            confidence=0.9,
            ticket_status="Pending Approval",
            issue_summary=f"Laptop replacement request - {age} yrs old with suspected hardware failure (KB-03 vs 4-year refresh cycle)",
            policy_conflict=(
                "KB-03 allows replacement at 3 years / on verified hardware failure, while the Asset Management "
                "Policy sets a 4-year refresh cycle and requires Finance sign-off for early replacement. "
                "Routed for both IT approval and Finance sign-off rather than resolved by the agent."
            ),
            precedent_ticket_ids=["TK-1043"],
        )

    if failure and age is not None and age >= 4:
        return _decision(
            category="Laptop/Hardware",
            intent="laptop_replacement_eligible",
            response=(
                f"At {age} years the laptop is past the 4-year refresh cycle and also meets the KB-03 3-year "
                "replacement threshold, so no Finance early-replacement sign-off is needed. I have raised a "
                "replacement ticket with IT Hardware. Replacement requests should be raised at least 2 weeks "
                "before the intended replacement date."
            ),
            action="CREATE_TICKET",
            priority="HIGH",
            source_ids=["KB-03", "ASSET-01"],
            ticket_required=True,
            assigned_team="IT Hardware",
            confidence=0.9,
            ticket_status="New",
            issue_summary=f"Laptop replacement request - {age} yrs old, hardware failure reported",
        )

    if failure:
        return _decision(
            category="Laptop/Hardware",
            intent="laptop_repair_first",
            response=(
                f"At {age} years the laptop is inside both the KB-03 3-year window and the 4-year asset refresh "
                "cycle, so a replacement would be an early replacement requiring Finance sign-off in addition to "
                "IT approval. KB-03 does allow earlier replacement for a **verified** hardware failure, so the "
                "first step is a hardware diagnostic. I have raised a repair/diagnostic ticket with IT Hardware; "
                "if the fault is verified as unrepairable it will be routed for the required approvals."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-03", "ASSET-01"],
            ticket_required=True,
            assigned_team="IT Hardware",
            confidence=0.88,
            ticket_status="In Progress",
            issue_summary=f"Laptop fault reported - {age} yrs old, diagnostic/repair before any replacement decision",
            policy_conflict=(
                "Replacement before the 4-year refresh cycle requires Finance sign-off (Asset Management Policy); "
                "KB-03 permits early replacement only for a verified hardware failure, so the failure must be "
                "verified first."
            ),
        )

    return _decision(
        category="Laptop/Hardware",
        intent="laptop_not_eligible",
        response=(
            f"With no verified hardware failure and {age} years of service, the laptop is not eligible for "
            "replacement: KB-03 sets 3 years of service (or a verified hardware failure) and the Asset Management "
            "Policy runs a 4-year refresh cycle, with Finance sign-off required for any early replacement. "
            "If a fault develops, come back to me and I will raise a diagnostic ticket."
        ),
        action="RESOLVE",
        priority="LOW",
        source_ids=["KB-03", "ASSET-01"],
        confidence=0.85,
        issue_summary="Laptop replacement eligibility query",
    )


def rule_software(text: str, slots: Dict) -> Dict:
    in_catalog = slots.get("in_catalog")
    if in_catalog is True:
        return _decision(
            category="Software",
            intent="catalog_software_self_install",
            response=(
                "Software listed in the approved catalog can be self-installed - no approval or ticket is needed. "
                "Install it from the catalog and let me know if the installation itself fails."
            ),
            action="RESOLVE",
            priority="LOW",
            source_ids=["KB-04"],
            confidence=0.9,
            issue_summary="Catalog software self-installation",
        )
    if in_catalog is False:
        return _decision(
            category="Software",
            intent="non_catalog_software_review",
            response=(
                "Software that is not in the approved catalog requires an **IT Security review**, which takes "
                "3-5 business days. I have raised a request in *Pending Approval* and assigned it to IT Security. "
                "Precedent: TK-1044 is currently in the same review queue. Please do not install it in the "
                "meantime."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-04"],
            ticket_required=True,
            assigned_team="IT Security",
            confidence=0.93,
            ticket_status="Pending Approval",
            issue_summary="Non-catalog software installation request - IT Security review required",
            precedent_ticket_ids=["TK-1044"],
        )
    return _follow_up(
        "Software",
        "Is the software listed in the approved software catalog? Catalog items can be self-installed; anything else needs IT Security review.",
        "in_catalog",
        ["KB-04"],
        "software_triage",
    )


def rule_printer(text: str, slots: Dict) -> Dict:
    restarted = slots.get("spooler_restarted")
    if restarted is None:
        return _follow_up(
            "Printer",
            "Have you already checked the print queue and restarted the print spooler?",
            "spooler_restarted",
            ["KB-05"],
            "printer_triage",
        )
    if restarted is False:
        return _decision(
            category="Printer",
            intent="printer_first_line_fix",
            response=(
                "Please try the standard first-line fix: check the printer queue for stuck jobs, then restart the "
                "print spooler. That clears most phantom errors. If the issue persists after the restart, tell me "
                "the printer's asset tag and I will log a ticket."
            ),
            action="RESOLVE",
            priority="LOW",
            source_ids=["KB-05"],
            confidence=0.88,
            issue_summary="Printer troubleshooting guidance issued",
        )
    if not slots.get("asset_tag"):
        return _follow_up(
            "Printer",
            "Thanks. Since the issue persists after the restart, what is the printer's asset tag? I need it to log the ticket.",
            "asset_tag",
            ["KB-05"],
            "printer_ticket",
        )
    return _decision(
        category="Printer",
        intent="printer_ticket_logged",
        response=(
            f"Queue check and spooler restart did not fix it, so I have logged a ticket for printer "
            f"**{slots['asset_tag']}** with the IT Service Desk, as the policy requires."
        ),
        action="CREATE_TICKET",
        priority="MEDIUM",
        source_ids=["KB-05"],
        ticket_required=True,
        assigned_team="IT Service Desk",
        confidence=0.92,
        ticket_status="New",
        issue_summary=f"Printer fault persists after spooler restart - asset tag {slots['asset_tag']}",
        precedent_ticket_ids=["TK-1046"],
    )


def rule_mailbox(text: str, slots: Dict) -> Dict:
    if slots.get("wants_quota_increase"):
        return _decision(
            category="Email/Mailbox",
            intent="mailbox_quota_increase",
            response=(
                "Quota increases beyond the 25GB default require **manager approval** and are capped at 50GB. "
                "I have raised a quota-increase request in *Pending Approval* - it will be actioned once your "
                "manager approves. Precedent: TK-1045 was approved at 35GB. Archiving old mail in the meantime "
                "will get you sending again faster."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-06"],
            ticket_required=True,
            assigned_team="IT Service Desk",
            confidence=0.92,
            ticket_status="Pending Approval",
            issue_summary="Mailbox quota increase request (manager approval required, 50GB cap)",
            precedent_ticket_ids=["TK-1045"],
        )
    return _decision(
        category="Email/Mailbox",
        intent="mailbox_full",
        response=(
            "Your mailbox has hit the default **25GB** quota, which is why sending is blocked. The first step is "
            "to archive old mail - that frees space immediately and needs no approval.\n\n"
            "If you need more than 25GB, that requires **manager approval** and is **capped at 50GB**. Tell me if "
            "you want me to raise the quota-increase request and I will route it for approval."
        ),
        action="RESOLVE",
        priority="MEDIUM",
        source_ids=["KB-06"],
        confidence=0.93,
        issue_summary="Mailbox full at default 25GB quota",
        precedent_ticket_ids=["TK-1045"],
    )


def rule_guest_wifi(text: str, slots: Dict) -> Dict:
    return _decision(
        category="Guest Wi-Fi",
        intent="guest_wifi_request",
        response=(
            "No IT ticket is needed for this. You can generate guest Wi-Fi credentials yourself from the "
            "**front-desk kiosk**, and they are valid for **24 hours** - so generate them on the day of the visit."
        ),
        action="RESOLVE",
        priority="LOW",
        source_ids=["KB-07"],
        confidence=0.95,
        issue_summary="Guest Wi-Fi access request",
        precedent_ticket_ids=["TK-1051"],
    )


def rule_expense(text: str, slots: Dict) -> Dict:
    has_account = slots.get("expense_account_exists")
    if has_account is None:
        return _follow_up(
            "Finance/Expense",
            "Do you already have an expense tool account (i.e. you have logged in before), or is this a new access request?",
            "expense_account_exists",
            ["KB-08"],
            "expense_triage",
        )
    if has_account:
        return _decision(
            category="Finance/Expense",
            intent="expense_login_issue",
            response=(
                "Since the account already exists, this is a login/technical issue and IT can help. I have raised a "
                "ticket with the IT Service Desk to investigate the invalid-credentials error. Note that access "
                "itself is granted by Finance, not IT."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-08"],
            ticket_required=True,
            assigned_team="IT Service Desk",
            confidence=0.9,
            ticket_status="In Progress",
            issue_summary="Expense tool login failure on an existing account",
        )
    return _decision(
        category="Finance/Expense",
        intent="expense_access_request",
        response=(
            "Access to the expense management tool is granted by **Finance, not IT** - IT can only help with "
            "login or technical issues once an account exists. I have routed this request to Finance and raised a "
            "ticket so it is tracked; IT cannot grant this access."
        ),
        action="CREATE_TICKET",
        priority="MEDIUM",
        source_ids=["KB-08"],
        ticket_required=True,
        assigned_team="Finance",
        confidence=0.9,
        ticket_status="Pending Approval",
        issue_summary="Expense tool access request - routed to Finance",
    )


def rule_wfh_equipment(text: str, slots: Dict) -> Dict:
    days = slots.get("remote_days")
    if days is None:
        return _follow_up(
            "WFH Equipment",
            "How many days per week are you working remotely? The home office allowance applies above 3 days a week.",
            "remote_days",
            ["KB-10"],
            "wfh_triage",
        )
    if days > 3:
        return _decision(
            category="WFH Equipment",
            intent="wfh_equipment_eligible",
            response=(
                f"Working remotely {days} days a week makes you eligible for the **one-time** home office "
                "equipment allowance (chair, monitor). The sequence is: **manager sign-off**, then **Finance "
                "processing**; IT only handles the equipment shipping request once it is approved.\n\n"
                "I have raised a request in *Pending Approval* and routed it for manager sign-off and Finance. "
                "Precedent: TK-1047 is at the same stage."
            ),
            action="CREATE_TICKET",
            priority="MEDIUM",
            source_ids=["KB-10"],
            ticket_required=True,
            assigned_team="Finance",
            confidence=0.92,
            ticket_status="Pending Approval",
            issue_summary=f"Home office equipment (monitor) request - remote {days} days/week",
            precedent_ticket_ids=["TK-1047"],
        )
    return _decision(
        category="WFH Equipment",
        intent="wfh_equipment_not_eligible",
        response=(
            f"The home office equipment allowance applies to employees working remotely **more than 3 days a "
            f"week**. At {days} days a week you are not eligible under KB-10, so I cannot raise an equipment "
            "request. If your remote pattern changes, come back to me."
        ),
        action="RESOLVE",
        priority="LOW",
        source_ids=["KB-10"],
        confidence=0.88,
        issue_summary="Home office equipment eligibility query",
    )


def rule_access_request(text: str, slots: Dict) -> Dict:
    return _decision(
        category="Access Request",
        intent="privileged_access_request",
        response=(
            "I cannot grant admin/privileged access, and there is **no policy in the Veridian knowledge base that "
            "covers privileged access to servers** - so I am not going to invent an approval path for it.\n\n"
            "I have escalated this to IT Security with a ticket for a human decision. From precedent (TK-1050, "
            "rejected), please be ready to provide a written business justification, the duration of access needed "
            "and your manager's endorsement. Flagged as urgent for month-end, but urgency alone will not bypass "
            "review."
        ),
        action="ESCALATE",
        priority="HIGH",
        source_ids=[],
        ticket_required=True,
        escalation_required=True,
        assigned_team="IT Security",
        confidence=0.8,
        ticket_status="Escalated",
        issue_summary="Admin access request for finance reporting server - no governing KB policy, escalated",
        precedent_ticket_ids=["TK-1050"],
    )


def rule_unknown(text: str, slots: Dict) -> Dict:
    return _follow_up(
        "Unknown",
        "I can help. What isn't working - your laptop, VPN, email, printer, software, or another IT service?",
        "clarify",
        [],
        "clarification_needed",
    )


RULES = {
    "Security Incident": rule_security,
    "Password": rule_password,
    "VPN": rule_vpn,
    "Laptop/Hardware": rule_laptop,
    "Software": rule_software,
    "Printer": rule_printer,
    "Email/Mailbox": rule_mailbox,
    "Guest Wi-Fi": rule_guest_wifi,
    "Finance/Expense": rule_expense,
    "WFH Equipment": rule_wfh_equipment,
    "Access Request": rule_access_request,
    "Unknown": rule_unknown,
}


def decide(conversation_text: str, message: str, session: Dict) -> Dict:
    """Main entry point: classify -> fill slots -> apply the category rule."""
    slots = session.setdefault("slots", {})
    pending = session.get("pending_slot")
    if pending:
        apply_pending_answer(pending, message, slots)

    extract_slots(conversation_text, slots)

    category = classify(conversation_text)
    if category == "Unknown" and session.get("category"):
        category = session["category"]
    # A short answer such as "yes" must not reclassify an ongoing conversation.
    if pending and session.get("category") and category != session["category"]:
        if len(message.split()) <= 4:
            category = session["category"]

    decision = RULES.get(category, rule_unknown)(conversation_text, slots)

    # Attach retrieved KB ids if the rule produced none and something matches.
    if not decision["source_ids"] and category not in {"Access Request", "Unknown"}:
        decision["source_ids"] = retrieval.search_ids(conversation_text, 1)

    session["category"] = decision["category"] if decision["category"] != "Unknown" else session.get("category")
    session["pending_slot"] = decision.get("pending_slot")
    return decision
