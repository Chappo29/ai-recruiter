import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_VACANCY_NOT_FOUND = "Вакансия не найдена"
_RESUME_NOT_FOUND = "Резюме не найдено"
_HH_UNAVAILABLE = "HeadHunter временно недоступен. Повторите запрос позже."

RESUME_URL_RE = re.compile(
    r"^https?://(?:[\w-]+\.)?hh\.ru/resume/[a-zA-Z0-9]+$",
    re.IGNORECASE,
)
VACANCY_URL_RE = re.compile(
    r"^https?://(?:[\w-]+\.)?hh\.ru/vacancy/\d+",
    re.IGNORECASE,
)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}


def clean_hh_url(url: str) -> str:
    """Remove UTM and other query parameters from hh.ru URLs."""
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

_FETCH_RETRIES = 3
_RETRY_PAUSE_SEC = 1.0

_NOT_FOUND_MARKERS = (
    "resume not found",
    "vacancy not found",
    "такой страницы нет",
)


def _html_parser() -> str:
    try:
        import lxml  # noqa: F401

        return "lxml"
    except ImportError:
        return "html.parser"


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    return cleaned or None


def _element_text(element) -> str | None:
    if element is None:
        return None
    return _clean_text(element.get_text(separator="\n", strip=True))


def _validate_resume_url(url: str) -> str:
    normalized = url.strip()
    if not RESUME_URL_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_RESUME_NOT_FOUND,
        )
    return normalized


def _validate_vacancy_url(url: str) -> str:
    normalized = url.strip()
    if not VACANCY_URL_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_VACANCY_NOT_FOUND,
        )
    return normalized


def _log_hh_response_debug(response: httpx.Response) -> None:
    logger.error("STATUS: %s", response.status_code)
    logger.error("BODY: %s", response.text[:500])


def _raise_hh_status_error(
    url: str,
    status_code: int,
    response: httpx.Response | None = None,
) -> None:
    if response is not None:
        _log_hh_response_debug(response)
    else:
        logger.error("hh.ru вернул статус %s для %s", status_code, url)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"hh.ru вернул {status_code}",
    )


async def _fetch_html(
    url: str,
    not_found_detail: str,
    *,
    unavailable_detail: str = _HH_UNAVAILABLE,
    log_hh_status_on_error: bool = False,
) -> str:
    last_error: Exception | None = None
    saw_forbidden = False

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        for attempt in range(1, _FETCH_RETRIES + 1):
            try:
                response = await client.get(url)
                if log_hh_status_on_error:
                    _log_hh_response_debug(response)

                if response.status_code == 200:
                    pass
                elif response.status_code == 403:
                    saw_forbidden = True
                    last_error = httpx.HTTPStatusError(
                        "403 Forbidden",
                        request=response.request,
                        response=response,
                    )
                    if attempt < _FETCH_RETRIES:
                        logger.warning(
                            "HH returned 403 for %s (attempt %s/%s), retrying",
                            url,
                            attempt,
                            _FETCH_RETRIES,
                        )
                        await asyncio.sleep(_RETRY_PAUSE_SEC)
                        continue
                    logger.error(
                        "HH bot block (403) for %s after %s attempts",
                        url,
                        _FETCH_RETRIES,
                    )
                    if log_hh_status_on_error:
                        _raise_hh_status_error(url, 403, response)
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=unavailable_detail,
                    )

                elif response.status_code == 404:
                    if log_hh_status_on_error:
                        _raise_hh_status_error(url, 404, response)
                    logger.error("HH page not found (404): %s", url)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=not_found_detail,
                    )

                elif response.status_code >= 500:
                    last_error = httpx.HTTPStatusError(
                        f"{response.status_code} Server Error",
                        request=response.request,
                        response=response,
                    )
                    if attempt < _FETCH_RETRIES:
                        logger.warning(
                            "HH server error %s for %s (attempt %s/%s), retrying",
                            response.status_code,
                            url,
                            attempt,
                            _FETCH_RETRIES,
                        )
                        await asyncio.sleep(_RETRY_PAUSE_SEC)
                        continue
                    logger.error(
                        "HH server error %s for %s after %s attempts",
                        response.status_code,
                        url,
                        _FETCH_RETRIES,
                    )
                    if log_hh_status_on_error:
                        _raise_hh_status_error(url, response.status_code, response)
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=unavailable_detail,
                    )

                elif response.status_code != 200:
                    if log_hh_status_on_error:
                        _raise_hh_status_error(url, response.status_code, response)
                    response.raise_for_status()

                html = response.text.strip()
                if not html:
                    if log_hh_status_on_error:
                        _log_hh_response_debug(response)
                    logger.error("Empty HTML response from HH: %s", url)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=not_found_detail,
                    )

                lower_html = html.lower()
                if any(marker in lower_html for marker in _NOT_FOUND_MARKERS):
                    if log_hh_status_on_error:
                        _log_hh_response_debug(response)
                    logger.error("HH page content indicates not found: %s", url)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=not_found_detail,
                    )

                logger.info("Fetched HH page: %s", url)
                return html

            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    logger.error("HH page not found (404): %s", url)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=not_found_detail,
                    ) from exc
                last_error = exc
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = exc

            if attempt < _FETCH_RETRIES:
                logger.warning(
                    "HH fetch attempt %s/%s failed for %s: %s",
                    attempt,
                    _FETCH_RETRIES,
                    url,
                    last_error,
                )
                await asyncio.sleep(_RETRY_PAUSE_SEC)
            else:
                logger.error(
                    "HH fetch failed for %s after %s attempts: %s",
                    url,
                    _FETCH_RETRIES,
                    last_error,
                )

    if saw_forbidden:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=unavailable_detail,
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=not_found_detail,
    ) from last_error


def _parse_vacancy_html(html: str) -> dict[str, Any]:
    """Parse vacancy page HTML (hh.ru selectors 2025–2026)."""
    soup = BeautifulSoup(html, _html_parser())

    title_tag = soup.find("h1", {"data-qa": "vacancy-title"})
    title = title_tag.get_text(strip=True) if title_tag else None

    company_tag = soup.find("a", {"data-qa": "vacancy-company-name"})
    if not company_tag:
        company_tag = soup.find("span", {"data-qa": "vacancy-company-name"})
    company = company_tag.get_text(strip=True) if company_tag else None

    salary_tag = soup.find("span", {"data-qa": "vacancy-salary-compensation-type-net"})
    if not salary_tag:
        salary_tag = soup.find("div", {"data-qa": "vacancy-salary"})
    salary = salary_tag.get_text(strip=True) if salary_tag else None
    if salary:
        salary = re.sub(r"\s+", " ", salary).strip()

    desc_tag = soup.find("div", {"data-qa": "vacancy-description"})
    description = desc_tag.get_text(separator="\n", strip=True) if desc_tag else None

    requirements = None
    if description:
        markers = [
            "кого мы ищем",
            "требования",
            "что мы ожидаем",
            "необходимые навыки",
            "от кандидата",
        ]
        lower_desc = description.lower()
        for marker in markers:
            idx = lower_desc.find(marker)
            if idx != -1:
                end_markers = [
                    "условия",
                    "мы предлагаем",
                    "что мы предлагаем",
                    "бонус",
                ]
                end_idx = len(description)
                for end_marker in end_markers:
                    end = lower_desc.find(end_marker, idx)
                    if end != -1 and end < end_idx:
                        end_idx = end
                requirements = description[idx:end_idx].strip()
                break

    return {
        "title": title,
        "company": company,
        "salary": salary,
        "requirements": requirements,
        "description": description,
    }


def _extract_full_name(soup: BeautifulSoup) -> str | None:
    selectors = (
        '[data-qa="resume-personal-name"]',
        '[data-qa="resume-block-name"]',
        ".resume-header-name",
        ".resume-header-title h2",
        ".resume-header-title h1",
    )
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = _clean_text(element.get_text(separator=" ", strip=True))
            if text:
                return text

    header = soup.select_one(".resume-header, .resume-applicant")
    if header:
        for tag in ("h1", "h2"):
            element = header.find(tag)
            if element:
                text = _clean_text(element.get_text(separator=" ", strip=True))
                if text:
                    return text
    return None


def _extract_title(soup: BeautifulSoup) -> str | None:
    element = soup.select_one('h2[data-qa="resume-block-title-position"]')
    if element:
        return _clean_text(element.get_text(separator=" ", strip=True))
    element = soup.select_one('[data-qa="resume-block-title-position"]')
    if element:
        return _clean_text(element.get_text(separator=" ", strip=True))
    return None


def _extract_experience(soup: BeautifulSoup) -> str | None:
    block = soup.select_one('div[data-qa="resume-block-experience"]')
    if not block:
        return None
    return _clean_text(block.get_text(separator=" ", strip=True))


def _extract_skills(soup: BeautifulSoup) -> str | None:
    skill_nodes = soup.select('[data-qa="bloko-tag__text"]')
    if not skill_nodes:
        skill_nodes = soup.select(".bloko-tag__text, .bloko-tag span, .bloko-tag")
    skills: list[str] = []
    seen: set[str] = set()
    for node in skill_nodes:
        text = _clean_text(node.get_text(separator=" ", strip=True))
        if text and text.lower() not in seen:
            seen.add(text.lower())
            skills.append(text)
    if not skills:
        return None
    return ", ".join(skills)


def _extract_extra_blocks(soup: BeautifulSoup) -> list[str]:
    extra: list[str] = []
    block_selectors = (
        ('div[data-qa="resume-block-education"]', "Образование"),
        ('div[data-qa="resume-block-skills"]', "Навыки"),
        ('div[data-qa="resume-block-about"]', "О себе"),
        ('div[data-qa="resume-block-languages"]', "Языки"),
        ('div[data-qa="resume-block-contacts"]', "Контакты"),
    )
    for selector, _label in block_selectors:
        element = soup.select_one(selector)
        if element:
            text = _clean_text(element.get_text(separator=" ", strip=True))
            if text:
                extra.append(text)
    return extra


def _build_resume_text(
    full_name: str | None,
    title: str | None,
    experience: str | None,
    skills: str | None,
    extra_blocks: list[str],
) -> str | None:
    parts: list[str] = []
    for value in (full_name, title, experience, skills):
        if value:
            parts.append(value)
    for block in extra_blocks:
        if block and block not in parts:
            parts.append(block)
    if not parts:
        return None
    return " ".join(parts)


def _parse_resume_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, _html_parser())
    full_name = _extract_full_name(soup)
    title = _extract_title(soup)
    experience = _extract_experience(soup)
    skills = _extract_skills(soup)
    extra_blocks = _extract_extra_blocks(soup)
    resume_text = _build_resume_text(full_name, title, experience, skills, extra_blocks)
    return {
        "full_name": full_name,
        "title": title,
        "experience": experience,
        "skills": skills,
        "resume_text": resume_text,
    }


async def parse_vacancy(url: str) -> dict:
    url = clean_hh_url(url)
    vacancy_url = _validate_vacancy_url(url)
    logger.info("Parsing HH vacancy: %s", vacancy_url)
    html = await _fetch_html(
        vacancy_url,
        _VACANCY_NOT_FOUND,
        log_hh_status_on_error=True,
    )
    parsed = _parse_vacancy_html(html)
    logger.info(
        "Parsed: title=%s, company=%s",
        parsed.get("title"),
        parsed.get("company"),
    )
    return parsed


async def parse_resume(url: str) -> dict:
    resume_url = _validate_resume_url(url)
    logger.info("Parsing HH resume: %s", resume_url)
    html = await _fetch_html(resume_url, _RESUME_NOT_FOUND)
    parsed = _parse_resume_html(html)
    logger.info(
        "Parsed HH resume %s: name=%s title=%s",
        resume_url,
        parsed.get("full_name"),
        parsed.get("title"),
    )
    return parsed
