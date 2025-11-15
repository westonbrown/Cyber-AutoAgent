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
from http.cookies import SimpleCookie
from typing import Optional, Any, Union
from urllib.parse import urlparse, parse_qs
from modules import __version__

from playwright.async_api import (
    Page,
    BrowserContext,
    Response,
    TimeoutError,
    Request,
    Dialog,
    Download,
    ConsoleMessage,
)
from pymitter import EventEmitter
from six import StringIO
from stagehand import StagehandConfig, Stagehand, StagehandPage
from stagehand.context import StagehandContext
from strands import tool
from tldextract import tldextract

logger = logging.getLogger(__name__)
_TOON_PREVIEW_LIMIT = 10
_BROWSER_RETRIABLE_ERRORS = (
    "Execution context was destroyed",
    "Most likely because of a navigation",
    "browser has been closed",
    "Target closed",
)


def _sanitize_toon_value(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    return text.replace(",", ";")


def format_toon_table(name: str, columns: list[str], rows: list[dict[str, Any]]) -> str:
    """Render a compact TOON table for LLM-friendly structured summaries."""
    if not rows:
        return ""
    header = ",".join(columns)
    lines = [f"{name}[{len(rows)}]{{{header}}}:"]
    for row in rows:
        values = [_sanitize_toon_value(row.get(column, "")) for column in columns]
        lines.append(f"  {','.join(values)}")
    return "\n".join(lines)


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
    default_timeout: float
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
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-smooth-scrolling",
            ],
        }

        if extra_http_headers:
            launch_options["extra_http_headers"] = extra_http_headers

        if self.artifacts_dir:
            launch_options["downloads_path"] = os.path.join(
                self.artifacts_dir, "browser_downloads"
            )
            launch_options["user_data_dir"] = os.path.join(
                self.artifacts_dir, "browser_profile"
            )
            launch_options["record_har_content"] = "embed"
            launch_options["record_har_mode"] = "full"
            launch_options["record_har_path"] = os.path.join(
                self.artifacts_dir, "browser_network.har"
            )
        else:
            logger.warning(
                "No artifacts_dir provided. Browser will not persist network traffic, profile, downloads to artifacts."
            )

        self.default_timeout = float(os.getenv("BROWSER_DEFAULT_TIMEOUT", "120000"))
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

    @asynccontextmanager
    async def timeout(self):
        async with asyncio.timeout((self.default_timeout / 1000) + 5):
            yield

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

        logger.info("Initializing browser")
        await self.stagehand.init()
        self._initialized = True

        self.context.set_default_timeout(self.default_timeout)
        self.context.set_default_navigation_timeout(self.default_timeout)

        self.page.set_default_timeout(self.default_timeout)
        self.page.set_default_navigation_timeout(self.default_timeout)

        async def handle_dialog(dialog: Dialog):
            """Auto accept all dialogs"""
            await dialog.accept()
            await self.emit_async("dialog", dialog)

        async def handle_download(download: Download):
            """Auto-save downloads to artifacts_dir"""
            download_path = os.path.join(
                self.artifacts_dir,
                f"download_{time.time_ns()}_{download.suggested_filename}",
            )
            await download.save_as(download_path)
            await self.emit_async("download", download_path)

        self.page.on("dialog", handle_dialog)
        self.page.on("download", handle_download)

        for event_name in (
            "request",
            "response",
            "requestfailed",
            "requestfinished",
            "console",
        ):  # type: Any
            self.page.on(
                event_name,
                functools.partial(
                    lambda event, payload: self.emit_async(event, payload), event_name
                ),
            )

    async def reset(self):
        """Reset the Stagehand session if the browser context becomes invalid."""
        if self._initialized:
            try:
                await self.stagehand.close()
            except Exception as exc:
                logger.warning("Browser reset encountered error while closing: %s", exc)
        self._initialized = False
        await self.ensure_init()

    async def simplify_metadata_for_llm(
        self,
        requests: list[Request],
        downloads: list[str],
        logs: list[dict[str, Any]],
        dialogs: list[dict[str, Any]],
    ) -> str:
        """
        Processes logs, dialogs, downloads, and requests to generate summarized metadata formatted
        for use in an LLM. The metadata includes information about console logs, dialogs, downloaded
        files, and requests.

        Parameters:
            requests: A list of Request objects to be summarized.
            downloads: A list of file paths corresponding to downloaded files.
            logs: A list of dictionaries containing log entries, where each dictionary includes information
                  about log type and arguments.
            dialogs: A list of dictionaries representing dialog entries, each containing a type and message.

        Returns:
            str: A string containing summarized metadata formatted for LLM consumption.

        Raises:
            Any exceptions encountered during file writing, JSON serialization, or processing of logs,
            dialogs, downloads, or requests will be propagated.
        """
        metadata = []

        if len(logs) > 0:
            logs_summary = "\n".join(
                map(
                    lambda log: f"[{log['type']}] {' '.join(map(lambda arg: json.dumps(arg), log['args']))}".strip(),
                    logs,
                )
            )
            log_file = os.path.join(self.artifacts_dir, f"logs_{time.time_ns()}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(logs_summary)
            rows = []
            for idx, log in enumerate(logs[:_TOON_PREVIEW_LIMIT], start=1):
                args_preview = (
                    " ".join(json.dumps(arg, ensure_ascii=False) for arg in log["args"])
                    or "-"
                )
                if len(args_preview) > 160:
                    args_preview = args_preview[:157] + "..."
                rows.append(
                    {
                        "#": idx,
                        "type": log["type"],
                        "args": args_preview,
                        "artifact": os.path.basename(log_file),
                    }
                )
            toon_section = format_toon_table(
                "console_logs", ["#", "type", "args", "artifact"], rows
            )
            metadata.append(f"{toon_section}\n[Full console logs saved to {log_file}]")

        if len(dialogs) > 0:
            rows = []
            for idx, dialog in enumerate(dialogs[:_TOON_PREVIEW_LIMIT], start=1):
                message = dialog.get("message", "")
                if len(message) > 160:
                    message = message[:157] + "..."
                rows.append(
                    {"#": idx, "type": dialog.get("type", ""), "message": message}
                )
            toon_section = format_toon_table("dialogs", ["#", "type", "message"], rows)
            metadata.append(toon_section)

        if len(downloads) > 0:
            rows = [
                {"#": idx, "path": download_path}
                for idx, download_path in enumerate(
                    downloads[:_TOON_PREVIEW_LIMIT], start=1
                )
            ]
            toon_section = format_toon_table("downloaded_files", ["#", "path"], rows)
            metadata.append(toon_section)

        if len(requests) > 0:
            requests_summary = await self.simplify_requests_for_llm(requests)
            if requests_summary:
                metadata.append(requests_summary)

        return "\n".join(metadata)

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
        summary_rows: list[dict[str, Any]] = []
        har_entries: list[dict] = []

        har_file_path = os.path.join(
            self.artifacts_dir, f"network_calls_{time.time_ns()}.har"
        )

        har_data = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "Cyber-AutoAgent",
                    "version": __version__,
                    "comment": "",
                },
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
                        else pw_timings["domainLookupEnd"]
                        - pw_timings["domainLookupStart"]
                    ),
                    "connect": (
                        -1
                        if pw_timings["connectEnd"] == -1
                        else pw_timings["connectEnd"] - pw_timings["connectStart"]
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
                        else pw_timings["requestStart"]
                        - pw_timings["secureConnectionStart"]
                    ),
                }

                total_time_taken = sum(
                    [time_value for time_value in timings.values() if time_value > 0], 0
                )
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
                        "headers": [
                            {"name": k, "value": v}
                            for k, v in all_request_headers.items()
                        ],
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
                            har_entry["request"]["queryString"].append(
                                {"name": name, "value": value}
                            )

                if cookie_header := all_request_headers.get("cookie"):
                    parsed_cookie = SimpleCookie(cookie_header)
                    for cookie in parsed_cookie.items():  # type: tuple[str, Morsel]
                        har_entry["request"]["cookies"].append(
                            {"name": cookie[0], "value": cookie[1].value}
                        )

                simplified_request = [
                    f"`{request.method}` `{request.url}`",
                ]

                if formatted_request_headers := format_headers(all_request_headers):
                    simplified_request.extend(
                        ["Request Headers:", formatted_request_headers]
                    )

                if request_body := request.post_data_buffer:
                    har_entry["request"]["bodySize"] = len(request_body)
                    post_data = har_entry["request"]["postData"] = form_har_body(
                        request.headers.get("content-type", ""), request_body
                    )
                    if post_data["encoding"] == "utf-8":
                        simplified_request.append(
                            f"Request Body: ```{post_data['text']}```"
                        )
                    else:
                        simplified_request.append("Request Body: Non-UTF8 Binary")

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
                        "headers": [
                            {"name": k, "value": v}
                            for k, v in all_response_headers.items()
                        ],
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
                                har_entry_response["cookies"].append(
                                    {"name": cookie[0], "value": cookie[1].value}
                                )

                    with suppress(asyncio.TimeoutError):
                        async with asyncio.timeout(
                            60
                        ):  # Wait for up to 60 seconds for the response body to be available
                            content = await response.body()
                            har_entry_response["bodySize"] = len(content)
                            content_type = all_response_headers.get("content-type", "")
                            har_entry_response["content"] = form_har_body(
                                content_type, content
                            )

                    simplified_response = [
                        f"Status Code: `{response.status}`",
                    ]
                    if formatted_response_headers := format_headers(
                        all_response_headers
                    ):
                        simplified_response.extend(
                            ["Response Headers:", formatted_response_headers],
                        )
                else:
                    simplified_response = [
                        "No Response was received",
                    ]

                body_size = -1
                if response:
                    try:
                        body_size = har_entry["response"].get("bodySize", -1)
                    except Exception:
                        body_size = -1

                summary_rows.append(
                    {
                        "#": len(summary_rows) + 1,
                        "method": request.method,
                        "host": parsed_url.hostname or "",
                        "path": parsed_url.path or "/",
                        "status": response.status if response else "n/a",
                        "bytes": body_size,
                    }
                )

                network_call_stringified = "\n".join(
                    simplified_request + simplified_response
                )
                network_calls.append(
                    f'<network_call har-entry-index="{len(har_entries) - 1}">\n{network_call_stringified}\n</network_call>'
                )
            except Exception:
                logger.exception(
                    f"Error processing network call {index} {request.method} {request.url}"
                )

        if len(har_entries) == 0:
            return ""

        with open(har_file_path, "w", encoding="utf-8") as f:
            json.dump(har_data, f, indent=2, ensure_ascii=False)

        network_preview = network_calls[:_TOON_PREVIEW_LIMIT]
        network_calls_stringified = "\n".join(network_preview)
        if len(network_calls) > _TOON_PREVIEW_LIMIT:
            network_calls_stringified += f"\n...[{len(network_calls) - _TOON_PREVIEW_LIMIT} additional calls truncated]"

        toon_section = format_toon_table(
            "network_calls",
            ["#", "method", "host", "path", "status", "bytes"],
            summary_rows[:_TOON_PREVIEW_LIMIT],
        )
        segments = [
            toon_section,
            f"[Full HAR saved to {har_file_path}]",
            f'<network_calls har-file="{har_file_path}">\n{network_calls_stringified}\n</network_calls>',
        ]
        return "\n".join(filter(None, segments))

    @asynccontextmanager
    async def interaction_context_capture(
        self, only_domains: Optional[list[str]] = None
    ):
        """
        An asynchronous context manager for capturing various web interactions including network requests, downloads,
        console messages, and dialog events. Allows optional filtering of network requests based on specified domains.
        The captured data is organized and simplified into a structure that includes requests, downloads, logs, and dialogs.

        Parameters:
            only_domains (Optional[list[str]]): A list of domain filters to capture requests only for specific domains.
            If None, all requests are captured.

        Yields:
            Any: A simplified metadata object containing captured requests, downloads, logs, and dialogs.

        Context Behavior:
            - On context entry, sets up event listeners to capture specified web  interactions.
            - On context exit, removes the event listeners to prevent further interception of events.
        """
        requests: list[Request] = []
        downloads: list[str] = []
        logs: list[dict[str, Any]] = []
        dialogs: list[dict[str, Any]] = []

        def capture_request(request_or_response: Request | Response):
            """
            Captures an HTTP request or a response's associated request and stores it.

            This function checks the provided input, which can be either an HTTP `Request`
            or a `Response`. If the input is a `Response`, its associated request is captured.
            It ensures that the captured request is added to a maintained list of requests only
            if specific criteria are met, such as the request method being neither `OPTIONS`
            nor already captured, and optionally filtered by domain names.

            Parameters:
                request_or_response: Request | Response
                    The HTTP `Request` object or a `Response` object whose request needs
                    to be captured.
            """
            request: Request = (
                request_or_response.request
                if isinstance(request_or_response, Response)
                else request_or_response
            )
            if request.method == "OPTIONS" or request in requests:
                return

            request_url_hostname: Optional[str] = urlparse(request.url).hostname
            if only_domains:
                for filter_domain in only_domains:
                    if (
                        request_url_hostname is not None
                        and request_url_hostname.endswith(filter_domain)
                    ):
                        requests.append(request)
                        return
            else:
                requests.append(request)

        async def capture_log(msg: ConsoleMessage):
            """
            Asynchronously captures a console log message.

            This function processes a console message, extracts its arguments,
            and converts them into JSON-compatible values. The resulting JSON values
            and the type of the console message are then stored in a log entry.

            Parameters:
                msg (ConsoleMessage): The console message to be captured.

            Raises:
                None

            Returns:
                None
            """
            args: list[Any] = []
            for arg in msg.args:
                args.append(await arg.json_value())
            logs.append(
                {
                    "type": msg.type,
                    "args": args,
                }
            )

        def capture_download(file_path: str):
            downloads.append(file_path)

        def capture_dialog(dialog: Dialog):
            dialogs.append(
                {
                    "type": dialog.type,
                    "message": dialog.message,
                    "default_value": dialog.default_value,
                }
            )

        self.on("request", capture_request)
        self.on("requestfinished", capture_request)
        self.on("requestfailed", capture_request)
        self.on("response", capture_request)
        self.on("console", capture_log)
        self.on("download", capture_download)
        self.on("dialog", capture_dialog)
        try:
            yield await self.simplify_metadata_for_llm(
                requests, downloads, dialogs, logs
            )
        finally:
            self.off("request", capture_request)
            self.off("requestfinished", capture_request)
            self.off("requestfailed", capture_request)
            self.off("response", capture_request)
            self.off("console", capture_log)
            self.off("download", capture_download)
            self.off("dialog", capture_dialog)


_BROWSER: Optional[BrowserService] = None
_BROWSER_LOCK = asyncio.Lock()


def initialize_browser(
    provider: str,
    model: str,
    artifacts_dir: Optional[str] = None,
    extra_http_headers: Optional[dict[str, str]] = None,
):
    """Initialize the shared browser instance.

    If CYBER_BROWSER_DEFAULT_HEADERS=true, apply a safe default set of headers
    (desktop User-Agent and Accept-Language). Provided extra_http_headers, if any,
    will override the defaults on a per-key basis.
    """
    logger.info("[BROWSER] initialized")

    # Optional default headers toggleable via env
    if os.getenv("CYBER_BROWSER_DEFAULT_HEADERS", "false").lower() == "true":
        defaults = {
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "accept-language": "en-US,en;q=0.9",
        }
        # Merge: caller-provided headers override defaults
        if isinstance(extra_http_headers, dict):
            merged = {
                **defaults,
                **{k.lower(): v for k, v in extra_http_headers.items()},
            }
        else:
            merged = defaults
        extra_http_headers = merged

    global _BROWSER
    _BROWSER = BrowserService(provider, model, artifacts_dir, extra_http_headers)
    return _BROWSER


@asynccontextmanager
async def get_browser():
    """
    An asynchronous context manager to access the browser instance.

    This function provides access to a shared browser instance. It ensures the
    browser has been initialized and acquires a lock to guarantee safe usage
    across asynchronous operations. It also ensures the browser initialization
    is complete before yielding the instance. Locking is required because the
    LLM ends up calling multiple tools in parallel sometimes.

    Raises:
        ValueError: If the browser instance has not been initialized.

    Yields:
        The initialized browser instance ready for use.
    """
    if not _BROWSER:
        raise ValueError(
            "Browser not initialized. Please call initialize_browser first."
        )

    async with _BROWSER_LOCK:
        await _BROWSER.ensure_init()
        yield _BROWSER


def format_headers(headers: dict[str, str]) -> str:
    """
    Formats HTTP headers into a string representation including only relevant headers.

    Parameters:
        headers: dict[str, str]
            A dictionary containing HTTP headers as key-value pairs.

    Returns:
        str
            A formatted string containing the filtered and formatted HTTP headers.
    """
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
        f"\t`{k}`: `{v}`"
        for k, v in headers.items()
        if k.lower() in important_headers or k.lower().startswith("x-")
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
async def browser_set_headers(headers: Optional[dict[str, str]] = None):
    """
    Set headers that need to be sent with all requests from the browser

    Parameters:
        headers (dict[str, str]): the headers to be sent with all requests

    Notes:
        - Accepts an empty object. If omitted or empty, no changes are applied and a helpful
          message is returned so the agent can call again with a non-empty map.
    """
    async with get_browser() as browser:
        if not headers:
            return "No headers provided. Please call browser_set_headers with a non-empty map, e.g. {'user-agent': '...'}"
        await browser.context.set_extra_http_headers(headers)
        return f"Applied {len(headers)} extra HTTP header(s) to the browser context"


@tool
async def browser_goto_url(url: str):
    """
    Navigate the browser to a specified URL and capture network responses.

    Use this tool when you need to open a URL in a browser. This is useful for SPAs where the full page is only rendered
    with javascript and requires a browser to access.

    Args:
        url: The URL to navigate to.

    Returns:
        - Any Network requests, dialogs, console logs and downloads captured during the navigation.
        - Observations of the current page state after the navigation.
        - If navigation fails due to timeouts/blocks, an HTTP fallback summary (headers and key files) is returned.
    """
    logger.info("[BROWSER] entered goto url")
    async with get_browser() as browser:
        reset_notice: Optional[str] = None

        async def _http_fallback(reason: str) -> str:
            parsed = urlparse(url)
            origin = (
                f"{parsed.scheme}://{parsed.netloc}"
                if parsed.scheme and parsed.netloc
                else url
            )
            targets = [url]
            # Try common reconnaissance files
            if parsed.scheme and parsed.netloc:
                targets += [
                    f"{origin}/robots.txt",
                    f"{origin}/.well-known/security.txt",
                ]

            rows = []
            artifacts = []
            waf_detected = False
            for idx, t in enumerate(targets, start=1):
                try:
                    # Provide generic desktop headers to reduce basic bot blocking
                    req_headers = {
                        "user-agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "accept-language": "en-US,en;q=0.9",
                    }
                    async with browser.timeout():
                        resp = await browser.context.request.get(
                            t, timeout=15000, headers=req_headers
                        )
                    status = resp.status
                    # Playwright Python APIResponse exposes headers as a property/dict
                    try:
                        headers = resp.headers  # type: ignore[attr-defined]
                    except Exception:
                        headers = {}
                    # Always attempt to capture a body preview, even on error, for WAF pages
                    try:
                        text_body = await resp.text()
                    except Exception:
                        text_body = ""
                    # Persist a compact artifact for each fetched resource
                    artifact_path = os.path.join(
                        browser.artifacts_dir,
                        f"http_fallback_{time.time_ns()}_{idx}.txt",
                    )
                    preview = text_body[:2000] if isinstance(text_body, str) else ""
                    with open(artifact_path, "w", encoding="utf-8") as fh:
                        fh.write(
                            "\n".join(
                                [
                                    f"URL: {t}",
                                    f"Status: {status}",
                                    "Headers:",
                                    format_headers(headers) or "(none)",
                                    "\nBody (first 2000 chars):\n" + preview
                                    if preview
                                    else "\n(No body captured)",
                                ]
                            )
                        )
                    artifacts.append(artifact_path)
                    # Detect Cloudflare/WAF via headers/body hints
                    try:
                        server_header = str((headers or {}).get("server", "")).lower()
                        cf_ray = (headers or {}).get("cf-ray") or (headers or {}).get(
                            "cf_ray"
                        )
                        if (
                            "cloudflare" in server_header
                            or cf_ray
                            or (
                                isinstance(text_body, str)
                                and "cloudflare" in text_body.lower()
                            )
                        ):
                            waf_detected = True
                    except Exception:
                        pass
                    rows.append(
                        {
                            "#": idx,
                            "url": t,
                            "status": status,
                            "bytes": len(text_body)
                            if isinstance(text_body, str)
                            else 0,
                            "artifact": os.path.basename(artifact_path),
                        }
                    )
                except Exception as fetch_exc:
                    rows.append(
                        {
                            "#": idx,
                            "url": t,
                            "status": "error",
                            "bytes": 0,
                            "artifact": str(fetch_exc),
                        }
                    )

            toon = format_toon_table(
                "http_fallback", ["#", "url", "status", "bytes", "artifact"], rows
            )
            waf_note = " Detected Cloudflare/WAF indicators." if waf_detected else ""
            banner = f"[HTTP fallback executed] Reason: {reason}. Fetched {len(rows)} resource(s).{waf_note}"
            return "\n".join([banner, toon])

        async def _perform_navigation():
            async with browser.interaction_context_capture(
                only_domains=[browser.page_domain, extract_domain(url)]
            ) as interaction_context:
                async with browser.timeout():
                    await browser.page.goto(url)

            async with browser.timeout():
                observations = "\n".join(
                    map(
                        lambda obs: obs.description,
                        await browser.page.observe(
                            f"{url} was just opened. "
                            "give all important elements on the page that might be relevant to the next action. "
                            "observe the overall state of the page to understand the purpose of the page."
                        ),
                    )
                )
            return f"<observations>\n{observations}\n</observations>\n{interaction_context}"

        for attempt in range(2):
            try:
                payload = await _perform_navigation()
                if reset_notice:
                    payload = f"{reset_notice}\n{payload}"
                return payload
            except TimeoutError:
                # Navigation timed out: perform a light reset once, then fallback
                if attempt == 0:
                    logger.warning(
                        "Browser navigation timeout; resetting browser and retrying once"
                    )
                    await browser.reset()
                    reset_notice = "[Browser reset applied] Navigation timeout; retrying after session reset."
                    continue
                # Fallback to HTTP fetch
                return await _http_fallback("navigation timeout")
            except Exception as exc:
                message = str(exc)
                should_retry = any(
                    token in message for token in _BROWSER_RETRIABLE_ERRORS
                )
                if attempt == 0 and should_retry:
                    logger.warning(
                        "Browser navigation failed (%s); resetting browser and retrying once",
                        exc,
                    )
                    await browser.reset()
                    reset_notice = "[Browser reset applied] Execution context was destroyed; retry succeeded after session reset."
                    continue
                # On non-retriable errors (e.g., WAF/blocked), use HTTP fallback to at least collect headers
                return await _http_fallback(message or "navigation error")


@tool
async def browser_get_page_html() -> str:
    """
    Get the HTML content of the current page in the browser.

    Use this tool to retrieve the HTML content of the current page in the browser.

    Returns:
        The path of the downloaded HTML file artifact.
    """
    async with get_browser() as browser:
        async with browser.timeout():
            page_html = await browser.page.content()
        html_artifact_file = os.path.join(
            browser.artifacts_dir, f"browser_page_{time.time_ns()}.html"
        )
        with open(html_artifact_file, "w", encoding="utf-8") as f:
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

    Returns:
        The result of the javascript expression.
    """
    async with get_browser() as browser:
        async with browser.timeout():
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
    async with get_browser() as browser:
        async with browser.timeout():
            cookies = await browser.context.cookies()
        if len(cookies) == 0:
            return "No cookies found"

        csv_buffer = StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=[
                "name",
                "value",
                "domain",
                "path",
                "expires",
                "httpOnly",
                "secure",
                "sameSite",
            ],
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
        - Any Network requests, dialogs, console logs and downloads captured during the interaction.
        - Observations of the current page state after the interaction.
    """
    async with get_browser() as browser:
        async with browser.interaction_context_capture(
            only_domains=[browser.page_domain]
        ) as interaction_context:
            async with browser.timeout():
                await browser.page.act(action)
            with contextlib.suppress(TimeoutError):
                await browser.page.wait_for_load_state("networkidle", timeout=60000)

        # Eagerly returning relevant observations to reduce agent tool calls
        async with browser.timeout():
            observations = "\n".join(
                map(
                    lambda obs: obs.description,
                    await browser.page.observe(
                        f"`{action}` action was just performed. "
                        "give all important elements on the page that might be relevant to the next action."
                        "observe the overall state of the page to understand the purpose of the page."
                    ),
                )
            )
        return f"<observations>\n{observations}\n</observations>\n{interaction_context}"


@tool
async def browser_observe_page(instruction: Optional[str] = None) -> list[str]:
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
    async with get_browser() as browser:
        async with browser.timeout():
            observations = await browser.page.observe(instruction)
        return [observation.description for observation in observations]
