
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        if first.get("type") == "json_invalid":
            return JSONResponse(
                {"title": "malformed_json", "detail": first.get("msg", ""),
                 "status": 400},
                status_code=400)
        field = ".".join(str(p) for p in first.get("loc", ())[1:]) or "body"
        return JSONResponse(
            {"title": "validation_error",
             "detail": f"{field}: {first.get('msg', 'invalid')}",
             "status": 422},
            status_code=422)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else ""
        title = {400: "malformed_json", 404: "not_found", 405: "method_not_allowed",
                 422: "validation_error"}.get(exc.status_code, "error")
        return JSONResponse({"title": title, "detail": detail,
                             "status": exc.status_code},
                            status_code=exc.status_code)
