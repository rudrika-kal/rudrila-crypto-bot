from __future__ import annotations
from .volatility_execution import VolatilityExecutionFamily
from .news_macro import NewsMacroEngine
from .breaking_news import BreakingNewsGuard
from .consensus import consensus
from .entry_rules import EntryRules
from .regime import RegimeDetector
from .risk import RiskEngine
from .exits import ExitPlanner
from .position_manager import PositionManager

class DecisionStack1120:
    def __init__(self):
        self.volatility=VolatilityExecutionFamily()
        self.news=NewsMacroEngine()
        self.breaking=BreakingNewsGuard()
        self.entry=EntryRules()
        self.regime=RegimeDetector()
        self.risk=RiskEngine()
        self.exits=ExitPlanner()
        self.position_manager=PositionManager()
