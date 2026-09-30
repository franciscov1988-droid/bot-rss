#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Telegram: reenvía las publicaciones nuevas de uno o varios feeds RSS
a tu canal de Telegram.

Uso:
    python bot_rss_telegram.py            -> corre en bucle (revisa cada X minutos)
    python bot_rss_telegram.py --una-vez  -> revisa una sola vez y termina
"""

import html
import json
import os
import re
import sys
import time
from pathlib import Path

import feedparser
import requests

# ============================================================
#  1) CONFIGURACIÓN  — edita SOLO esta sección
# ============================================================

# Token que te da @BotFather (algo como  123456789:AAE-xxxxxxxxxxxxxxxx)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "PEGA_AQUI_TU_TOKEN")

# Canal de destino:
#   - Canal PÚBLICO:  "@nombre_de_tu_canal"
#   - Canal PRIVADO:  el número, por ejemplo  -1001234567890
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@tu_canal")

# Feeds que quieres reenviar. Puedes poner uno o varios.
FEEDS = [
    "https://volvamosalevangelio.org/feed/",
    "https://rinconreformado.com/feed/",
    "https://biteproject.com/feed/",
    "https://9marcas.org/feed/",
    "https://semperreformandaperu.org/feed/",
    "https://evangelio.blog/feed/",
    "https://www.evangelioverdadero.com/feed/"
    "https://josuebarrios.com/feed/"
]

# Cada cuántos minutos revisar (solo aplica en modo bucle)
INTERVALO_MINUTOS = 15

# Máximo de publicaciones a enviar en cada revisión (evita inundar el canal)
MAX_POR_CICLO = 5

# Archivo donde se guarda lo que ya se envió (para no repetir nunca).
# Por defecto se guarda en tu carpeta personal, que siempre tiene permiso
# de escritura. En GitHub Actions se define por variable de entorno para
# guardarlo dentro del repositorio. Si prefieres otra ruta, cámbiala aquí.
ARCHIVO_ESTADO = os.environ.get(
    "ARCHIVO_ESTADO",
    str(Path.home() / "bot_rss_enviados.json"),
)

# En la PRIMERA ejecución, ¿marcar lo que ya existe como "ya visto"
# sin enviarlo? (True = NO manda de golpe las publicaciones viejas)
PRIMERA_VEZ_SILENCIOSO = True

# ============================================================
#  De aquí para abajo normalmente NO necesitas tocar nada
# ============================================================

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def cargar_enviados():
    ruta = Path(ARCHIVO_ESTADO)
    if ruta.exists():
        try:
            return set(json.loads(ruta.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def guardar_enviados(enviados):
    Path(ARCHIVO_ESTADO).write_text(
        json.dumps(sorted(enviados), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def limpiar_html(texto):
    """Quita etiquetas HTML y espacios de más de un resumen."""
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", "", texto)        # borra <p>, <a>, etc.
    texto = html.unescape(texto)                 # &amp; -> &
    texto = re.sub(r"\s+", " ", texto).strip()   # colapsa espacios
    return texto


def id_de_entrada(entrada):
    """Identificador único y estable de cada publicación."""
    return entrada.get("id") or entrada.get("link") or entrada.get("title", "")


def construir_mensaje(entrada):
    titulo = entrada.get("title", "(sin título)").strip()
    enlace = entrada.get("link", "").strip()

    resumen = limpiar_html(entrada.get("summary", ""))
    if len(resumen) > 300:
        resumen = resumen[:300].rstrip() + "…"

    partes = [f"<b>{html.escape(titulo)}</b>"]
    if resumen:
        partes.append(html.escape(resumen))
    if enlace:
        partes.append(enlace)
    return "\n\n".join(partes)


def enviar_mensaje(texto):
    resp = requests.post(
        f"{API}/sendMessage",
        data={
            "chat_id": CHANNEL_ID,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,  # False = muestra la vista previa
        },
        timeout=30,
    )
    datos = resp.json()
    if not datos.get("ok"):
        print(f"  ⚠️  Telegram respondió error: {datos}")
    return datos.get("ok", False)


def revisar_una_vez():
    enviados = cargar_enviados()
    primera_vez = len(enviados) == 0 and PRIMERA_VEZ_SILENCIOSO
    nuevos_enviados = 0

    for url in FEEDS:
        print(f"Leyendo feed: {url}")
        feed = feedparser.parse(url)

        if feed.bozo:
            print(f"  ⚠️  El feed dio un aviso al leerse: {feed.bozo_exception}")

        # feedparser trae lo más reciente primero; lo invertimos para
        # enviar del más viejo al más nuevo y respetar el orden real.
        for entrada in reversed(feed.entries):
            uid = id_de_entrada(entrada)
            if not uid or uid in enviados:
                continue

            if primera_vez:
                enviados.add(uid)   # solo marcar, no enviar
                continue

            if nuevos_enviados >= MAX_POR_CICLO:
                break

            texto = construir_mensaje(entrada)
            print(f"  → Enviando: {entrada.get('title', '')[:60]}")
            if enviar_mensaje(texto):
                enviados.add(uid)
                nuevos_enviados += 1
                time.sleep(3)  # pausa breve para no saturar a Telegram

    guardar_enviados(enviados)

    if primera_vez:
        print("Primera ejecución: se marcaron las publicaciones actuales como "
              "vistas (no se enviaron). A partir de ahora solo llegarán las nuevas.")
    else:
        print(f"Listo. Publicaciones nuevas enviadas: {nuevos_enviados}")


def main():
    if BOT_TOKEN.startswith("PEGA_AQUI") or CHANNEL_ID == "@tu_canal":
        print("❌ Falta configurar BOT_TOKEN y CHANNEL_ID dentro del archivo.")
        sys.exit(1)

    if "--una-vez" in sys.argv:
        revisar_una_vez()
        return

    print(f"Bot iniciado. Revisando cada {INTERVALO_MINUTOS} minutos. "
          "(Presiona Ctrl+C para detener)")
    while True:
        try:
            revisar_una_vez()
        except Exception as e:
            print(f"⚠️  Error en la revisión: {e}")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()
