def build(n: int) -> list:
    return [{"id": i, "name": f"item-{i}", "tags": (i % 7, i % 11)} for i in range(n)]
