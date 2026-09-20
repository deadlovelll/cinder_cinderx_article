from recsys.domain.values.ids import ItemId


def ids_from_csv(raw: str) -> list[ItemId]:
    if not raw:
        return []
    return [int(part) for part in raw.split(",") if part]
