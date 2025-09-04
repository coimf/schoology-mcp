# Schoology MCP Server

Provide LLMs with your courses and upcoming assignments from Schoology.

## Installation

Since there is no official Schoology API, we use a cookie-based approach to fetch the data from endpoints.

### Getting Your Cookie

To get your cookie, follow these steps:

1. Login to Schoology.
2. Open developer tools (press F12).
3. Go to the `Console` tab.
4. Run `document.cookie` and copy the output.

### Getting Endpoints

**Upcoming Assignments**
1. Open developer tools.
2. Go to the `Network` tab and reload the page as necessary.
3. Find the `upcoming_submissions_ajax` request and copy the URL (right-click > copy value > copy URL).

**Courses**
1. Open developer tools.
2. Go to the `Network` tab and reload the page as necessary.
3. Click the courses dropdown in Schoology to load your courses.
3. Find the `courses` request and copy the URL (right-click > copy value > copy URL).

Now, clone the repository and add the following to the configuration file in your MCP client of choice, replacing `<your_schoology_cookie>`, `<upcoming_submissions_ajax>`, and `<courses_endpoint>` with the values you copied from the previous steps and the path to the repo.
```json
{
  "mcpServers": {
    "schoology-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "PATH/TO/schoology-mcp",
        "run",
        "server.py"
      ],
      "env": {
        "SCHOOLOGY_COOKIE": "<your_schoology_cookie>",
        "SCHOOLOGY_UPCOMING_ENDPOINT": "<upcoming_submissions_ajax>",
        "SCHOOLOGY_COURSES_ENDPOINT": "<courses_endpoint>"
      }
    }
  }
}
```

## Tools

1. `get_current_date`
- Returns the current date and time in the format YYYY-MM-DD HH:MM:SS.

2. `get_enrolled_courses`
- Fetch a list of courses the user is enrolled in from Schoology.
- Returns a list of dictionaries containing course information.

3. `get_upcoming_assignments`
- Fetch a list of upcoming assignments from Schoology.
- Returns a list of dictionaries containing assignment information.
