"""
Document ingestion: scan repos → read markdown → chunk → extract topics.
"""
import hashlib
from pathlib import Path
from src.config import get_settings
from src.models import DocumentChunk
import structlog

logger = structlog.get_logger()


def scan_repos() -> list[Path]:
    """Find all markdown/text files across configured repos."""
    settings = get_settings()
    base = Path(settings.source_repos_path)
    exclude = set(settings.exclude_pattern_list)
    files: list[Path] = []

    for repo in settings.source_repo_list:
        repo_path = base / repo
        if not repo_path.exists():
            logger.warning("repo_not_found", repo=repo, path=str(repo_path))
            continue
        for pattern in settings.include_pattern_list:
            for f in repo_path.glob(pattern):
                # Skip excluded paths
                if any(f.match(ex) for ex in exclude):
                    continue
                files.append(f)
        logger.info("repo_scanned", repo=repo, files=len(files))

    return files


def chunk_document(path: Path, chunk_size: int = 800, overlap: int = 100) -> list[DocumentChunk]:
    """Split a markdown file into overlapping text chunks."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    repo = path.parts[-3] if len(path.parts) >= 3 else "unknown"

    # Find the nearest heading for each chunk
    lines = text.split("\n")
    chunks: list[DocumentChunk] = []
    current_heading = ""
    words: list[str] = []
    word_positions: list[int] = []

    # Tokenize by words (simple)
    all_words = text.split()
    if not all_words:
        return []

    i = 0
    chunk_index = 0
    while i < len(all_words):
        chunk_words = all_words[i: i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunk_id = hashlib.md5(f"{path}:{chunk_index}".encode()).hexdigest()[:12]

        # Find nearest heading above this position
        char_pos = len(" ".join(all_words[:i]))
        heading = ""
        char_count = 0
        for line in lines:
            char_count += len(line) + 1
            if char_count > char_pos:
                break
            if line.startswith("#"):
                heading = line.lstrip("#").strip()

        chunks.append(DocumentChunk(
            id=chunk_id,
            text=chunk_text,
            source_file=str(path),
            source_repo=repo,
            heading=heading,
            chunk_index=chunk_index,
        ))
        i += chunk_size - overlap
        chunk_index += 1

    return chunks
