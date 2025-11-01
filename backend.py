from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import aiohttp

app = FastAPI()

@app.post("/agent/execute")
async def execute_command(payload: dict):
    texto = payload.get("command", "").lower()
    user_vars = payload.get("vars", {})

    if user_vars.get("endpoint_woo"):
        wc_url = user_vars.get("endpoint_woo")
        wc_resp = await get_external_saas(wc_url)
        return JSONResponse(content={"mensaje": f"Productos WooCommerce conectados a {wc_url}: {wc_resp}"})

    if user_vars.get("api_key_stripe"):
        stripe_key = user_vars.get("api_key_stripe")
        # Aquí podrías hacer llamada a Stripe usando stripe_key

    if user_vars.get("curso_api"):
        curso_url = user_vars.get("curso_api")
        cursos = await get_external_saas(curso_url)
        return JSONResponse(content={"mensaje": f"Cursos disponibles: {cursos}"})

    # IA fallback (debes implementarlo luego)
    ia_response = await get_perplexity_response(texto)
    return JSONResponse(content={"mensaje": ia_response})

async def get_external_saas(url, params=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params or {}, timeout=20) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.text()
                return {"error": error}

# Implementa la función get_perplexity_response según tu motor de IA real
async def get_perplexity_response(text):
    # Ejemplo básico
    return f"Respuesta IA simulada para: {text}"
