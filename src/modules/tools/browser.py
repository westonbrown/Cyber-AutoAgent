import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, Any, Union

from playwright.async_api import Page, BrowserContext, Response
from pymitter import EventEmitter
from stagehand import StagehandConfig, Stagehand, StagehandPage
from stagehand.context import StagehandContext
from strands import tool
from tldextract import tldextract

logger = logging.getLogger(__name__)


class BrowserService(EventEmitter):
    _initialized = False

    stagehand_config: StagehandConfig
    stagehand: Stagehand
    artifacts_dir: str
    provider: str
    model: str

    def __init__(
        self,
        provider: str,
        model: str,
        artifacts_dir: Optional[str] = None,
        extra_http_headers: Optional[dict[str, str]] = None,
    ):
        super().__init__()
        api_key = None
        # Stagehand internally uses litellm. so we ensure the model name is as per what is required by litellm
        if provider == "bedrock":
            model = f"bedrock/{model}"
            if os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
                api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        elif provider == "ollama":
            model = f"ollama/{model}"

        self.provider = provider
        self.model = model
        self.artifacts_dir = artifacts_dir
        launch_options: dict[str, Any] = {"viewPort": {"width": 1280, "height": 720}}

        if extra_http_headers:
            launch_options["extra_http_headers"] = extra_http_headers

        if self.artifacts_dir:
            launch_options["downloads_path"] = os.path.join(self.artifacts_dir, "browser_downloads")
            launch_options["user_data_dir"] = os.path.join(self.artifacts_dir, "browser_profile")
            launch_options["record_har_content"] = "embed"
            launch_options["record_har_mode"] = "full"
            launch_options["record_har_path"] = os.path.join(self.artifacts_dir, "browser_network.har")
        else:
            logger.warning(
                "No artifacts_dir provided. Browser will not persist network traffic, profile, downloads to artifacts."
            )

        self.stagehand_config = StagehandConfig(
            env="LOCAL", modelName=model, modelApiKey=api_key, selfHeal=True, localBrowserLaunchOptions=launch_options
        )
        self.stagehand = Stagehand(self.stagehand_config)

    @property
    def page_domain(self):
        """
        Get the domain of the page from its URL.

        This property extracts the domain and suffix of the URL associated
        with the `page` attribute to construct a full domain in the format
        `domain.suffix`.

        Returns:
            str: The domain of the page extracted from its URL.
        """
        parsed_domain = tldextract.extract(self.page.url)
        return f"{parsed_domain.domain}.{parsed_domain.suffix}"

    @property
    def page(self) -> Union[Page, StagehandPage]:
        """
        A property that retrieves the current page instance.

        This property provides access to the `page` attribute, which represents the
        current page or stagehand page being managed.

        Returns:
            Union[Page, StagehandPage]: The current page or stagehand page instance.
        """
        return self.stagehand.page

    @property
    def context(self) -> Union[BrowserContext, StagehandContext]:
        """
        This property retrieves the context associated with the current stagehand instance.

        The context represents the environment or operational settings pertinent to the instance
        and ensures access to the appropriate functionalities or configurations.

        Returns
        -------
        Union[BrowserContext, StagehandContext]
            The context managed by stagehand.
        """
        return self.stagehand.context

    async def ensure_init(self):
        """Lazy init stagehand when needed"""
        if self._initialized:
            return
        await self.stagehand.init()
        self._initialized = True
        self.page.on(
            "response",
            lambda response: self.emit_async("response", response),
        )

    @asynccontextmanager
    async def network_capture(self, only_domains: Optional[list[str]] = None):
        """
        Async context manager to capture network responses during its usage.

        This context manager listens to network responses that occur during its
        scope and provides a list of responses upon exiting. It attaches an event
        listener to capture specific responses and removes the listener once the
        context is exited.

        Args:
            only_domains (Optional[list[str]]): Optional domains to filter responses by.

        Yields:
            list[Response]: A list of captured responses generated during the
            context manager's scope.
        """
        responses: list[Response] = []

        def capture_response(response: Response):
            if only_domains:
                for filter_domain in only_domains:
                    if response.url.endswith(filter_domain):
                        responses.append(response)
                        return
            else:
                responses.append(response)

        self.on("response", capture_response)
        try:
            yield responses
        finally:
            self.off("responses", capture_response)


_BROWSER: Optional[BrowserService] = None


def initialize_browser(
    provider: str,
    model: str,
    artifacts_dir: Optional[str] = None,
    extra_http_headers: Optional[dict[str, str]] = None,
):
    global _BROWSER
    _BROWSER = BrowserService(provider, model, artifacts_dir, extra_http_headers)
    return _BROWSER


async def get_browser():
    if not _BROWSER:
        raise ValueError("Browser not initialized. Please call initialize_browser first.")
    await _BROWSER.ensure_init()
    return _BROWSER


def format_headers(headers: dict[str, str]) -> str:
    important_headers = [
        "content-type",
        "content-length",
        "date",
        "server",
        "location",
        "authorization",
        "cookie",
        "set-cookie",
    ]
    return "\n".join(
        [f"\t`{k}`: `{v}`" for k, v in headers.items() if k.lower() in important_headers or k.lower().startswith("x-")]
    )


async def simplify_responses_for_llm(responses: list[Response]) -> str:
    """
    Simplifies a list of response objects into a human-readable format suitable
    for large language models (LLMs). The function extracts key details
    from the request and response, including HTTP method, URL, headers,
    request body (if present), status code, and response body size.

    Parameters:
    responses: list[Response]
        A list of Response objects to be simplified.

    Returns:
    list[str]
        A list of simplified string representations for the provided responses.
    """
    simplified_responses: list[str] = []
    for response in responses:
        simplified_request = [
            f"`{response.request.method}` `{response.request.url}`",
            "Request Headers:",
            format_headers(response.request.headers),
        ]

        if request_body := response.request.post_data_buffer:
            simplified_request.append(f"Request Body: ```{request_body}```")

        simplified_response = [
            f"Status Code: `{response.status}`",
            "Response Headers:",
            format_headers(response.headers),
        ]

        simplified_responses.append("\n".join(simplified_request + simplified_response))

    return "<network_call>" + "</network_call>\n<network_call>".join(simplified_responses) + "</network_call>"


@tool
async def browser_set_headers(headers: dict[str, str]):
    """
    Set headers that need to be sent with all requests from the browser

    Parameters:
        headers (dict[str, str]): the headers to be sent with all requests
    """
    browser = await get_browser()
    await browser.context.set_extra_http_headers(headers)


@tool
async def browser_goto_url(url: str):
    """
    Navigate the browser to a specified URL and capture network responses.

    Use this tool when you need to open a URL in a browser. This is useful for SPAs where the full page is only rendered
    with javascript and requires a browser to access.

    Args:
        url: The URL to navigate to.

    Returns:
        A collection of network responses captured during the navigation.
    """
    browser = await get_browser()
    url_domain = tldextract.extract(url)
    async with browser.network_capture(
        only_domains=[browser.page_domain, f"{url_domain.domain}.{url_domain.suffix}"]
    ) as responses:
        await browser.page.goto(url)
        return await simplify_responses_for_llm(responses)


@tool
async def browser_get_page_html() -> str:
    """
    Get the HTML content of the current page in the browser.

    Use this tool to retrieve the HTML content of the current page in the browser.

    Returns:
        The HTML content of the current page in the browser.
    """
    browser = await get_browser()
    return await browser.page.content()


@tool
async def browser_perform_action(action: str):
    """
    Perform an action on the current page in the browser.

    Use this tool to perform an action on the current page in the browser.

    Notes:
        - The instruction should perform only one atomic action on the page. Examples, `Single click on a specific element`, `Type into a single input field`.
        - Do not combine multiple instructions into one. `Click and type` is wrong. `Type and click on first suggestion` is wrong.
        - If there are two similar elements, be specific about which one to interact with.
        - Do not mix two actions in one instruction. For example, if you are clicking on a button and then typing into an input field, do not combine them into one instruction. Instead, create two separate instructions: one for the click action and another for the typing action.

    Examples:
        - Click on the sign in button
        - Enter john.doe into the username input field
        - Enter SecretPassword into the password input field
        - Click on the submit button
        - Click on Cars from the dropdown menu

    Returns:
        - A collection of network responses captured during the course of this action.
    """
    browser = await get_browser()
    async with browser.network_capture(only_domains=[browser.page_domain]) as responses:
        await browser.page.act(action)
        return await simplify_responses_for_llm(responses)


@tool
async def browser_observe_page(instruction: Optional[str] = None):
    """
    Observes the page and returns a list of descriptions of interesting elements on the page.

    Use this tool if you want to see what a page contains or if you're looking for something specific on the page.

    Examples:
        - All interactive elements on the page
        - All forms on the page
        - All links on the page
        - All sensitive interactions on the page
        - The links to edit user information

    Args:
        instruction (Optional[str]): An optional instruction or directive to filter
            or specify the observations required from the page.

    Returns:
        List[str]: A list of descriptions derived from the observations recorded
            on the browser page.
    """
    browser = await get_browser()
    observations = await browser.page.observe(instruction)
    return [observation.description for observation in observations]
