import asyncio
import base64
import contextlib
import csv
import datetime
import functools
import json
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from http.cookies import SimpleCookie, Morsel
from typing import Optional, Any, Union
from urllib.parse import urlparse, parse_qs
from modules import __version__

from playwright.async_api import Page, BrowserContext, Response, TimeoutError, Request
from pymitter import EventEmitter
from six import StringIO
from stagehand import StagehandConfig, Stagehand, StagehandPage
from stagehand.context import StagehandContext
from strands import tool
from tldextract import tldextract

logger = logging.getLogger(__name__)


@functools.cache
def extract_domain(url_or_fqdn: str) -> str:
    """
    Extracts the domain from a given URL or fully qualified domain name (FQDN).
    The function uses the `tldextract` library to parse the input and retrieve the primary
    domain and suffix. If no suffix is found, it is assumed to be a local domain,
    and only the domain is returned. Typical use cases include extracting useful
    domain information from URLs or processing local domains.

    Args:
        url_or_fqdn: A string representing a URL or fully qualified domain name from
        which the domain will be extracted.

    Returns:
        A string representing the extracted domain. For example, for input
        "www.example.com", "example.com" is returned. For local domains such as
        "server.local", "server" is returned.
    """
    domain_extract = tldextract.extract(url_or_fqdn)
    if not domain_extract.suffix:
        # Suffix can be empty for local domains such as `something.mine.local` or `server.orb.local`
        return domain_extract.domain

    return f"{domain_extract.domain}.{domain_extract.suffix}"


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
        launch_options: dict[str, Any] = {
            "headless": True,
            "viewPort": {"width": 1280, "height": 720},
            "args": ["--disable-blink-features=AutomationControlled", "--disable-smooth-scrolling"],
        }

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
            env="LOCAL",
            modelName=model,
            modelApiKey=api_key,
            selfHeal=True,
            localBrowserLaunchOptions=launch_options,
            verbose=0,  # errors only. keep output minimal
            use_rich_logging=False,  # ensure ansi does not pollute outputs
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
        return extract_domain(self.page.url)

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
        for network_event in ("request", "response", "requestfailed", "requestfinished"):  # type: Any
            self.page.on(
                network_event,
                lambda response: self.emit_async(network_event, response),
            )

    async def simplify_requests_for_llm(self, requests: list[Request]) -> str:
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
        network_calls: list[str] = []
        har_entries: list[dict] = []

        har_file_path = os.path.join(self.artifacts_dir, f"network_calls_{time.time_ns()}.har")

        har_data = {
            "log": {
                "version": "1.2",
                "creator": {"name": "Cyber-AutoAgent", "version": __version__, "comment": ""},
                "browser": {
                    "name": self.context.browser.browser_type.name,
                    "version": self.context.browser.version,
                    "comment": "",
                },
                "entries": har_entries,
            }
        }

        for index, request in enumerate(requests):
            try:
                parsed_url = urlparse(request.url)
                all_request_headers = await request.all_headers()
                pw_timings = request.timing
                timings = {
                    "blocked": 0,
                    "dns": (
                        -1
                        if pw_timings["domainLookupEnd"] == -1
                        else pw_timings["domainLookupEnd"] - pw_timings["domainLookupStart"]
                    ),
                    "connect": (
                        -1 if pw_timings["connectEnd"] == -1 else pw_timings["connectEnd"] - pw_timings["connectStart"]
                    ),
                    "send": -1,
                    "wait": (
                        -1
                        if pw_timings["responseStart"] == -1
                        else pw_timings["responseStart"] - pw_timings["requestStart"]
                    ),
                    "receive": (
                        -1
                        if pw_timings["responseEnd"] == -1
                        else pw_timings["responseEnd"] - pw_timings["responseStart"]
                    ),
                    "ssl": (
                        -1
                        if pw_timings["secureConnectionStart"] == -1
                        else pw_timings["requestStart"] - pw_timings["secureConnectionStart"]
                    ),
                }

                total_time_taken = sum([time_value for time_value in timings.values() if time_value > 0], 0)
                started_date_time = datetime.datetime.fromtimestamp(
                    request.timing["startTime"] / 1000.0, tz=datetime.timezone.utc
                )
                har_entry: dict[str, Any] = {
                    "timings": timings,
                    "time": total_time_taken,
                    "startedDateTime": started_date_time.isoformat(),
                    "request": {
                        "method": request.method,
                        "url": request.url,
                        "httpVersion": "HTTP/1.1",
                        "headers": [{"name": k, "value": v} for k, v in all_request_headers.items()],
                        "queryString": [],
                        "cookies": [],
                        "bodySize": -1,
                        "headersSize": -1,
                    },
                }

                har_entries.append(har_entry)

                if parsed_url.query:
                    for name, values in parse_qs(parsed_url.query).items():
                        for value in values:
                            har_entry["request"]["queryString"].append({"name": name, "value": value})

                if cookie_header := all_request_headers.get("cookie"):
                    parsed_cookie = SimpleCookie(cookie_header)
                    for cookie in parsed_cookie.items():  # type: tuple[str, Morsel]
                        har_entry["request"]["cookies"].append({"name": cookie[0], "value": cookie[1].value})

                simplified_request = [
                    f"`{request.method}` `{request.url}`",
                ]

                if formatted_request_headers := format_headers(all_request_headers):
                    simplified_request.extend(["Request Headers:", formatted_request_headers])

                if request_body := request.post_data_buffer:
                    har_entry["request"]["bodySize"] = len(request_body)
                    post_data = har_entry["request"]["postData"] = form_har_body(
                        request.headers.get("content-type", ""), request_body
                    )
                    if post_data["encoding"] == "utf-8":
                        simplified_request.append(f"Request Body: ```{post_data['text']}```")
                    else:
                        simplified_request.append(f"Request Body: Non-UTF8 Binary")

                response: Response | None = None

                with suppress(asyncio.TimeoutError):
                    async with asyncio.timeout(
                        60
                    ):  # Wait for up to 60 seconds for the response object to be available (Status/headers first).
                        response = await request.response()

                if response:
                    all_response_headers = await response.all_headers()
                    har_entry["response"] = har_entry_response = {
                        "status": response.status,
                        "statusText": response.status_text,
                        "httpVersion": "HTTP/1.1",
                        "headers": [{"name": k, "value": v} for k, v in all_response_headers.items()],
                        "cookies": [],
                        "headersSize": -1,
                        "bodySize": -1,
                    }  # type: dict[str, Any]

                    if location_header := (all_response_headers.get("location")):
                        har_entry_response["redirectURL"] = location_header

                    for header, value in all_response_headers.items():
                        if header.lower() == "set-cookie":
                            parsed_cookie = SimpleCookie(value)
                            for cookie in parsed_cookie.items():  # type: tuple[str, Morsel]
                                har_entry_response["cookies"].append({"name": cookie[0], "value": cookie[1].value})

                    with suppress(asyncio.TimeoutError):
                        async with asyncio.timeout(
                            60
                        ):  # Wait for up to 60 seconds for the response body to be available
                            content = await response.body()
                            har_entry_response["bodySize"] = len(content)
                            content_type = all_response_headers.get("content-type", "")
                            har_entry_response["content"] = form_har_body(content_type, content)

                    simplified_response = [
                        f"Status Code: `{response.status}`",
                    ]
                    if formatted_response_headers := format_headers(all_response_headers):
                        simplified_response.extend(
                            ["Response Headers:", formatted_response_headers],
                        )
                else:
                    simplified_response = [
                        "No Response was received",
                    ]

                network_calls.append(
                    f'<network_call har-entry-index="{len(har_entries) - 1}">\n{"\n".join(simplified_request + simplified_response)}\n</network_call>'
                )
            except Exception:
                logger.exception(f"Error processing network call {index} {request.method} {request.url}")

        with open(har_file_path, "w") as f:
            json.dump(har_data, f, indent=2, ensure_ascii=False)

        return f'<network_calls har-file-path="{har_file_path}">\n{"\n".join(network_calls)}\n</network_calls>'

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
            list[Request]: A list of captured requests generated during the
            context manager's scope.
        """
        requests: list[Request] = []

        def capture_request(request_or_response: Request | Response):
            request: Request = (
                request_or_response.request if isinstance(request_or_response, Response) else request_or_response
            )

            if request.method == "OPTIONS" or request in requests:
                return

            request_url_hostname: Optional[str] = urlparse(request.url).hostname
            if only_domains:
                for filter_domain in only_domains:
                    if request_url_hostname is not None and request_url_hostname.endswith(filter_domain):
                        requests.append(request)
                        return
            else:
                requests.append(request)

        self.on("request", capture_request)
        self.on("requestfinished", capture_request)
        self.on("requestfailed", capture_request)
        self.on("response", capture_request)
        try:
            yield requests
        finally:
            self.off("request", capture_request)
            self.off("requestfinished", capture_request)
            self.off("requestfailed", capture_request)
            self.off("response", capture_request)


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

    filtered_headers = [
        f"\t`{k}`: `{v}`" for k, v in headers.items() if k.lower() in important_headers or k.lower().startswith("x-")
    ]

    if len(filtered_headers) == 0:
        return ""

    return "\n".join(filtered_headers)


def form_har_body(content_type: str, data: bytes):
    """
    Generates a formatted HAR (HTTP Archive) body representation for given content
    type and binary data. Handles encoding of the data as either UTF-8 text or
    Base64, based on its ability to be decoded as UTF-8.

    Parameters:
    content_type: str
        The MIME type of the data.
    data: bytes
        The binary data to be encoded and included in the HAR body.

    Returns:
    dict
        A dictionary containing the HAR body representation with fields 'mimeType',
        'text', and 'encoding'. The 'text' field will hold the data in either
        UTF-8 or Base64 encoding, and the 'encoding' field will specify the
        corresponding encoding method.

    Raises:
        UnicodeDecodeError: If the data cannot be decoded as UTF-8, it will
        automatically encode the data in Base64 without raising this error
        to the caller.
    """
    body_repr = {"mimeType": content_type}
    try:
        utf8_decoded_data = data.decode("utf-8")
        body_repr["text"] = utf8_decoded_data
        body_repr["encoding"] = "utf-8"
    except UnicodeDecodeError:
        base64_encoded_data = base64.b64encode(data).decode("utf-8")
        body_repr["text"] = base64_encoded_data
        body_repr["encoding"] = "base64"
    return body_repr


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
        A collection of network responses captured during the navigation and observations of the current state of the page after the navigation.
    """
    browser = await get_browser()
    async with browser.network_capture(only_domains=[browser.page_domain, extract_domain(url)]) as requests:
        await browser.page.goto(url)
        network_summary = await browser.simplify_requests_for_llm(requests)

    # Eagerly returning relevant observations to reduce agent tool calls
    observations = await browser_observe_page(
        f"{url} was just opened. "
        "give all important elements on the page that might be relevant to the next action. "
        "observe the overall state of the page to understand the purpose of the page."
    )
    return f"<observations>\n{"\n".join(observations)}\n</observations>\n{network_summary}"


@tool
async def browser_get_page_html() -> str:
    """
    Get the HTML content of the current page in the browser.

    Use this tool to retrieve the HTML content of the current page in the browser.

    Returns:
        The path of the downloaded HTML file artifact.
    """
    browser = await get_browser()
    page_html = await browser.page.content()
    html_artifact_file = os.path.join(browser.artifacts_dir, f"browser_page_{time.time_ns()}.html")
    with open(html_artifact_file, "w") as f:
        f.write(page_html)
    return f"HTML content saved to artifact: {html_artifact_file}"


@tool
async def browser_evaluate_js(expression: str):
    """
    Evaluate a javascript expression in the current page in the browser.

    Use this tool if you want to run some javascript in the browser.

    Examples:
        - `() => document.location.href`
        - `async () => { response = await fetch(location.href); return response.status; }`
        - `() => JSON.stringify(localStorage)`

    Args:
        expression (str): The javascript expression to evaluate. The expression has to be a function that returns a value.
    """
    browser = await get_browser()
    return await browser.page.evaluate(expression)


@tool
async def browser_get_cookies():
    """
    Get the current active cookies from the browser

    Use this tool to get all available cookies from the browser.

    Returns:
        str: A string in CSV format containing all the browser cookies, including
             attributes such as 'name', 'value', 'domain', 'path', 'expires',
             'httpOnly', 'secure', and 'sameSite'. If no cookies are found,
             a message string indicating this is returned.
    """
    browser = await get_browser()
    cookies = await browser.context.cookies()
    if len(cookies) == 0:
        return "No cookies found"

    csv_buffer = StringIO()
    writer = csv.DictWriter(
        csv_buffer, fieldnames=["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]
    )
    writer.writeheader()
    for cookie in cookies:
        writer.writerow(dict(cookie))

    return csv_buffer.getvalue()


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
        - A collection of network responses captured during the course of this action and observations of the current state of the page after the action
    """
    browser = await get_browser()
    async with browser.network_capture(only_domains=[browser.page_domain]) as requests:
        await browser.page.act(action)
        with contextlib.suppress(TimeoutError):
            await browser.page.wait_for_load_state("networkidle", timeout=60000)
        network_summary = await browser.simplify_requests_for_llm(requests)

    # Eagerly returning relevant observations to reduce agent tool calls
    observations = await browser_observe_page(
        f"`{action}` action was just performed. "
        "give all important elements on the page that might be relevant to the next action."
        "observe the overall state of the page to understand the purpose of the page."
    )
    return f"<observations>\n{'\n'.join(observations)}\n</observations>\n{network_summary}"


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
