#!/usr/bin/env python3
"""
MarkdownDirExtractor - Production markdown directory processor.

Features:
- Recursive .md file discovery
- .cashewignore support
- Checkpointing by file path + mtime
- LLM extraction with paragraph fallback
- Domain detection from folder structure
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.extractors import BaseExtractor
from extractors.utils import (
    load_ignore_patterns, should_ignore, split_into_paragraphs, 
    detect_domain_from_path
)

logger = logging.getLogger("cashew.extractors.markdown_dir")


class MarkdownDirExtractor(BaseExtractor):
    """Extract knowledge from markdown files in a directory."""

    @property
    def name(self) -> str:
        return "markdown"

    def __init__(self):
        # Track processed files with their mtimes
        self._processed: Dict[str, float] = {}

    def extract(self, source_path: str, model_fn: Optional[Callable], 
                db_path: str) -> List[Dict[str, Any]]:
        """Extract knowledge from markdown files."""
        source_dir = Path(source_path)
        
        if not source_dir.exists():
            logger.error(f"Source path does not exist: {source_path}")
            return []

        # Handle single file vs directory
        if source_dir.is_file() and source_dir.suffix == '.md':
            md_files = [source_dir]
            base_path = source_dir.parent
        elif source_dir.is_dir():
            # Load ignore patterns
            ignore_file = source_dir / ".cashewignore"
            ignore_patterns = load_ignore_patterns(ignore_file)
            
            # Find all markdown files
            md_files = []
            for md_file in source_dir.rglob("*.md"):
                if should_ignore(md_file, source_dir, ignore_patterns):
                    continue
                md_files.append(md_file)
            
            base_path = source_dir
        else:
            logger.error(f"Invalid source path: {source_path}")
            return []

        nodes = []

        # Process each file
        for md_file in md_files:
            rel_path = str(md_file.relative_to(base_path))
            current_mtime = md_file.stat().st_mtime
            
            # Check if already processed and unchanged
            if (rel_path in self._processed and 
                self._processed[rel_path] >= current_mtime):
                continue

            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except IOError as e:
                logger.warning(f"Could not read {md_file}: {e}")
                continue

            # Skip empty files
            if not content.strip():
                continue

            # Detect domain from folder structure
            domain = detect_domain_from_path(md_file, base_path)

            # Prepare source file tag
            source_tag = f"extractor:markdown:{rel_path}"

            # Extract knowledge using model or fallback to paragraphs
            if model_fn:
                extracted_nodes = self._extract_with_llm(
                    content, model_fn, domain, source_tag)
            else:
                extracted_nodes = self._extract_paragraphs(
                    content, domain, source_tag)

            nodes.extend(extracted_nodes)
            self._processed[rel_path] = current_mtime

        return nodes

    def _extract_with_llm(self, content: str, model_fn: Callable, 
                          domain: str, source_tag: str) -> List[Dict[str, Any]]:
        """Extract knowledge using LLM."""
        prompt = f"""Extract insights, facts, decisions, commitments, important information from markdown content.

Content:
{content}

Output one statement per line. Prefix each with type tag.
Types: [fact] concrete verifiable context-independent info | [observation] something noticed in context, may be situational | [insight] non-obvious connection requiring reasoning | [decision] choice made between alternatives | [commitment] stated intention or planned action | [belief] held opinion, not objectively verifiable | When uncertain, use [observation]

Caveman style: drop articles/filler, keep technical terms exact, fragments ok if express full thought. Content fragment not ok.

Good: "[fact] Backend uses FastAPI with PostGIS on Docker Compose"
Good: "[decision] UTS tile format chosen over rasterio for 8x RAM reduction"
Bad: "[fact] ## Stack"
Bad: "[fact] - Backend"

Rules:
Begin output immediately with first statement — no title, no preamble, no intro line, no section dividers. Any line starting with # or ** is wrong. No bullet points, dashes, numbering. No raw content fragments. Skip formatting, navigation, boilerplate.

Output typed statements only, one per line."""

        try:
            response = model_fn(prompt)
            if os.environ.get("CASHEW_LOG_LLM"):
                logger.info(f"LLM raw ({source_tag}):\n{response}\n---")
            parsed_statements = []
            for s in response.split('\n'):
                s = s.strip()
                if not s:
                    continue
                if s.startswith('#'):
                    print(f"FILTERED ({source_tag}): {s}")
                    continue
                parsed_statements.append(self._parse_typed_statement(s))

            return [{
                "content": stmt_content,
                "type": node_type,
                "confidence": 0.8,
                "domain": domain,
                "source_file": source_tag
            } for node_type, stmt_content in parsed_statements if len(stmt_content) > 15]
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            # Fallback to paragraph extraction
            return self._extract_paragraphs(content, domain, source_tag)

    def _extract_paragraphs(self, content: str, domain: str, 
                            source_tag: str) -> List[Dict[str, Any]]:
        """Fallback extraction using paragraph splitting."""
        paragraphs = split_into_paragraphs(content)
        
        return [{
            "content": para,
            "type": "observation",
            "confidence": 0.6,
            "domain": domain,
            "source_file": source_tag
        } for para in paragraphs]

    _VALID_TYPES = {'fact', 'observation', 'insight', 'decision', 'commitment', 'belief'}
    _TYPE_PREFIX_RE = re.compile(r'^\[(fact|observation|insight|decision|commitment|belief)\]\s+(.+)', re.IGNORECASE)

    def _classify_content(self, content: str) -> str:
        """Classify content type. Only catches clear cases; defaults to observation."""
        s = content.lower()
        if re.search(r'\b(decided|chose|selected|agreed|going with)\b', s):
            return "decision"
        if re.search(r'\b(will|plan to|going to|need to|must)\b', s):
            return "commitment"
        if re.search(r'\b(learned|realized|discovered|found that)\b', s):
            return "insight"
        return "observation"

    def _parse_typed_statement(self, line: str) -> tuple:
        """Parse [type] statement format. Falls back to classifier if no valid tag."""
        m = self._TYPE_PREFIX_RE.match(line)
        if m:
            return m.group(1).lower(), m.group(2).strip()
        return self._classify_content(line), line

    def get_state(self) -> Dict[str, Any]:
        return {"processed": self._processed}

    def set_state(self, state: Dict[str, Any]):
        self._processed = state.get("processed", {})