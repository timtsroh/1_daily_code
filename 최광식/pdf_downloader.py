#!/usr/bin/env python
"""
pdf_downloader.py
bit.ly 링크를 따라가 PDF를 다운로드하고, 페이지 수를 추출한다.

- bit.ly → 리다이렉트 따라감 (최종 URL은 bbs2.daolsec.com 또는 유사 도메인).
- `Content-Type: application/pdf` 가 아닌 경우는 PDF가 아니므로 스킵.
- 페이지 수는 pypdf로 읽고, 실패 시 바이너리 `/Type /Page` 카운트로 폴백.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_PAGE_RE = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


@dataclass
class PdfDownloadResult:
    ok: bool
    reason: str = ""                 # "not_pdf", "http_error", "empty", ""(성공)
    final_url: str = ""
    content_type: str = ""
    temp_path: Optional[Path] = None
    page_count: Optional[int] = None


def _count_pages_pypdf(path: Path) -> Optional[int]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        return len(reader.pages)
    except Exception:
        return None


def _count_pages_regex(path: Path) -> Optional[int]:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    count = len(_PAGE_RE.findall(data))
    return count or None


def count_pages(path: Path) -> Optional[int]:
    """pypdf 우선, 실패 시 바이너리 정규식 폴백."""
    n = _count_pages_pypdf(path)
    if n:
        return n
    return _count_pages_regex(path)


def resolve_and_download(url: str, timeout: float = 30.0) -> PdfDownloadResult:
    """bit.ly URL을 따라가 PDF를 임시 파일로 저장.

    PDF가 아니면 `ok=False`, 이유를 기록한다.
    호출자가 임시 파일을 이동·삭제한다.
    """
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            # 1) HEAD로 먼저 content-type을 보면 빠르지만, 일부 서버는 HEAD를 막거나
            #    리다이렉트 Location을 정확히 주지 않는다. 스트리밍 GET으로 통일.
            with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    return PdfDownloadResult(
                        ok=False,
                        reason=f"http_{resp.status_code}",
                        final_url=str(resp.url),
                    )
                final_url = str(resp.url)
                ctype = (resp.headers.get("content-type") or "").lower()
                if "application/pdf" not in ctype:
                    # 일부 서버가 `application/octet-stream`로 내려보내는 경우가 있을 수 있다.
                    # URL이 .pdf로 끝나는 경우까지는 허용.
                    if not (final_url.lower().endswith(".pdf")
                            or "pdf" in ctype and "octet" in ctype):
                        return PdfDownloadResult(
                            ok=False,
                            reason="not_pdf",
                            final_url=final_url,
                            content_type=ctype,
                        )

                # 임시 파일로 스트리밍 저장
                tmp = tempfile.NamedTemporaryFile(
                    prefix="choi_",
                    suffix=".pdf",
                    delete=False,
                )
                tmp_path = Path(tmp.name)
                size = 0
                try:
                    for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                        if chunk:
                            tmp.write(chunk)
                            size += len(chunk)
                finally:
                    tmp.close()

                if size == 0:
                    tmp_path.unlink(missing_ok=True)
                    return PdfDownloadResult(
                        ok=False,
                        reason="empty",
                        final_url=final_url,
                        content_type=ctype,
                    )

                # 앞 5바이트가 "%PDF-"인지 검증 (빗나간 HTML 방어)
                try:
                    with tmp_path.open("rb") as f:
                        head = f.read(5)
                    if head != b"%PDF-":
                        tmp_path.unlink(missing_ok=True)
                        return PdfDownloadResult(
                            ok=False,
                            reason="not_pdf_magic",
                            final_url=final_url,
                            content_type=ctype,
                        )
                except OSError:
                    return PdfDownloadResult(
                        ok=False,
                        reason="read_error",
                        final_url=final_url,
                        content_type=ctype,
                    )

                pages = count_pages(tmp_path)
                return PdfDownloadResult(
                    ok=True,
                    final_url=final_url,
                    content_type=ctype,
                    temp_path=tmp_path,
                    page_count=pages,
                )
    except httpx.HTTPError as e:
        return PdfDownloadResult(ok=False, reason=f"http_error:{e.__class__.__name__}")
