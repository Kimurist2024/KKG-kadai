#!/usr/bin/env python3
"""提出用 zip を作る。

git で管理しているファイルだけを入れるので、.env.local・node_modules・.venv などは入らない。
README.md は zip の中だけで完結するよう、GitHub への絶対リンクを相対パスに直して入れる。

    python3 floorplan-analyzer/scripts/make_submission_zip.py [<コミット>]   # 省略時は HEAD
"""
from __future__ import annotations

import hashlib
import io
import posixpath
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

TOP = "floorplan-submission"
OUT_NAME = "floorplan-analyzer-submission.zip"
MAIL_LIMIT_MB = 25  # Gmail の添付上限
GITHUB_BLOB = "https://github.com/Kimurist2024/KKG-kadai/blob/feature/kimura/"
MAIN_NOTE_HEAD = "> `main` ブランチには説明資料だけを置いています。"

# zip に入れないもの。理由を必ず書く。
EXCLUDE = {
    # 第三者が公開している図面の原本。再配布はせず、README 7章の URL で示す（抽出した画像とテキストは残す）
    "floorplan-analyzer/docs/validation/sources/ur_s2.pdf",
    "floorplan-analyzer/docs/validation/sources/mini_homes.pdf",
    # 課題として配布された資料。先方の手元にあり、日本語のファイル名は環境によって文字化けする
    # （同じデータは floorplan-analyzer/sample/ にあり、課題文は kadai.md にある）
    "【KKG】コーディング課題.pdf",
    "平面図解析結果.png",
    "部屋・壁・ドアマスク.json",
}

SECRET_PATTERNS = [
    ("OpenAI の API キー", re.compile(rb"sk-[A-Za-z0-9_-]{20,}")),
    ("GitHub のトークン", re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("AWS のアクセスキー", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("秘密鍵", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Slack のトークン", re.compile(rb"xox[abpr]-[A-Za-z0-9-]{10,}")),
]
SECRET_NAMES = re.compile(r"(^|/)(\.env(\.(?!example$)[^/]*)?|\.vercel/.*|[^/]*\.(pem|key|p12))$")


def git(*args: str, cwd: Path) -> bytes:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True).stdout


def fail(message: str) -> None:
    print(f"make_submission_zip: NG: {message}", file=sys.stderr)
    sys.exit(1)


def readme_for_zip(text: str) -> str:
    """GitHub 向けの注意書きを外し、絶対リンクを zip 内の相対パスに直す。"""
    lines = text.split("\n")
    idx = [i for i, line in enumerate(lines) if line.startswith(MAIN_NOTE_HEAD)]
    if len(idx) != 1:
        fail(f"README の main ブランチの注意書きが {len(idx)} 件（1 件のはず）")
    del lines[idx[0]]
    if lines[idx[0]] == "":
        del lines[idx[0]]
    text = "\n".join(lines).replace(GITHUB_BLOB, "")
    if "github.com/Kimurist2024/KKG-kadai" in text:
        fail("README に GitHub への絶対リンクが残っている")
    return text


def strip_code(text: str) -> str:
    """コードの中身を取り除く。対象は ``` と ~~~ のフェンス、空行の直後に始まる字下げブロック、`…` のコードスパン。"""
    kept: list[str] = []
    fence = ""          # 開いているフェンス（例: "```"）。空なら外側
    indented = False    # 字下げコードブロックの中か
    previous_blank = True
    for line in text.split("\n"):
        opened = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if fence:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence) \
                    and not line.strip(" `~"):
                fence = ""
            previous_blank = False
            continue
        if opened:
            fence = opened.group(1)
            previous_blank = False
            continue
        is_indented = bool(re.match(r"(?: {4}|\t)", line)) and line.strip() != ""
        if is_indented and (previous_blank or indented):
            indented = True
            continue
        if line.strip():
            indented = False
        previous_blank = line.strip() == ""
        kept.append(line)
    # コードスパンは行をまたげる（空行はまたげない）ので、ブロックを除いた後にまとめて除く
    return re.sub(r"(`+)(?:(?!\1)(?!\n[ \t]*\n).)+?\1", "", "\n".join(kept), flags=re.S)


def markdown_targets(text: str) -> list[str]:
    """リンクと画像の参照先を取り出す。タイトル付き、<> 囲み、参照形式の定義、HTML の src / href（引用符なしも）を対象にする。"""
    body = strip_code(text)
    inline = [a or b for a, b in re.findall(r"\]\(\s*(?:<([^>]+)>|([^)\s]+))(?:\s+[^)]*)?\)", body)]
    reference = [a or b for a, b in re.findall(r"^ {0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))", body, flags=re.M)]
    html = [a or b or c for a, b, c in
            re.findall(r"""(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""", body, flags=re.I)]
    return inline + reference + html


def resolve(link: str) -> str | None:
    """README（zip の最上位）から見た相対リンクを zip 内のパスに直す。外部リンクやページ内リンクは None。"""
    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:|#", link):
        return None
    path = unquote(link.split("#")[0].split("?")[0])
    return posixpath.normpath(path) if path else None


def main() -> None:
    here = Path(__file__).resolve().parent
    root = Path(git("rev-parse", "--show-toplevel", cwd=here).decode().strip())
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    commit = git("rev-parse", "--short", ref, cwd=root).decode().strip()
    mtime = int(git("log", "-1", "--format=%ct", ref, cwd=root).decode().strip())
    dirty = git("status", "--porcelain", cwd=root).decode().strip()

    files: dict[str, tuple[bytes, int]] = {}
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", ref, cwd=root))) as tar:
        for member in tar:
            if member.isdir() or member.name == "pax_global_header":
                continue
            if not member.isfile():
                fail(f"通常のファイルではない: {member.name}")
            if member.name in EXCLUDE:
                continue
            files[member.name] = (tar.extractfile(member).read(), member.mode)
    missing = EXCLUDE - set(git("ls-tree", "-r", "--name-only", "-z", ref, cwd=root).decode().split("\0"))
    if missing:
        fail(f"除外リストにあるがリポジトリに無い: {sorted(missing)}")

    readme = readme_for_zip(files["README.md"][0].decode("utf-8"))
    files["README.md"] = (readme.encode("utf-8"), files["README.md"][1])

    # README の相対リンクと画像が、zip の中ですべて開けること
    links = [(link, resolve(link)) for link in markdown_targets(readme)]
    links = [(link, path) for link, path in links if path is not None]
    broken = sorted({link for link, path in links
                     if path.startswith(("/", "..")) or (path != "." and path not in files
                                                         and not any(name.startswith(path + "/") for name in files))})
    if broken:
        fail(f"README のリンク先が zip に無い: {broken}")

    # 秘密情報が入っていないこと
    hits = [name for name in files if SECRET_NAMES.search(name)]
    for name, (data, _) in files.items():
        hits += [f"{name}（{label}）" for label, pattern in SECRET_PATTERNS if pattern.search(data)]
    if hits:
        fail(f"秘密情報の疑い: {hits}")

    out = root / OUT_NAME
    date = __import__("time").gmtime(mtime)[:6]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            data, mode = files[name]
            info = zipfile.ZipInfo(f"{TOP}/{name}", date_time=date)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o100000 | (mode & 0o777)) << 16)
            z.writestr(info, data)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (root / f"{OUT_NAME}.sha256").write_text(f"{digest}  {OUT_NAME}\n", encoding="utf-8")

    size_mb = out.stat().st_size / 1048576
    non_ascii = [name for name in files if not name.isascii()]
    print(f"作成: {out}")
    print(f"  コミット {commit} / {len(files)} ファイル / {size_mb:.1f} MB / sha256 {digest[:16]}…")
    print(f"  除外 {len(EXCLUDE)} 件 / README の相対リンク {len(links)} 件はすべて zip 内にある / 秘密情報の検出 0 件")
    print(f"  ASCII 以外のファイル名: {len(non_ascii)} 件")
    if dirty:
        print("  注意: 未コミットの変更は zip に入っていません（コミット済みの内容だけを入れます）")
    if size_mb > MAIL_LIMIT_MB:
        fail(f"{size_mb:.1f} MB はメール添付の上限 {MAIL_LIMIT_MB} MB を超えている")


if __name__ == "__main__":
    main()
