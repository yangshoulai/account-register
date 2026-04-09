import asyncio
import time

from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from pydoll.exceptions import ElementNotFound


async def wait_url(tab: Tab, url_flags: list[str], raise_exc: bool = True, timeout_sec: int = 10, interval_sec: int = 0.5) -> str | None:
    """等待页面跳转到指定 URL。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        current_url = (await tab.current_url or "").strip()
        for flag in url_flags:
            if flag in current_url:
                return current_url
        await asyncio.sleep(interval_sec)
    if raise_exc:
        raise ElementNotFound(f"等待网页 {url_flags} 超时")
    return None


async def wait_url_or_element(
        tab: Tab,
        url_flags: list[str],
        ele_selectors: list[str],
        raise_exc: bool = True,
        timeout_sec: int = 10,
        interval_sec: int = 0.5) -> tuple[str | None, WebElement | None]:
    """等待页面跳转到指定 URL 或元素出现。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        current_url = (await tab.current_url or "").strip()
        for flag in url_flags:
            if flag in current_url:
                return current_url, None
        for ele_selector in ele_selectors:
            element = await tab.query(ele_selector, raise_exc=False, timeout=0)
            if element:
                return None, element
        await asyncio.sleep(interval_sec)
    if raise_exc:
        raise ElementNotFound(f"等待网页 {url_flags} 或 元素 {ele_selectors} 超时")
    return None, None


async def get_live_value(input_el: WebElement | str, tab: Tab | None = None) -> str:
    if isinstance(input_el, str):
        if tab is None:
            raise ValueError("请指定 tab")
        input_el = await tab.query(input_el, raise_exc=False)
        if input_el is None:
            raise ElementNotFound(f"未找到元素 {input_el}")
    resp = await input_el.execute_script(
        "return (this.value ?? '').toString()",
        return_by_value=True,
    )
    return str(resp.get("result", {}).get("result", {}).get("value", "") or "")


async def ensure_input(tab: Tab, ele_selector: str, value: str, timeout_sec: int = 10, try_times: int = 3) -> bool:
    target_value = str(value)
    for index in range(try_times):
        input_el = await tab.query(ele_selector, timeout_sec)
        await input_el.focus()
        await input_el.clear()
        await input_el.type_text(target_value)
        await asyncio.sleep(0.5)
        current_value = await get_live_value(input_el)
        if current_value == target_value:
            return True
    return False
