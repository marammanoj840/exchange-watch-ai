import time
from typing import Dict

class LatencyTracker:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.timestamps: Dict[str, float] = {}
        self.record("detected_at")

    def record(self, stage: str) -> None:
        self.timestamps[stage] = time.time()

    def get_latency_ms(self, start_stage: str, end_stage: str) -> float:
        if start_stage in self.timestamps and end_stage in self.timestamps:
            return (self.timestamps[end_stage] - self.timestamps[start_stage]) * 1000.0
        return 0.0

    def get_summary(self) -> Dict[str, float]:
        summary = {}
        if "detected_at" in self.timestamps and "finished_at" in self.timestamps:
            summary["total_latency_ms"] = round(self.get_latency_ms("detected_at", "finished_at"), 2)
        elif "detected_at" in self.timestamps and "alert_sent_at" in self.timestamps:
            summary["total_latency_ms"] = round(self.get_latency_ms("detected_at", "alert_sent_at"), 2)

        if "extraction_started_at" in self.timestamps and "extraction_completed_at" in self.timestamps:
            summary["extraction_ms"] = round(self.get_latency_ms("extraction_started_at", "extraction_completed_at"), 2)

        if "classification_started_at" in self.timestamps and "classification_completed_at" in self.timestamps:
            summary["classification_ms"] = round(self.get_latency_ms("classification_started_at", "classification_completed_at"), 2)

        if "ai_started_at" in self.timestamps and "ai_completed_at" in self.timestamps:
            summary["inference_ms"] = round(self.get_latency_ms("ai_started_at", "ai_completed_at"), 2)
            summary["ai_ms"] = summary["inference_ms"]

        if "notification_started_at" in self.timestamps and "notification_sent_at" in self.timestamps:
            summary["telegram_delivery_ms"] = round(self.get_latency_ms("notification_started_at", "notification_sent_at"), 2)

        if "storage_started_at" in self.timestamps and "storage_completed_at" in self.timestamps:
            summary["storage_ms"] = round(self.get_latency_ms("storage_started_at", "storage_completed_at"), 2)

        return summary
