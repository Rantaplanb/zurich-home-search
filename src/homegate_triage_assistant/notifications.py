from __future__ import annotations

import shutil
import subprocess
import sys

from .schemas import EvaluationResult, ListingRecord


class NotificationService:
    def notify_listing(self, listing: ListingRecord, evaluation: EvaluationResult) -> None:
        title = "Homegate contact candidate"
        subtitle = f"{listing.title or listing.url} ({evaluation.total_score}/10)"
        message = evaluation.summary_lines[0]
        self._notify(title=title, subtitle=subtitle, message=message)

    def _notify(self, *, title: str, subtitle: str, message: str) -> None:
        if sys.platform == "darwin":
            script = (
                'display notification "{message}" with title "{title}" subtitle "{subtitle}"'
                .format(
                    message=message.replace('"', "'"),
                    title=title.replace('"', "'"),
                    subtitle=subtitle.replace('"', "'"),
                )
            )
            subprocess.run(["osascript", "-e", script], check=False)
            return

        if shutil.which("notify-send"):
            subprocess.run(["notify-send", title, f"{subtitle}\n{message}"], check=False)
