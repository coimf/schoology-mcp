from __future__ import annotations

import browser_cookie3
import requests
import logging
import json
import os
from http.cookiejar import CookieJar
from typing import Optional
from datetime import datetime
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    try:
        config = SchoologyConfig()
    except Exception as e:
        logger.error(f"Failed to connect to Schoology: {e}")
        raise
    try:
        yield {"config": config}
    finally:
        logger.info("Shutting down...")

mcp = FastMCP("schoology-mcp", lifespan=app_lifespan)

class SchoologyConfig:
    def __init__(self):
        self.base_url = os.environ.get("SCHOOLOGY_BASE_URL")
        if self.base_url is None:
            raise Exception("Please set the SCHOOLOGY_BASE_URL environment variable to <your-school-district>.schoology.com")
        self.session = self._create_requests_session(self.base_url, browser="chrome")
        if self.session is None:
            raise Exception("Failed to authenticate. Try signing into Schoology in your browser again.")
        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en,en-US;q=0.9",
            "cache-control": "no-cache",
            "dnt": "1",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": self.base_url,
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
            "DNT": "1",
            "Connection": "keep-alive",
        }

    def _load_browser_cookies(self, domain: str, browser: str = "chrome") -> Optional[CookieJar]:
        """
        Load cookies for domain from the browser.

        Args:
            domain: host to filter
            browser: "firefox", "chrome", etc.

        Returns:
            A `http.cookiejar.CookieJar` containing matching cookies.
        """

        loader = getattr(browser_cookie3, browser, None)
        if callable(loader):
            cj = loader(domain_name=domain)
        else:
            cj = browser_cookie3.load(domain_name=domain)

        return cj

    def _create_requests_session(self, domain: str, browser: str = "chrome") -> requests.Session:
        """
        Create a requests.Session preloaded with cookies for the domain.
        """
        session = requests.Session()
        cj = self._load_browser_cookies(domain=domain, browser=browser)
        if cj is None:
            raise Exception("Failed to load cookies. Try signing into Schoology in your browser again.")

        cookie_dict = {}
        for c in cj:
            cookie_dict[c.name] = c.value

        session.cookies.update(cookie_dict)
        return session

config = SchoologyConfig()

def _extract_assignments(response_json: dict) -> list[dict]:
    """
    Extracts and sorts assignment details from Schoology's response.

    Args:
        response_json: The JSON response with an 'html' field

    Returns:
        List of assignment dictionaries with title, due date, and class
    """
    if not isinstance(response_json, dict) or 'html' not in response_json:
        raise ValueError(f"Invalid response format: {response_json}\nmissing 'html' field")

    html = response_json.get("html", "")
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    assignments = []
    for event in soup.select(".upcoming-event"):
        title_tag = event.select_one(".event-title a")
        class_tags = event.select(".readonly-title.event-subtitle")

        if not title_tag or not class_tags:
            continue

        title = title_tag.get_text(strip=True)
        due_text = class_tags[0].get_text(strip=True)
        course = class_tags[-1].get_text(strip=True)

        due_str = due_text.replace("Due ", "")
        if due_str.endswith("at"):
            due_str += " 11:59 pm"

        try:
            due_dt = datetime.strptime(due_str, "%A, %B %d, %Y at %I:%M %p")
        except ValueError:
            due_dt = None

        assignments.append({
            "title": title,
            "due": due_dt,
            "class": course
        })

    assignments.sort(key=lambda x: x["due"] or datetime.max)
    return assignments

@mcp.tool()
def get_current_date() -> str:
    """
    Returns the current date and time in the format YYYY-MM-DD HH:MM:SS.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def get_enrolled_courses() -> list[dict]:
    """
    Retrieve all courses student is enrolled in from Schoology.
    """
    url = f"https://{config.base_url}/iapi2/site-navigation/courses"
    try:
        r = config.session.get(url, headers=config.headers)
        data = r.json()
        keep_keys = ["courseTitle", "sectionTitle"]
        courses = data.get('data', {}).get('courses', [])

        return [{k: c.get(k) for k in keep_keys} for c in courses]
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching courses: {e}")
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"Invalid response format: {e}")
        raise

@mcp.tool()
def get_upcoming_assignments() -> list[dict]:
    """
    Retrieve upcoming assignments from Schoology.
    """
    url = f"https://{config.base_url}/home/upcoming_submissions_ajax"
    r = config.session.get(url, headers=config.headers)
    try:
        r = r.json()
    except json.JSONDecodeError:
        return [{0: "Failed to decode response. Try signing into Schoology in your browser again."}]

    return _extract_assignments(r)

if __name__ == "__main__":
    mcp.run(transport='stdio')
