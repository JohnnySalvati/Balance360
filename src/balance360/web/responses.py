import json
from fastapi.responses import HTMLResponse

def toast_error(message: str) -> HTMLResponse:
    response = HTMLResponse("")
    response.headers["HX-Trigger"] = json.dumps({"showToast": {"message": message , "type": "error"}})
    response.headers["HX-Reswap"] = "none"
    return response