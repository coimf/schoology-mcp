from __future__ import annotations

import os
import requests
import logging
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
        self.cookie = self._get_required_env("SCHOOLOGY_COOKIE")
        self.courses_endpoint = self._get_required_env("SCHOOLOGY_COURSES_ENDPOINT")
        self.upcoming_endpoint = self._get_required_env("SCHOOLOGY_UPCOMING_ENDPOINT")

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:142.0) Gecko/20100101 Firefox/142.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "DNT": "1",
            "Connection": "keep-alive",
        }

    def _get_required_env(self, key: str) -> str:
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Please set {key} environment variable first.")
        return value

config = SchoologyConfig()

def _extract_assignments(response_json: dict) -> list[dict]:
    """
    Extracts and sorts assignment details from Schoology's response.

    Args:
        response_json: The JSON response with an 'html' field

    Returns:
        List of assignment dictionaries with title, due date, and class

    Raises:
        ValueError: If response format is invalid or missing 'html' field
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

def _split_cookie_string(c: str) -> dict[str, str]:
    parts = [p.strip() for p in c.split(";")]
    d = {}
    for p in parts:
        name, _, value = p.partition("=")
        d[name] = value
    return d

@mcp.tool()
def get_current_date() -> str:
    """
    Returns the current date and time in the format YYYY-MM-DD HH:MM:SS.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def get_enrolled_courses() -> list[dict]:
    """
    Retrieve courses student is enrolled in from Schoology.

    Raises:
        RequestException: If unable to fetch courses
        ValueError, KeyError: If unable to parse response
    """
    try:
        response = requests.get(
            config.courses_endpoint,
            headers=config.headers,
            cookies=_split_cookie_string(config.cookie),
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        keep_keys = ["courseTitle", "sectionTitle"]
        courses = data.get('data', {}).get('courses', [])

        return [{k: c.get(k) for k in keep_keys} for c in courses]

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error occurred while fetching courses: {e}")
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"Invalid response format: {e}")
        raise

@mcp.tool()
def get_upcoming_assignments() -> list[dict]:
    """
    Retrieve upcoming assignments from Schoology.

    Returns:
        list[dict]: Assignment details with the following structure:
            - title (str): Assignment name
            - due (datetime|None): Due date/time, None if parsing failed
            - class (str): Course name
    """

    response = requests.get(config.upcoming_endpoint, headers=config.headers, cookies=_split_cookie_string(config.cookie))
    return _extract_assignments(response.json())

if __name__ == "__main__":
    mcp.run(transport='stdio')
