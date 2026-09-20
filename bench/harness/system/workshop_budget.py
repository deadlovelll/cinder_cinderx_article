"""Раскладка ядер для воркшопа.

Микрозамеры хотят немного зарезервированных ядер и тишину вокруг. Сервису под
нагрузкой нужно другое: воркеры gunicorn и потоки сборщика мусора работают
одновременно, и если ядер ровно столько же, сколько воркеров, параллельной
сборке просто негде развернуться - это измерено.

Поэтому здесь ядра делятся иначе: половина самых быстрых уходит сервису,
дальше генератор нагрузки и база, а самые медленные остаются операционной
системе. Число воркеров берётся вдвое меньше ядер сервиса, чтобы на время
сборки половина ядер была свободна.
"""


import os

from bench.harness.system.cpu_classes import cpu_classes


def workshop_budget() -> dict[str, list[int]]:
    count = os.cpu_count() or 1
    classes = cpu_classes()
    order = sorted(range(count), key=lambda c: (-classes.get(c, 0), c))

    if count < 8:
        return {"service": order, "load": order, "db": order, "os": order,
                "workers": [max(1, count // 2)], "gc_threads": [max(1, count // 2)]}

    n_service = count // 2
    n_load = max(2, count // 5)
    n_db = max(2, count // 5)

    service = sorted(order[:n_service])
    load = sorted(order[n_service:n_service + n_load])
    db = sorted(order[n_service + n_load:n_service + n_load + n_db])
    rest = sorted(order[n_service + n_load + n_db:]) or db

    workers = max(1, n_service // 2)
    return {"service": service, "load": load, "db": db, "os": rest,
            "workers": [workers], "gc_threads": [workers]}
