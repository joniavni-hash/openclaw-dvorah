#!/usr/bin/env python3
"""
Context Guard - Prevents context overflow globally.

Monitors context usage and automatically:
1. Truncates when approaching limits
2. Prioritizes essential content
3. Provides fallback strategies
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Context limits (conservative)
MAX_CONTEXT_CHARS = 160000  # 80% of 200k tokens (assuming ~1.25 chars/token)
CRITICAL_THRESHOLD = 0.9    # When to force truncate
WARNING_THRESHOLD = 0.7     # When to start compacting

# Essential files (never truncate these)
ESSENTIAL_FILES = {
    "IDENTITY.md",
    "SOUL.md", 
    "USER.md",
    "CAPABILITY_INDEX.md",
    "MEMORY_INDEX.md",
}

class ContextGuard:
    def __init__(self, workspace_path: str = None):
        self.workspace = Path(workspace_path or os.environ.get("DVORAH_WORKSPACE", 
                                                             Path.home() / ".openclaw" / "workspace"))
        self.current_usage = 0
        self.loaded_files = {}
        
    def estimate_tokens(self, text: str) -> int:
        """Conservative token estimation (1.25 chars per token)"""
        return len(text) // 1.25
    
    def check_usage(self) -> Dict:
        """Check current context usage status"""
        usage_ratio = self.current_usage / MAX_CONTEXT_CHARS
        return {
            "chars": self.current_usage,
            "max_chars": MAX_CONTEXT_CHARS,
            "usage_ratio": usage_ratio,
            "status": (
                "critical" if usage_ratio >= CRITICAL_THRESHOLD else
                "warning" if usage_ratio >= WARNING_THRESHOLD else
                "ok"
            ),
            "tokens_estimate": int(self.estimate_tokens(str(self.current_usage))),
            "files_loaded": len(self.loaded_files)
        }
    
    def can_load(self, file_size: int) -> bool:
        """Check if we can safely load a file"""
        projected_usage = self.current_usage + file_size
        return projected_usage / MAX_CONTEXT_CHARS < CRITICAL_THRESHOLD
    
    def safe_load(self, file_path: str, max_lines: Optional[int] = None) -> str:
        """Load file with overflow protection"""
        try:
            path = self.workspace / file_path
            if not path.exists():
                return ""
                
            content = path.read_text(encoding='utf-8')
            
            # Essential files always load fully
            if path.name in ESSENTIAL_FILES:
                self.loaded_files[file_path] = len(content)
                self.current_usage += len(content)
                return content
            
            # Check if we can load safely
            if not self.can_load(len(content)):
                # Truncate if needed
                if max_lines:
                    lines = content.split('\n')
                    content = '\n'.join(lines[:max_lines])
                else:
                    # Take first 75% of file
                    truncate_at = int(len(content) * 0.75)
                    content = content[:truncate_at] + "\n\n[TRUNCATED - CONTEXT LIMIT]"
            
            self.loaded_files[file_path] = len(content)
            self.current_usage += len(content)
            return content
            
        except Exception as e:
            return f"[ERROR LOADING {file_path}: {e}]"
    
    def compact_context(self) -> str:
        """Emergency context compaction"""
        status = self.check_usage()
        if status["status"] != "critical":
            return "Context OK - no compaction needed"
        
        # Remove largest non-essential files first
        removed = []
        for file_path, size in sorted(self.loaded_files.items(), 
                                    key=lambda x: x[1], reverse=True):
            if Path(file_path).name not in ESSENTIAL_FILES:
                self.current_usage -= size
                del self.loaded_files[file_path]
                removed.append(file_path)
                
                # Check if we're back to safe levels
                if self.current_usage / MAX_CONTEXT_CHARS < WARNING_THRESHOLD:
                    break
        
        return f"Context compacted. Removed {len(removed)} files: {removed[:5]}..."
    
    def reset(self):
        """Reset context tracking"""
        self.current_usage = 0
        self.loaded_files.clear()

    def build_ordered_prompt(self, static_files: list, dynamic_content: str,
                              max_dynamic_chars: int = 40000) -> dict:
        """
        Arrange prompt for cache efficiency:
          1. Static prefix (IDENTITY, SOUL, USER, agent system prompt) → cached
          2. Dynamic suffix (state files, assembled context, message) → unique

        Returns dict with static_prefix, dynamic_suffix, total_chars, cache_boundary.
        The cache_boundary value tells the session spawner where to place the
        cache_control breakpoint in the API call.
        """
        static_parts = []
        for f in static_files:
            content = self.safe_load(f)
            if content and not content.startswith("[ERROR"):
                static_parts.append(content)

        static_prefix = "\n\n---\n\n".join(static_parts)

        # Truncate dynamic content if too large
        if len(dynamic_content) > max_dynamic_chars:
            dynamic_content = dynamic_content[:max_dynamic_chars] + "\n[TRUNCATED]"

        return {
            "static_prefix": static_prefix,
            "dynamic_suffix": dynamic_content,
            "total_chars": len(static_prefix) + len(dynamic_content),
            "cache_boundary": len(static_prefix),
            "static_files": static_files,
        }


# Global instance
guard = ContextGuard()

def safe_read_file(file_path: str, max_lines: Optional[int] = None) -> str:
    """Global function for safe file reading with context protection"""
    return guard.safe_load(file_path, max_lines)

def context_status() -> Dict:
    """Global function to check context status"""
    return guard.check_usage()

def emergency_compact() -> str:
    """Global function for emergency compaction"""
    return guard.compact_context()

def build_ordered_prompt(static_files: list, dynamic_content: str,
                         max_dynamic_chars: int = 40000) -> dict:
    """Global function for cache-boundary-aware prompt construction"""
    return guard.build_ordered_prompt(static_files, dynamic_content, max_dynamic_chars)