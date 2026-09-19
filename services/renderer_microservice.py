import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

from services.latex_engine import LatexEngine
from config import get_logger

logger = get_logger("RendererMicroservice")

app = FastAPI(
    title="FindMyBoss LaTeX & PDF Renderer Microservice",
    description="High-performance dedicated microservice for XeTeX/LaTeX document compilation with Tectonic.",
    version="1.0.0",
)

CVS_DIR = Path(os.getenv("CVS_DIR", "data/cvs"))
CVS_DIR.mkdir(parents=True, exist_ok=True)
engine = LatexEngine(output_dir=str(CVS_DIR))


class RenderRequest(BaseModel):
    latex_code: str
    output_filename: str = "resume.pdf"


@app.get("/health")
async def health_check():
    """Health check verifying service readiness and tectonic binary existence."""
    tectonic_ready = Path(str(engine.tectonic_bin)).exists() or bool(os.system("which tectonic > /dev/null 2>&1") == 0)
    return {
        "status": "healthy" if tectonic_ready else "degraded",
        "service": "findmyboss-renderer",
        "engine": "tectonic-xetex",
        "tectonic_binary": str(engine.tectonic_bin),
        "output_directory": str(CVS_DIR),
    }


@app.post("/api/render")
async def render_latex_to_pdf(req: RenderRequest):
    """
    Compiles raw LaTeX source code into a pristine PDF document using the isolated Tectonic engine.
    """
    if not req.latex_code or not req.latex_code.strip():
        raise HTTPException(status_code=400, detail="LaTeX code cannot be empty.")

    filename = req.output_filename
    if not filename.endswith(".pdf"):
        filename = f"{filename}.pdf"

    try:
        logger.info(f"🔨 Compiling LaTeX document: {filename} ({len(req.latex_code)} chars)")
        pdf_path = engine.compile_pdf(req.latex_code, output_filename=filename)
        return {
            "success": True,
            "filename": filename,
            "pdf_path": str(pdf_path),
            "size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
            "message": f"Successfully compiled {filename}",
        }
    except Exception as e:
        logger.error(f"❌ LaTeX compilation failed: {e}")
        raise HTTPException(status_code=500, detail=f"LaTeX compilation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.renderer_microservice:app", host="0.0.0.0", port=8001, reload=True)
