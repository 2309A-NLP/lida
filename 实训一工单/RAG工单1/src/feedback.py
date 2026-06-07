"""
反馈管理模块 - 记录用户对回答的反馈
"""
import json
import time
from pathlib import Path


class FeedbackManager:
    """管理用户反馈（赞/踩/评论）"""

    def __init__(self, storage_dir: str = "outputs"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.storage_dir / "feedback_data.json"
        self._lock = None
        # 尝试导入线程锁
        try:
            import threading
            self._lock = threading.Lock()
        except Exception:
            pass

    def record(self, question: str, answer: str, rating: str, comment: str = ""):
        """记录一条反馈"""
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "question": question,
            "answer": answer[:200],
            "rating": rating,
            "comment": comment,
        }

        if self._lock:
            with self._lock:
                self._append(entry)
        else:
            self._append(entry)

    def _append(self, entry: dict):
        records = self.load_all()
        records.append(entry)
        self._file.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def load_all(self, limit: int = 100) -> list:
        if not self._file.exists():
            return []
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return data[-limit:]
        except Exception:
            return []

    def get_stats(self) -> dict:
        records = self.load_all(10000)
        total = len(records)
        positive = sum(1 for r in records if r["rating"] == "positive")
        negative = sum(1 for r in records if r["rating"] == "negative")
        return {
            "total": total,
            "positive": positive,
            "negative": negative,
            "positive_rate": f"{positive / total * 100:.1f}%" if total > 0 else "0%",
        }

    def export_csv(self) -> str:
        records = self.load_all(10000)
        lines = ["时间,问题,评价,评论"]
        for r in records:
            q = r.get("question", "").replace(",", "，").replace("\n", " ")
            c = r.get("comment", "").replace(",", "，").replace("\n", " ")
            lines.append(f"{r.get('timestamp','')},{q},{r.get('rating','')},{c}")
        return "\n".join(lines)
