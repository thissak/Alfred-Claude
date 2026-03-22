"""Apple Notes 저장 헬퍼 — Markdown을 HTML로 변환 후 공유 폴더에 저장."""

import re
import subprocess


FOLDER_NAME = "Alfred"

# NOTE 블록 파싱: [NOTE:제목]...[/NOTE]
NOTE_PATTERN = re.compile(
    r"\[NOTE:(.+?)\]\s*\n(.*?)\[/NOTE\]", re.DOTALL
)


def md_to_html(md):
    """간단한 Markdown → Apple Notes HTML 변환."""
    lines = md.strip().split("\n")
    html_parts = []
    in_table = False
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()

        # 빈 줄
        if not stripped:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
                list_type = None
            if in_table:
                html_parts.append("</table>")
                in_table = False
            html_parts.append("<div><br></div>")
            continue

        # 테이블 구분선 (|---|---|) — 스킵
        if re.match(r"^\|[-\s|:]+\|$", stripped):
            continue

        # 테이블 행
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                html_parts.append("<table>")
                in_table = True
                # 첫 행은 헤더
                row = "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells) + "</tr>"
            else:
                row = "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>"
            html_parts.append(row)
            continue

        if in_table:
            html_parts.append("</table>")
            in_table = False

        # 헤딩
        if stripped.startswith("### "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h3>{_inline(stripped[4:])}</h3>")
            continue
        if stripped.startswith("## "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h2>{_inline(stripped[3:])}</h2>")
            continue
        if stripped.startswith("# "):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append(f"<h1>{_inline(stripped[2:])}</h1>")
            continue

        # 리스트
        if re.match(r"^[-*] ", stripped):
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            html_parts.append(f"<li>{_inline(stripped[2:])}</li>")
            continue

        if re.match(r"^\d+\. ", stripped):
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            text = re.sub(r"^\d+\.\s*", "", stripped)
            html_parts.append(f"<li>{_inline(text)}</li>")
            continue

        # 일반 텍스트
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
        html_parts.append(f"<div>{_inline(stripped)}</div>")

    # 닫기
    if in_list:
        html_parts.append(f"</{list_type}>")
    if in_table:
        html_parts.append("</table>")

    return "\n".join(html_parts)


def _inline(text):
    """인라인 마크다운 변환 (bold, italic, code, 색상 태그)."""
    # [중요] → 빨간색
    text = re.sub(r"\[중요\]", '<font color="#FF0000">중요</font>', text)
    # [참고] → 회색
    text = re.sub(r"\[참고\]", '<font color="#808080">참고</font>', text)
    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # *italic*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # `code`
    text = re.sub(r"`(.+?)`", r"<tt>\1</tt>", text)
    return text


def parse_and_save(response):
    """응답에서 [NOTE:제목]...[/NOTE] 파싱 → Apple Notes 저장 → 클린 응답 반환."""
    match = NOTE_PATTERN.search(response)
    if not match:
        return response, False

    title = match.group(1).strip()
    content_md = match.group(2).strip()
    html = md_to_html(content_md)

    # Apple Notes에 저장
    saved = _save_to_notes(title, html)

    # NOTE 블록 제거한 클린 응답
    clean = response[: match.start()].rstrip()
    if saved:
        print(f"[노트 저장] {title}")
    return clean, saved


def _save_to_notes(title, html, retries=2, timeout=30):
    """AppleScript로 Alfred 공유 폴더에 노트 생성. 타임아웃 + 재시도."""
    escaped_title = title.replace('"', '\\"')
    escaped_html = html.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
    tell application "Notes"
        tell account "iCloud"
            make new note at folder "Alfred" with properties {{name:"{escaped_title}", body:"{escaped_html}"}}
        end tell
    end tell'''

    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode == 0:
                return True
            print(f"[노트 저장 실패] 시도 {attempt}/{retries}: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"[노트 저장 타임아웃] 시도 {attempt}/{retries}: {timeout}초 초과")

    return False
