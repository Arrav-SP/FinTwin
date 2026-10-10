from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_ui(app: FastAPI, root: Path) -> None:
    """Serve the built web UI from `root` (web/dist). Call after every API route is registered.

    The UI routes in the browser, so any page address must return index.html or a reload would
    fail. Addresses under /api and addresses that name a file are never answered with the app.
    """
    app.mount("/assets", StaticFiles(directory=root / "assets", check_dir=False), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def ui(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        if "." in path.rsplit("/", 1)[-1]:
            file = (root / path).resolve()
            if root.resolve() not in file.parents or not file.is_file():
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(file)
        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=503, detail="The web UI has not been built. Run: npm --prefix web run build")
        return FileResponse(index)
