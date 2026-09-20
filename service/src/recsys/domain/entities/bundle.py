class Bundle:
    __slots__ = ("neighbours", "weights", "ranks", "shares", "labels")

    def __init__(self, neighbours: list, weights: list, ranks: list,
                 shares: list, labels: list) -> None:
        self.neighbours = neighbours
        self.weights = weights
        self.ranks = ranks
        self.shares = shares
        self.labels = labels
