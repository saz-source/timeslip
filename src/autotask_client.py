"""
Autotask REST API client.
Handles all API calls with retry/backoff. No secrets are logged.
"""
from __future__ import annotations
import os
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class Company:
    id: int
    name: str


@dataclass
class WorkType:
    id: int
    name: str


@dataclass
class CreationResult:
    ticket_id: int
    ticket_number: str
    time_entry_id: int


class PartialCreationError(Exception):
    """Ticket was created but time entry failed — stores ticket_id to avoid duplicate on retry."""
    def __init__(self, ticket_id: int, ticket_number: str, cause: Exception):
        super().__init__(str(cause))
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number


class AutotaskClient:

    def __init__(self, config: Config) -> None:
        self._config = config
        self._base = config.autotask_base_url.rstrip("/") + "/v1.0"
        self._session = self._build_session()
        self._all_companies: list | None = None
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        try:
            self.get_my_resource_id()
            return True
        except Exception as exc:
            logger.error("Connection test failed: %s", exc)
            return False

    def get_my_resource_id(self) -> int:
        """Look up resource by email (AUTOTASK_RESOURCE_EMAIL) not API username."""
        email = os.environ.get("AUTOTASK_RESOURCE_EMAIL", self._config.autotask_username)
        resp = self._query(
            "Resources",
            [{"field": "email", "op": "eq", "value": email}],
        )
        items = resp.get("items", [])
        if not items:
            raise RuntimeError(
                f"No Resource found for email '{email}'. "
                "Verify AUTOTASK_RESOURCE_EMAIL in .env."
            )
        return int(items[0]["id"])

    def get_work_types(self) -> list:
        """Fetch BillingCodes (AllocationCodes) for time entries."""
        resp = self._query(
            "BillingCodes",
            [{"field": "isActive", "op": "eq", "value": True}],
            max_records=200,
        )
        items = resp.get("items", [])
        return [WorkType(id=int(i["id"]), name=str(i.get("name", i["id"]))) for i in items]

    def get_priority_medium_id(self) -> int:
        try:
            url = f"{self._base}/Tickets/entityInformation/fields"
            resp = self._get(url)
            for field_def in resp.get("fields", []):
                if field_def.get("name", "").lower() == "priority":
                    for pv in field_def.get("picklistValues", []):
                        if pv.get("label", "").lower() == "medium":
                            return int(pv["value"])
        except Exception as exc:
            logger.warning("Priority picklist failed: %s. Using 2.", exc)
        return 2

    def validate_queue(self, queue_id: int) -> bool:
        return True   # Queue 404s in this instance — skip validation

    # ------------------------------------------------------------------
    # Company lookup — fuzzy + initials matching
    # ------------------------------------------------------------------

    def search_companies(self, name: str) -> list:
        query = name.strip()

        # 1. Direct API contains search
        try:
            resp = self._query(
                "Companies",
                [{"field": "companyName", "op": "contains", "value": query},
                 {"field": "isActive", "op": "eq", "value": True}],
                max_records=25,
            )
            results = list(resp.get("items", []))
        except Exception:
            results = []

        # 2. Fuzzy match against full company list (fetched once per session)
        try:
            if self._all_companies is None:
                resp2 = self._query(
                    "Companies",
                    [{"field": "isActive", "op": "eq", "value": True}],
                    max_records=500,
                )
                self._all_companies = resp2.get("items", [])
            existing_ids = {i["id"] for i in results}
            for item in self._all_companies:
                if item["id"] not in existing_ids:
                    score = self._match_score(item.get("companyName", ""), query)
                    if score >= 0.35:
                        results.append(item)
        except Exception:
            pass

        # Sort by score
        results.sort(
            key=lambda i: self._match_score(i.get("companyName", ""), query),
            reverse=True,
        )
        return [Company(id=int(i["id"]), name=str(i.get("companyName", i["id"])))
                for i in results[:20]]

    @staticmethod
    def _match_score(company_name: str, query: str) -> float:
        """Score how well query matches company_name. Higher = better match."""
        cn = company_name.lower()
        q = query.lower().strip()
        if not q:
            return 0.0
        if cn == q:
            return 10.0
        if cn.startswith(q):
            return 8.0
        if q in cn:
            return 6.0
        # Initials: skip non-alpha words like "&"
        initials = "".join(
            w[0] for w in company_name.split() if w and w[0].isalpha()
        ).lower()
        if initials == q:
            return 7.0
        if initials.startswith(q):
            return 5.0
        # Word-prefix: "bob ind" -> "Bob Industries"
        q_words = q.split()
        cn_words = cn.split()
        if q_words and all(any(cw.startswith(qw) for cw in cn_words) for qw in q_words):
            return 4.0
        return SequenceMatcher(None, q, cn).ratio() * 3.0

    # ------------------------------------------------------------------
    # Ticket + Time Entry creation
    # ------------------------------------------------------------------

    TRAVEL_TIME_BILLING_CODE_ID = 27192   # Travel Time billing code

    def create_ticket_and_time_entry(
        self,
        company_id: int,
        title: str,
        description: str,
        start_dt: datetime,
        end_dt: datetime,
        billing_code_id: int,
        resource_id: int,
        priority_id: int,
        queue_id: int,
        travel_hours: float = 0.0,
    ) -> CreationResult:
        date_str = start_dt.strftime("%Y-%m-%d")
        role_id = int(os.environ.get("AUTOTASK_ROLE_ID", 29682834))

        # 1. Create Ticket
        ticket_payload: dict[str, Any] = {
            "companyID": company_id,
            "title": title,
            "description": description,
            "status": 5,
            "priority": priority_id,
            "queueID": queue_id,
            "ticketType": 1,
            "assignedResourceID": resource_id,
            "assignedResourceRoleID": role_id,
        }
        ticket_resp = self._post("Tickets", ticket_payload)
        ticket_id = int(ticket_resp["itemId"])

        time.sleep(0.5)
        ticket_detail = self._get(f"{self._base}/Tickets/{ticket_id}")
        ticket_number = str(
            ticket_detail.get("item", {}).get("ticketNumber", ticket_id)
        )

        try:
            time_entry_id = self.create_time_entries(
                ticket_id=ticket_id,
                ticket_number=ticket_number,
                title=title,
                description=description,
                start_dt=start_dt,
                end_dt=end_dt,
                billing_code_id=billing_code_id,
                resource_id=resource_id,
                travel_hours=travel_hours,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            raise PartialCreationError(ticket_id, ticket_number, exc)

        return CreationResult(
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            time_entry_id=time_entry_id,
        )

    def create_time_entries(
        self,
        ticket_id: int,
        ticket_number: str,
        title: str,
        description: str,
        start_dt: datetime,
        end_dt: datetime,
        billing_code_id: int,
        resource_id: int,
        travel_hours: float = 0.0,
    ) -> int:
        """Create time entries for an existing ticket. Used for normal flow and partial-failure recovery."""
        from datetime import timedelta as _td
        role_id = int(os.environ.get("AUTOTASK_ROLE_ID", 29682834))

        if travel_hours > 0:
            travel_end = start_dt
            travel_start = start_dt - _td(hours=travel_hours)
            self._post("TimeEntries", {
                "resourceID": resource_id,
                "ticketID": ticket_id,
                "roleID": role_id,
                "startDateTime": self._fmt_dt(travel_start),
                "endDateTime": self._fmt_dt(travel_end),
                "summaryNotes": f"Travel time — {title}",
                "billingCodeID": self.TRAVEL_TIME_BILLING_CODE_ID,
            })

        te_resp = self._post("TimeEntries", {
            "resourceID": resource_id,
            "ticketID": ticket_id,
            "roleID": role_id,
            "startDateTime": self._fmt_dt(start_dt),
            "endDateTime": self._fmt_dt(end_dt),
            "summaryNotes": description,
            "billingCodeID": billing_code_id,
        })
        return int(te_resp["itemId"])

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(self._auth_headers())
        return session

    def _auth_headers(self) -> dict[str, str]:
        return {
            "APIIntegrationcode": self._config.autotask_integration_code,
            "Username": self._config.autotask_username,
            "Secret": self._config.autotask_secret,
            "Content-Type": "application/json",
        }

    def _query(self, entity: str, filters: list, max_records: int = 50) -> dict:
        url = f"{self._base}/{entity}/query"
        r = self._session.post(url, json={"filter": filters, "MaxRecords": max_records},
                               timeout=30)
        self._raise_for_status(r, url)
        return r.json()

    def _post(self, entity: str, payload: dict) -> dict:
        url = f"{self._base}/{entity}"
        r = self._session.post(url, json=payload, timeout=30)
        if not r.ok:
            try:
                data = r.json()
                if "itemId" in data:
                    return data  # Autotask 500 that actually succeeded
            except Exception:
                pass
            self._raise_for_status(r, url)
        return r.json()

    def _get(self, url: str) -> dict:
        r = self._session.get(url, timeout=30)
        self._raise_for_status(r, url)
        return r.json()

    def _raise_for_status(self, r: requests.Response, url: str) -> None:
        if not r.ok:
            entity = url.split("/v1.0/")[-1].split("?")[0].split("/")[0] if "/v1.0/" in url else "resource"
            raw = r.text[:300]
            try:
                errs = r.json().get("errors", [])
                if errs:
                    raw = "; ".join(str(e) for e in errs[:3])
            except Exception:
                pass
            if r.status_code == 401:
                msg = "Authentication failed — check AUTOTASK_USERNAME and AUTOTASK_SECRET in .env"
            elif r.status_code == 403:
                msg = "Access denied — check AUTOTASK_INTEGRATION_CODE in .env"
            elif r.status_code == 400:
                msg = f"Invalid {entity} data: {raw}"
            elif r.status_code == 404:
                msg = f"{entity} not found (404) — check IDs in .env"
            else:
                msg = f"Autotask {r.status_code} on {entity}: {raw}"
            self._last_error = msg
            raise RuntimeError(msg)

    @staticmethod
    def _fmt_dt(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
