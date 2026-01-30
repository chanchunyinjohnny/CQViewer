"""Queue information model."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class QueueInfo:
    """Information about a Chronicle Queue file."""

    filepath: Path
    file_size: int
    message_count: int
    version: int = 0
    roll_cycle: str = ""
    index_count: int = 0
    index_spacing: int = 0

    @property
    def filename(self) -> str:
        """Get just the filename."""
        return self.filepath.name

    @property
    def file_size_str(self) -> str:
        """Human-readable file size."""
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def __str__(self) -> str:
        """String representation."""
        return f"{self.filename} ({self.file_size_str}, {self.message_count} messages)"
