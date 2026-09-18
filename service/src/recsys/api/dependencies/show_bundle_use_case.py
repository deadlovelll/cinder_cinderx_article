from __future__ import annotations

from fastapi import Request

from recsys.application.use_cases.bundle.show_bundle import ShowBundleUseCase


def show_bundle_use_case(request: Request) -> ShowBundleUseCase:
    return request.app.state.container.show_bundle
