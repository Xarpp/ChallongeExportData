class User:
    def __init__(self, username, elo, calibration, id=-1, matches_played=0, matches_won=0, tournaments_played=1,
                 r_change=0, r_win=0, r_lose=0, winner=False):
        self.id = id
        self.username = username
        self.elo = elo
        self.calibration = calibration
        self.r_win = r_win
        self.r_lose = r_lose
        self.r_change = r_change
        self.winner = winner
        self.matches_played = matches_played
        self.matches_won = matches_won
        self.tournaments_played = tournaments_played
