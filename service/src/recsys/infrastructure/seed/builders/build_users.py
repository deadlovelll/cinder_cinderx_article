from datetime import timedelta

from recsys.infrastructure.seed.config import BASE_DATE, SEGMENTS


def build_users(n_users: int, n_items: int, rnd) -> tuple[list[dict], list[dict]]:
    user_rows, state_rows = [], []
    for uid in range(1, n_users + 1):
        user_rows.append({
            "id": uid,
            "segment": SEGMENTS[next(rnd) % len(SEGMENTS)],
            "region": ("eu", "us", "apac")[next(rnd) % 3],
            "age": 16 + next(rnd) % 60,
            "median_basket_cents": 1_000 + next(rnd) % 50_000,
        })
        recent = [next(rnd) % n_items for _ in range(5 + next(rnd) % 25)]
        purchased = [next(rnd) % n_items for _ in range(20 + next(rnd) % 120)]
        disliked = [next(rnd) % n_items for _ in range(next(rnd) % 15)]
        state_rows.append({
            "user_id": uid,
            "recent_items": ",".join(str(x) for x in recent),
            "purchased_items": ",".join(str(x) for x in purchased),
            "disliked_items": ",".join(str(x) for x in disliked),
        })
    return user_rows, state_rows
