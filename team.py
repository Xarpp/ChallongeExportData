class Team:
    def __init__(self, id, username, teammates=None, elo=0, r_win=0, r_lose=0, winner=False):

        if teammates is None:
            teammates = []

        self.id = id
        self.username = username
        self.teammates = teammates
        self.winner = winner
        self.elo = elo
        self.r_win = r_win
        self.r_lose = r_lose

    def set_avg_elo(self):
        sum_elo = 0
        for teammate in self.teammates:
            sum_elo += teammate.elo
        self.elo = int(sum_elo/len(self.teammates))
