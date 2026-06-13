from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Player:
    name: str
    club: str
    league: str
    position: Optional[str] = None

@dataclass
class Team:
    name: str
    players: List[Player]
