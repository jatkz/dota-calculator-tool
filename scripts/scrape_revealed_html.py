#!/usr/bin/env python3
"""Click a reveal button on a page and save the rendered HTML.

This is meant for pages where the desired markup is only inserted or expanded
after a user interaction. It uses Playwright so the page's JavaScript runs the
same way it would in a real browser session.

Examples:
    python scripts/scrape_revealed_html.py "https://example.com" \
        --button-selector "button.show-stats" \
        --content-selector ".stats-panel" \
        --output stats-panel.html

    python scripts/scrape_revealed_html.py "https://example.com" \
        --button-text "Show more" \
        --output rendered-page.html \
        --full-page
"""

from __future__ import annotations

import argparse
from pathlib import Path


def debug_log(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[debug] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a page, click a button, and save the revealed HTML."
    )
    parser.add_argument("url", help="Page URL to open.")
    parser.add_argument(
        "--button-selector",
        help="CSS selector for the button or clickable element.",
    )
    parser.add_argument(
        "--button-text",
        help="Visible button text to click if a CSS selector is not convenient.",
    )
    parser.add_argument(
        "--exact-text",
        action="store_true",
        help="Require an exact text match when using --button-text.",
    )
    parser.add_argument(
        "--content-selector",
        help="CSS selector for the content that appears after the click.",
    )
    parser.add_argument(
        "--wait-text",
        action="append",
        default=[],
        help=(
            "Visible text to wait for after the click. "
            "Can be provided multiple times."
        ),
    )
    parser.add_argument(
        "--output",
        default="revealed.html",
        help="Where to write the resulting HTML. Defaults to revealed.html.",
    )
    parser.add_argument(
        "--browser",
        choices=("chromium", "firefox", "webkit"),
        default="chromium",
        help="Browser engine to use. Defaults to chromium.",
    )
    parser.add_argument(
        "--channel",
        choices=("chrome", "chrome-beta", "msedge", "msedge-beta", "msedge-dev"),
        help=(
            "Optional branded browser channel to launch instead of the bundled "
            "Playwright browser."
        ),
    )
    parser.add_argument(
        "--executable-path",
        help="Optional path to a browser executable to launch.",
    )
    parser.add_argument(
        "--cdp-url",
        help=(
            "Connect to an already running Chromium/Chrome instance over the "
            "Chrome DevTools Protocol, for example http://127.0.0.1:9222."
        ),
    )
    parser.add_argument(
        "--reuse-open-page",
        action="store_true",
        help=(
            "When using --cdp-url, reuse an already open tab whose URL starts "
            "with the requested URL."
        ),
    )
    parser.add_argument(
        "--page-index",
        type=int,
        help="When using --cdp-url, select a specific open page by index.",
    )
    parser.add_argument(
        "--target-index",
        type=int,
        help="When using --cdp-url, select a specific open page by flat target index.",
    )
    parser.add_argument(
        "--list-open-pages",
        action="store_true",
        help="When using --cdp-url, print open page indexes, titles, and URLs, then exit.",
    )
    parser.add_argument(
        "--skip-goto",
        action="store_true",
        help="Do not navigate to the URL; operate on the currently selected page.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=15000,
        help="Timeout for waits and clicks in milliseconds. Defaults to 15000.",
    )
    parser.add_argument(
        "--pre-click-wait-ms",
        type=int,
        default=0,
        help="Optional pause before clicking, in milliseconds.",
    )
    parser.add_argument(
        "--post-click-wait-ms",
        type=int,
        default=1500,
        help="Optional pause after clicking, in milliseconds. Defaults to 1500.",
    )
    parser.add_argument(
        "--wait-for-network-idle",
        action="store_true",
        help="Wait for network activity to settle after the click.",
    )
    parser.add_argument(
        "--force-click",
        action="store_true",
        help="Force the click even if Playwright thinks another element overlaps it.",
    )
    parser.add_argument(
        "--skip-click",
        action="store_true",
        help="Do not click anything; just save the current rendered page.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window instead of running headless.",
    )
    parser.add_argument(
        "--keep-open-ms",
        type=int,
        default=0,
        help="Keep the page open for inspection after the click, in milliseconds.",
    )
    parser.add_argument(
        "--full-page",
        action="store_true",
        help=(
            "Save the full rendered page HTML. By default, if --content-selector "
            "is provided, only that element's outer HTML is saved."
        ),
    )
    parser.add_argument(
        "--pre-screenshot",
        help="Optional screenshot path to capture before clicking.",
    )
    parser.add_argument(
        "--pre-output",
        help="Optional HTML path to save before clicking.",
    )
    parser.add_argument(
        "--screenshot",
        help="Optional screenshot path to capture after the click completes.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print browser/page progress and console errors while running.",
    )
    args = parser.parse_args()

    if (
        not args.skip_click
        and not args.list_open_pages
        and not args.button_selector
        and not args.button_text
    ):
        parser.error("Provide either --button-selector or --button-text.")

    return args


def build_click_target(page, args):
    if args.button_selector:
        return page.locator(args.button_selector).first

    button_by_role = page.get_by_role(
        "button",
        name=args.button_text,
        exact=args.exact_text,
    )
    if button_by_role.count() > 0:
        return button_by_role.first

    return page.get_by_text(args.button_text, exact=args.exact_text).first


def save_html(path: str, html: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def find_matching_page(browser, url: str):
    for context in browser.contexts:
        for page in context.pages:
            if page.url.startswith(url):
                return context, page
    return None, None


def iter_open_pages(browser):
    target_index = 0
    for context_index, context in enumerate(browser.contexts):
        for page_index, page in enumerate(context.pages):
            yield target_index, context_index, page_index, context, page
            target_index += 1


def main() -> int:
    args = parse_args()

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        raise SystemExit(
            "Playwright is not installed. Run "
            "'pip install playwright' and then 'playwright install chromium'."
        )

    with sync_playwright() as playwright:
        context = None
        page = None
        browser = None
        close_browser_on_exit = False
        close_page_on_exit = False

        if args.cdp_url:
            if args.browser != "chromium":
                raise SystemExit("--cdp-url can only be used with --browser chromium.")
            debug_log(args.debug, f"Connecting to existing browser at {args.cdp_url}")
            browser = playwright.chromium.connect_over_cdp(args.cdp_url)
            if args.list_open_pages:
                for target_index, context_index, page_index, _, open_page in iter_open_pages(browser):
                    try:
                        title = open_page.title()
                    except Exception:
                        title = "<unable to read title>"
                    print(
                        f"[target={target_index} context={context_index} page={page_index}] "
                        f"title={title!r} url={open_page.url}"
                    )
                return 0
            if args.target_index is not None:
                matched = False
                for target_index, _, _, context, open_page in iter_open_pages(browser):
                    if target_index == args.target_index:
                        page = open_page
                        matched = True
                        debug_log(
                            args.debug,
                            f"Using target index {args.target_index} at {page.url}",
                        )
                        break
                if not matched:
                    raise SystemExit(
                        f"No open page matched --target-index {args.target_index}. "
                        "Run with --list-open-pages first."
                    )
            elif args.page_index is not None:
                matched = False
                for _, _, page_index, context, open_page in iter_open_pages(browser):
                    if page_index == args.page_index:
                        page = open_page
                        matched = True
                        debug_log(args.debug, f"Using page index {args.page_index} at {page.url}")
                        break
                if not matched:
                    raise SystemExit(
                        f"No open page matched --page-index {args.page_index}. "
                        "Run with --list-open-pages first."
                    )
            if page is None and args.reuse_open_page:
                context, page = find_matching_page(browser, args.url)
                if page is not None:
                    debug_log(args.debug, f"Reusing open page at {page.url}")
            if page is None:
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = browser.new_context()
                page = context.new_page()
                close_page_on_exit = True
        else:
            browser_type = getattr(playwright, args.browser)
            launch_kwargs = {"headless": not args.headed}
            if args.channel:
                launch_kwargs["channel"] = args.channel
            if args.executable_path:
                launch_kwargs["executable_path"] = args.executable_path

            debug_log(
                args.debug,
                (
                    f"Launching browser={args.browser}, channel={args.channel or 'default'}, "
                    f"headed={args.headed}"
                ),
            )
            browser = browser_type.launch(**launch_kwargs)
            page = browser.new_page()
            close_browser_on_exit = True

        page.set_default_timeout(args.timeout_ms)

        if args.debug:
            page.on(
                "console",
                lambda msg: print(f"[console:{msg.type}] {msg.text}"),
            )
            page.on(
                "pageerror",
                lambda exc: print(f"[pageerror] {exc}"),
            )
            page.on(
                "requestfailed",
                lambda request: print(f"[requestfailed] {request.method} {request.url}"),
            )

        try:
            if not args.skip_goto:
                debug_log(args.debug, f"Opening {args.url}")
                page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                debug_log(args.debug, f"Loaded title={page.title()!r} url={page.url}")
            else:
                debug_log(args.debug, f"Using current page title={page.title()!r} url={page.url}")

            if args.pre_output:
                debug_log(args.debug, f"Saving pre-click HTML to {args.pre_output}")
                save_html(args.pre_output, page.content())

            if args.pre_screenshot:
                pre_screenshot_path = Path(args.pre_screenshot)
                pre_screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                debug_log(args.debug, f"Saving pre-click screenshot to {args.pre_screenshot}")
                page.screenshot(path=str(pre_screenshot_path), full_page=True)

            if args.pre_click_wait_ms > 0:
                debug_log(args.debug, f"Waiting {args.pre_click_wait_ms}ms before click")
                page.wait_for_timeout(args.pre_click_wait_ms)

            if not args.skip_click:
                click_target = build_click_target(page, args)
                debug_log(args.debug, "Waiting for click target to become visible")
                click_target.wait_for(state="visible", timeout=args.timeout_ms)
                click_target.scroll_into_view_if_needed(timeout=args.timeout_ms)
                if args.debug:
                    target_html = click_target.evaluate("element => element.outerHTML")
                    debug_log(args.debug, f"Click target snippet: {target_html[:500]}")

                debug_log(args.debug, f"Clicking target force={args.force_click}")
                click_target.click(timeout=args.timeout_ms, force=args.force_click)

            if args.wait_for_network_idle and not args.skip_click:
                debug_log(args.debug, "Waiting for network to become idle")
                page.wait_for_load_state("networkidle", timeout=args.timeout_ms)

            if args.content_selector:
                debug_log(args.debug, f"Waiting for content selector {args.content_selector}")
                page.locator(args.content_selector).first.wait_for(
                    state="visible",
                    timeout=args.timeout_ms,
                )

            for wait_text in args.wait_text:
                debug_log(args.debug, f"Waiting for text {wait_text!r}")
                page.get_by_text(wait_text).first.wait_for(
                    state="visible",
                    timeout=args.timeout_ms,
                )

            if args.post_click_wait_ms > 0:
                debug_log(args.debug, f"Waiting {args.post_click_wait_ms}ms after click")
                page.wait_for_timeout(args.post_click_wait_ms)

            if args.keep_open_ms > 0:
                debug_log(args.debug, f"Keeping page open for {args.keep_open_ms}ms")
                page.wait_for_timeout(args.keep_open_ms)

            if args.screenshot:
                screenshot_path = Path(args.screenshot)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                debug_log(args.debug, f"Saving post-click screenshot to {args.screenshot}")
                page.screenshot(path=str(screenshot_path), full_page=True)

            if args.content_selector and not args.full_page:
                html = page.locator(args.content_selector).first.evaluate(
                    "element => element.outerHTML"
                )
            else:
                html = page.content()

            debug_log(args.debug, f"Saving HTML to {args.output}")
            save_html(args.output, html)
            print(f"Saved HTML to {Path(args.output).resolve()}")
            return 0
        except PlaywrightTimeoutError as exc:
            raise SystemExit(
                "Timed out while interacting with the page. "
                "Double-check the URL, selectors, and timeout values."
            ) from exc
        except Exception as exc:
            error_text = str(exc)
            if args.cdp_url and "ECONNREFUSED" in error_text:
                raise SystemExit(
                    "Could not connect to Chrome DevTools at "
                    f"{args.cdp_url}. Make sure Chrome was started with "
                    "--remote-debugging-port=9222 in a fresh process. On Windows, "
                    "fully close Chrome first or launch a separate instance with "
                    '--user-data-dir="C:\\temp\\chrome-cdp-profile".'
                ) from exc
            raise SystemExit(f"Scrape failed: {type(exc).__name__}: {exc}") from exc
        finally:
            if close_page_on_exit and page is not None:
                page.close()
            if close_browser_on_exit and browser is not None:
                browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
