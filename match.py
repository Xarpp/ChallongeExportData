class Match:
    def __init__(self, id, player1, player2, winner_id, updated=None, sent=False, state=None, player1_r_change=None,
                 player2_r_change=None):
        self.id = id
        self.state = state
        self.player1 = player1
        self.player2 = player2
        self.player1_r_change = player1_r_change
        self.player2_r_change = player2_r_change
        self.winner_id = winner_id
        self.sent = sent
        self.updated = updated
