import json
import os
import subprocess
import sys


OUT = os.path.join(os.path.dirname(__file__), "fixture_shape.json")
CONTAINER = os.environ.get("RECSYS_DB_CONTAINER", "recsys-db-1")
DB = os.environ.get("RECSYS_DB_NAME", "recsys")
USER = os.environ.get("RECSYS_DB_USER", "recsys")

TABLES = ("users", "items", "covisitation", "item_embeddings",
          "user_state", "popularity", "pins", "impressions", "interactions")

QUERY = "\nunion all ".join(
    f"select '{t}' as t, count(*) as n from {t}" for t in TABLES)


def psql(sql: str) -> str:
    out = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", USER, "-d", DB,
         "-At", "-F", "|", "-c", sql],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"psql: {out.stderr.strip()}")
    return out.stdout


def main() -> None:
    counts = {}
    for line in psql(QUERY).splitlines():
        name, n = line.split("|")
        counts[name] = int(n)

    version = psql("select version()").strip().split(",")[0]

    rows = {
        "catalogue_items": counts["items"],
        "users": counts["users"],
        "graph_edges": counts["covisitation"],
        "item_embeddings": counts["item_embeddings"],
        "user_state_rows": counts["user_state"],
        "popularity_rows": counts["popularity"],
        "pins": counts["pins"],
        "impressions": counts["impressions"],
        "interactions": counts["interactions"],
    }

    for k, v in rows.items():
        print(f"  {k:<20} {v:>10,}".replace(",", " "))

    json.dump({"source": f"postgres container {CONTAINER}, database {DB}",
               "note": "снято с базы, обслуживавшей нагрузочную лестницу; "
                       "impressions/interactions обнулены сбросом фикстуры",
               "server": version,
               "counts": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
