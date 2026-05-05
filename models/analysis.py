"""DealAnalysis — output model for AI-powered deal evaluation."""
from dataclasses import dataclass, field


@dataclass
class DealAnalysis:
    score: float            # 1.0–10.0 composite score
    grade: str              # A / B / C / D / F
    recommendation: str     # "Pursue" / "Watch" / "Pass"
    memo: str               # 3-4 sentence investment thesis
    strengths: list[str] = field(default_factory=list)  # bullet points
    risks: list[str] = field(default_factory=list)       # bullet points
    comp_context: str = ""  # market comparison paragraph

    @property
    def badge_color(self) -> str:
        """Streamlit-friendly hex color for score badge."""
        if self.score >= 7.5:
            return "#22c55e"   # green
        if self.score >= 5.0:
            return "#f59e0b"   # amber
        return "#ef4444"       # red


def grade_from_score(score: float) -> str:
    if score >= 8.0:
        return "A"
    if score >= 6.5:
        return "B"
    if score >= 5.0:
        return "C"
    if score >= 3.0:
        return "D"
    return "F"


def recommendation_from_score(score: float) -> str:
    if score >= 7.0:
        return "Pursue"
    if score >= 5.0:
        return "Watch"
    return "Pass"
