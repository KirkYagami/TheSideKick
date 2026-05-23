from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_experimental.tools import PythonREPLTool
from langchain_core.tools import Tool

from .env_helper import load_environment

import os
import requests


load_environment()

pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"

serper = GoogleSerperAPIWrapper()


async def playwright_tools():
    """
    Initialize Playwright browser tools.
    Compatible with LangChain v1+
    """

    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=False
    )

    toolkit = PlayWrightBrowserToolkit.from_browser(
        async_browser=browser
    )

    tools = toolkit.get_tools()

    return tools, browser, playwright


def push(text: str) -> str:
    """
    Send a push notification using Pushover.
    """

    if not pushover_token or not pushover_user:
        return "Pushover credentials not configured"

    try:
        response = requests.post(
            pushover_url,
            data={
                "token": pushover_token,
                "user": pushover_user,
                "message": text,
            },
            timeout=15,
        )

        response.raise_for_status()

        return "Push notification sent successfully"

    except requests.RequestException as e:
        return f"Failed to send push notification: {str(e)}"


def get_file_tools():
    """
    Initialize file management tools.
    """

    os.makedirs("sandbox", exist_ok=True)

    toolkit = FileManagementToolkit(
        root_dir="sandbox"
    )

    return toolkit.get_tools()


async def other_tools():
    """
    Load all non-browser tools.
    Compatible with LangChain v1+
    """

    push_tool = Tool(
        name="send_push_notification",
        func=push,
        description="Send a push notification to the user using Pushover.",
    )

    search_tool = Tool(
        name="search",
        func=serper.run,
        description="Search the web for recent or factual information.",
    )

    wikipedia = WikipediaAPIWrapper()

    wiki_tool = WikipediaQueryRun(
        api_wrapper=wikipedia
    )

    python_repl = PythonREPLTool()

    file_tools = get_file_tools()

    return (
        file_tools
        + [
            push_tool,
            search_tool,
            python_repl,
            wiki_tool,
        ]
    )