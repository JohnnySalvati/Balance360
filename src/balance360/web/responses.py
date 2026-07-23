import json

from fastapi.responses import HTMLResponse
from pydantic import ValidationError


def toast_error(message: str) -> HTMLResponse:
    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": {"message": message, "type": "error"}}
    )
    response.headers["HX-Reswap"] = "none"
    return response


def format_validation_error(e: ValidationError) -> str:
    result = []
    for error in e.errors():
        context = error.get("ctx")
        if context:
            result.append(str(context.get("error")))
        else:
            msg = error.get("msg")
            loc = error.get("loc")
            result.append(f"{loc[0] if loc else ''} {str(msg)}")
    return " | ".join(result)
