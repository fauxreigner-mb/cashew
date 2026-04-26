#!/usr/bin/env python3
"""
SessionExtractor - Extract knowledge from OpenClaw session JSONL files.

Features:
- Parse JSONL session format
- Incremental processing (tracks line counts)
- Focus on assistant + user content
- Skip tool calls and system messages
- Extract knowledge using model_fn
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.extractors import BaseExtractor

logger = logging.getLogger("cashew.extractors.sessions")


class SessionExtractor(BaseExtractor):
    """Extract knowledge from OpenClaw session JSONL files."""

    @property
    def name(self) -> str:
        return "sessions"

    def __init__(self):
        # Track processed files and their line counts
        self._processed: Dict[str, int] = {}

    def extract(self, source_path: str, model_fn: Optional[Callable], 
                db_path: str) -> List[Dict[str, Any]]:
        """Extract knowledge from session directory."""
        source_dir = Path(source_path)
        
        if not source_dir.exists():
            logger.error(f"Session directory does not exist: {source_path}")
            return []

        # Find all .jsonl files
        if source_dir.is_file() and source_dir.suffix == '.jsonl':
            session_files = [source_dir]
        elif source_dir.is_dir():
            session_files = list(source_dir.glob("*.jsonl"))
        else:
            logger.error(f"Invalid source path: {source_path}")
            return []

        nodes = []

        # Process each session file
        for session_file in session_files:
            session_id = session_file.stem
            file_path = str(session_file)
            
            # Get current line count
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    current_lines = sum(1 for _ in f)
            except IOError as e:
                logger.warning(f"Could not read {session_file}: {e}")
                continue

            # Check if already processed
            processed_lines = self._processed.get(file_path, 0)
            if processed_lines >= current_lines:
                continue  # No new content

            # Read new lines only
            new_messages = self._read_new_messages(
                session_file, processed_lines, current_lines)
            
            if not new_messages:
                continue

            # Extract knowledge from conversation
            if model_fn:
                extracted_nodes = self._extract_with_llm(
                    new_messages, model_fn, session_id)
            else:
                extracted_nodes = self._extract_simple(
                    new_messages, session_id)

            nodes.extend(extracted_nodes)
            self._processed[file_path] = current_lines

        return nodes

    def _read_new_messages(self, session_file: Path, start_line: int, 
                          end_line: int) -> List[Dict[str, Any]]:
        """Read new messages from JSONL file."""
        messages = []
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i < start_line:
                        continue
                    if i >= end_line:
                        break
                    
                    try:
                        message = json.loads(line.strip())
                        # Filter relevant messages
                        if self._is_relevant_message(message):
                            messages.append(message)
                    except json.JSONDecodeError:
                        continue
                        
        except IOError as e:
            logger.warning(f"Error reading {session_file}: {e}")
        
        return messages

    def _is_relevant_message(self, message: Dict[str, Any]) -> bool:
        """Check if message is relevant for knowledge extraction."""
        role = message.get('role', '')
        content = message.get('content', '')
        
        # Skip system messages and empty content
        if role == 'system' or not content:
            return False
        
        # Skip tool calls (they usually have structured content)
        if isinstance(content, dict) or content.startswith('{'):
            return False
        
        # Skip very short messages
        if len(content) < 50:
            return False
        
        # Focus on assistant and user messages
        return role in ['assistant', 'user']

    # ~100k chars per chunk — well under 200k token context window for any model
    _CHUNK_CHARS = 100_000
    # per-message cap for LLM prompt; full content still stored in base nodes
    _PER_MSG_CHARS = 10_000

    def _truncate_at_boundary(self, text: str, max_chars: int) -> str:
        """Truncate text at a natural boundary (line, sentence, word) near max_chars."""
        if len(text) <= max_chars:
            return text
        window = text[:max_chars]
        floor = max_chars // 2
        for sep in ('\n', '. ', ' '):
            pos = window.rfind(sep)
            if pos >= floor:
                return window[:pos + len(sep)].rstrip()
        return window

    def _extract_with_llm(self, messages: List[Dict[str, Any]],
                          model_fn: Callable, session_id: str) -> List[Dict[str, Any]]:
        """Extract knowledge using LLM, chunking large sessions to fit context window."""
        if not messages:
            return []

        chunks = self._chunk_messages(messages)
        nodes = []
        for chunk in chunks:
            nodes.extend(self._extract_chunk_with_llm(chunk, model_fn, session_id))
        return nodes

    def _chunk_messages(self, messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split messages into chunks that fit within _CHUNK_CHARS."""
        chunks = []
        current_chunk: List[Dict[str, Any]] = []
        current_size = 0
        for msg in messages:
            msg_size = len(msg.get('content', ''))
            if current_chunk and current_size + msg_size > self._CHUNK_CHARS:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
            current_chunk.append(msg)
            current_size += msg_size
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def _extract_chunk_with_llm(self, messages: List[Dict[str, Any]],
                                 model_fn: Callable, session_id: str) -> List[Dict[str, Any]]:
        """Extract knowledge from one chunk of messages."""
        conversation = [
            f"{msg.get('role', '').upper()}: {self._truncate_at_boundary(msg.get('content', ''), self._PER_MSG_CHARS)}"
            for msg in messages
        ]
        conv_text = "\n\n".join(conversation)

        prompt = f"""Extract insights, decisions, commitments, facts, important information from conversation. Session: {session_id}

Conversation:
{conv_text}

Output one statement per line. Prefix each with type tag.
Types: [fact] concrete verifiable context-independent info | [observation] something noticed in context, may be situational | [insight] non-obvious connection requiring reasoning | [decision] choice made between alternatives | [commitment] stated intention or planned action | [belief] held opinion, not objectively verifiable | When uncertain, use [observation]

Caveman style: drop articles/filler, keep technical terms exact, fragments ok if express full thought. Content fragment not ok.

Good: "[fact] SNR stability used as reliability proxy for mesh links"
Good: "[decision] Rebase approach: extract final state from 99feeab instead of cherry-picking sequentially"
Good: "[commitment] Must add len(nh) validation to hop_id before merging"
Bad: "[fact] Edge recovery logic (lines 1340-1403)"

Rules:
Begin output immediately with first statement — no title, no preamble, no intro line, no section dividers. Any line starting with # or ** is wrong. No bullet points, dashes, numbering. No raw content fragments. No meta-comments. Skip pleasantries, filler, routine interactions.

Output typed statements only, one per line."""

        try:
            response = model_fn(prompt)
            if os.environ.get("CASHEW_LOG_LLM"):
                logger.info(f"LLM raw ({session_id}):\n{response}\n---")
            parsed_statements = []
            for s in response.split('\n'):
                s = s.strip()
                if not s:
                    continue
                if s.startswith('#'):
                    print(f"FILTERED ({session_id}): {s}")
                    continue
                parsed_statements.append(self._parse_typed_statement(s))

            batch_referent_time = None
            for msg in messages:
                ts = (msg.get('timestamp') or '').strip()
                if ts:
                    batch_referent_time = ts

            return [{
                "content": content,
                "type": node_type,
                "confidence": 0.75,
                "domain": "conversations",
                "source_file": f"extractor:session:{session_id}",
                "referent_time": batch_referent_time,
            } for node_type, content in parsed_statements if len(content) > 20]

        except Exception as e:
            logger.warning(f"LLM extraction failed for {session_id}: {e}")
            return self._extract_simple(messages, session_id)

    def _extract_simple(self, messages: List[Dict[str, Any]], 
                        session_id: str) -> List[Dict[str, Any]]:
        """Simple extraction without LLM."""
        nodes = []
        
        for msg in messages:
            content = msg.get('content', '').strip()
            role = msg.get('role', '')
            ts = (msg.get('timestamp') or '').strip() or None

            if len(content) < 100:  # Skip short messages
                continue

            # Extract longer, substantial messages. Per-message timestamp
            # becomes the node's event clock (referent_time).
            nodes.append({
                "content": f"{role}: {content}",
                "type": "observation",
                "confidence": 0.5,
                "domain": "conversations",
                "source_file": f"extractor:session:{session_id}",
                "referent_time": ts,
            })
        
        return nodes

    _VALID_TYPES = {'fact', 'observation', 'insight', 'decision', 'commitment', 'belief'}
    _TYPE_PREFIX_RE = re.compile(r'^\[(fact|observation|insight|decision|commitment|belief)\]\s+(.+)', re.IGNORECASE)

    def _classify_statement(self, statement: str) -> str:
        """Classify statement type. Only catches clear cases; defaults to observation."""
        s = statement.lower()
        if re.search(r'\b(decided|chose|selected|agreed|going with)\b', s):
            return "decision"
        if re.search(r'\b(will|plan to|going to|need to|must|should)\b', s):
            return "commitment"
        if re.search(r'\b(learned|realized|discovered|found that)\b', s):
            return "insight"
        return "observation"

    def _parse_typed_statement(self, line: str) -> tuple[str, str]:
        """Parse [type] statement format. Falls back to classifier if no valid tag."""
        m = self._TYPE_PREFIX_RE.match(line)
        if m:
            return m.group(1).lower(), m.group(2).strip()
        return self._classify_statement(line), line

    def get_state(self) -> Dict[str, Any]:
        return {"processed": self._processed}

    def set_state(self, state: Dict[str, Any]):
        self._processed = state.get("processed", {})