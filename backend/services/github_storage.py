import base64
import json
import httpx

REPO_NAME = "dsa-planner-data"
_API = "https://api.github.com"


class GitHubStorageService:
    def __init__(self, token: str, username: str):
        self.token = token
        self.username = username
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def ensure_repo(self) -> bool:
        """Create the private dsa-planner-data repo if it doesn't exist yet."""
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{_API}/repos/{self.username}/{REPO_NAME}",
                headers=self._headers,
            )
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                cr = await client.post(
                    f"{_API}/user/repos",
                    headers=self._headers,
                    json={
                        "name": REPO_NAME,
                        "private": True,
                        "description": "My DSA practice sessions — managed by DSA Revision Planner",
                        "auto_init": True,
                    },
                )
                return cr.status_code in (200, 201)
        return False

    async def _get_sha(self, path: str) -> str | None:
        """Return the blob SHA of an existing file (needed to update it)."""
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{_API}/repos/{self.username}/{REPO_NAME}/contents/{path}",
                headers=self._headers,
            )
            if r.status_code == 200:
                return r.json().get("sha")
        return None

    async def commit_file(self, path: str, content: str, message: str) -> bool:
        encoded = base64.b64encode(content.encode()).decode()
        sha = await self._get_sha(path)
        payload: dict = {"message": message, "content": encoded}
        if sha:
            payload["sha"] = sha
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(
                f"{_API}/repos/{self.username}/{REPO_NAME}/contents/{path}",
                headers=self._headers,
                json=payload,
            )
            return r.status_code in (200, 201)

    async def commit_session(self, session: dict) -> bool:
        """Write sessions/{date}/{Question-Title}.json"""
        slug = session["question"].replace(" ", "-").replace("/", "-")
        path = f"sessions/{session['date']}/{slug}.json"
        content = json.dumps(session, indent=2, ensure_ascii=False)
        msg = f"practice: {session['question']} ({session['date']})"
        return await self.commit_file(path, content, msg)

    async def commit_insight(self, markdown: str, date: str, question: str) -> bool:
        """Write insights/{date}-{Question-Title}.md"""
        slug = question.replace(" ", "-").replace("/", "-")
        path = f"insights/{date}-{slug}.md"
        return await self.commit_file(path, markdown, f"insight: {question} ({date})")

    async def commit_weekly_summary(self, markdown: str, week_label: str) -> bool:
        """Write insights/weekly/{week_label}.md"""
        path = f"insights/weekly/{week_label}.md"
        return await self.commit_file(path, markdown, f"weekly summary: {week_label}")

    async def list_session_files(self) -> list[dict]:
        """Return all committed session JSON objects (for weekly summary)."""
        sessions: list[dict] = []
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{_API}/repos/{self.username}/{REPO_NAME}/git/trees/HEAD",
                headers=self._headers,
                params={"recursive": "1"},
            )
            if r.status_code != 200:
                return sessions
            for item in r.json().get("tree", []):
                path: str = item.get("path", "")
                if path.startswith("sessions/") and path.endswith(".json"):
                    fr = await client.get(
                        f"{_API}/repos/{self.username}/{REPO_NAME}/contents/{path}",
                        headers=self._headers,
                    )
                    if fr.status_code == 200:
                        raw = base64.b64decode(fr.json()["content"]).decode()
                        try:
                            sessions.append(json.loads(raw))
                        except Exception:
                            pass
        return sessions
