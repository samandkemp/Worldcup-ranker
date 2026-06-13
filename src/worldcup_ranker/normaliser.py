from functools import lru_cache

LEAGUE_ALIASES = {
    # English
    'premier league': 'premier league',
    'premier': 'premier league',
    'epl': 'premier league',
    'english premier league': 'premier league',
    'eng-premier league': 'premier league',
    # Spanish
    'la liga': 'la liga',
    'liga': 'la liga',
    'laliga': 'la liga',
    'primera division': 'la liga',
    'esp-la liga': 'la liga',
    # German
    'bundesliga': 'bundesliga',
    '1. bundesliga': 'bundesliga',
    'ger-bundesliga': 'bundesliga',
    # Italian
    'serie a': 'serie a',
    'ita-serie a': 'serie a',
    # French
    'ligue 1': 'ligue 1',
    'ligue1': 'ligue 1',
    'fra-ligue 1': 'ligue 1',
    # Portuguese
    'primeira liga': 'primeira liga',
    'liga nos': 'primeira liga',
    'liga portugal': 'primeira liga',
    'por-liga nos': 'primeira liga',
    # Dutch
    'eredivisie': 'eredivisie',
    'ned-eredivisie': 'eredivisie',
    # Belgian
    'jupiler pro league': 'jupiler pro league',
    'first division a': 'jupiler pro league',
    'bel-first division a': 'jupiler pro league',
    # Scottish
    'scottish premiership': 'scottish premiership',
    'sco-premiership': 'scottish premiership',
    # Turkish
    'super lig': 'super lig',
    'süper lig': 'super lig',
    'tur-super lig': 'super lig',
    # Brazilian
    'brasileirao': 'brasileirao',
    'serie a brasileirao': 'brasileirao',
    'campeonato brasileiro serie a': 'brasileirao',
    'bra-serie a': 'brasileirao',
    # Argentine
    'liga profesional': 'liga profesional argentina',
    'superliga argentina': 'liga profesional argentina',
    'arg-liga profesional': 'liga profesional argentina',
    # Mexican
    'liga mx': 'liga mx',
    'mex-liga mx': 'liga mx',
    # MLS
    'mls': 'mls',
    'major league soccer': 'mls',
    'usa-mls': 'mls',
    # Saudi
    'saudi pro league': 'saudi pro league',
    'saudi professional league': 'saudi pro league',
    # Champions League / international
    'uefa champions league': 'uefa champions league',
    'champions league': 'uefa champions league',
    'ucl': 'uefa champions league',
}


@lru_cache(maxsize=2048)
def normalise_league(league: str) -> str:
    if not league:
        return ''
    key = league.strip().lower()
    return LEAGUE_ALIASES.get(key, key)
