from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAIProvider(ABC):
    @abstractmethod
    def analyze_document(self, title: str, category: str, content: str) -> Dict[str, Any]:
        """
        Analyzes document content and returns structured analysis:
        {
            "priority": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
            "summary": "Concise summary...",
            "effective_date": "YYYY-MM-DD" or "Not specified",
            "key_changes": ["Change 1", "Change 2"]
        }
        """
        pass
