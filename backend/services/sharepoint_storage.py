"""
SharePoint / OneDrive file storage via Microsoft Graph API.

Mirrors the interface of github_storage.py but writes to the user's
OneDrive (which is accessible from SharePoint) using the Graph API.

Files are stored under: OneDrive/DSA-Planner/
  sessions/{date}/{question-slug}.json
  insights/{date}-{question-slug}.md
  summaries/{year}-W{week}.md
"""

import json
import logging
import re
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
ROOT_FOLDER = "DSA-Planner"


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\-]", "-", text.lower())[:60].strip("-")


class SharePointStorageService:
    def __init__(self, access_token: str, refresh_token: str | None = None):
        self.access_token = access_token
        self.refresh_token = refresh_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _refresh_if_needed(self, response: httpx.Response) -> bool:
        """Refresh the access token if we got a 401. Returns True if refreshed."""
        if response.status_code != 401 or not self.refresh_token:
            return False
        import os
        client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")
        tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
        if not client_id:
            return False
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "Files.ReadWrite Calendars.ReadWrite offline_access",
                },
            )
        if r.status_code == 200:
            self.access_token = r.json()["access_token"]
            self.refresh_token = r.json().get("refresh_token", self.refresh_token)
            return True
        return False

    async def _put_file(self, drive_path: str, content: bytes, content_type: str = "application/octet-stream") -> bool:
        """Upload a file to OneDrive at the given path under the root folder."""
        full_path = f"{ROOT_FOLDER}/{drive_path}"
        url = f"{GRAPH_BASE}/me/drive/root:/{full_path}:/content"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": content_type,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.put(url, content=content, headers=headers)
            if r.status_code == 401 and await self._refresh_if_needed(r):
                headers["Authorization"] = f"Bearer {self.access_token}"
                r = await client.put(url, content=content, headers=headers)
        if r.status_code in (200, 201):
            return True
        log.error("SharePoint upload failed for %s: %s %s", drive_path, r.status_code, r.text[:200])
        return False

    async def ensure_root_folder(self) -> bool:
        """Create DSA-Planner root folder if it doesn't exist."""
        url = f"{GRAPH_BASE}/me/drive/root/children"
        payload = {
            "name": ROOT_FOLDER,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload, headers=self._headers())
        # 409 = already exists — that's fine
        return r.status_code in (200, 201, 409)

    async def commit_session(self, session: dict) -> bool:
        date = session.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        slug = _slug(session.get("question", "unknown"))
        path = f"sessions/{date}/{slug}.json"
        content = json.dumps(session, indent=2, ensure_ascii=False).encode()
        return await self._put_file(path, content, "application/json")

    async def commit_insight(self, insight_md: str, date: str, question_title: str) -> bool:
        slug = _slug(question_title)
        path = f"insights/{date}-{slug}.md"
        return await self._put_file(path, insight_md.encode(), "text/markdown")

    async def commit_weekly_summary(self, summary_md: str, week_label: str) -> bool:
        path = f"summaries/{week_label}.md"
        return await self._put_file(path, summary_md.encode(), "text/markdown")

    async def list_session_files(self) -> list[dict]:
        """List all JSON files under sessions/ and return their parsed contents."""
        url = f"{GRAPH_BASE}/me/drive/root:/{ROOT_FOLDER}/sessions:/children"
        results = []
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers())
            if r.status_code != 200:
                return []
            date_folders = r.json().get("value", [])
            for folder in date_folders:
                folder_url = f"{GRAPH_BASE}/me/drive/items/{folder['id']}/children"
                fr = await client.get(folder_url, headers=self._headers())
                if fr.status_code != 200:
                    continue
                for item in fr.json().get("value", []):
                    if not item["name"].endswith(".json"):
                        continue
                    dl_url = item.get("@microsoft.graph.downloadUrl") or \
                              f"{GRAPH_BASE}/me/drive/items/{item['id']}/content"
                    dr = await client.get(dl_url, headers=self._headers(), follow_redirects=True)
                    if dr.status_code == 200:
                        try:
                            results.append(dr.json())
                        except Exception:
                            pass
        return results

    async def list_sessions_with_insights(self) -> list[dict]:
        """List sessions paired with their insight markdown if available."""
        sessions = await self.list_session_files()
        insights_index = await self._build_insights_index()
        for s in sessions:
            date = s.get("date", "")
            slug = _slug(s.get("question", ""))
            s["insight_md"] = insights_index.get(f"{date}-{slug}", "")
        return sessions

    async def _build_insights_index(self) -> dict:
        url = f"{GRAPH_BASE}/me/drive/root:/{ROOT_FOLDER}/insights:/children"
        index = {}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=self._headers())
            if r.status_code != 200:
                return index
            for item in r.json().get("value", []):
                key = item["name"].replace(".md", "")
                dl_url = item.get("@microsoft.graph.downloadUrl") or \
                          f"{GRAPH_BASE}/me/drive/items/{item['id']}/content"
                dr = await client.get(dl_url, headers=self._headers(), follow_redirects=True)
                if dr.status_code == 200:
                    index[key] = dr.text
        return index
