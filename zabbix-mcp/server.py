"""
MCP Server para Zabbix 7.x
Conector personalizado para Grok (y cualquier cliente MCP).

Variables de entorno necesarias:
  ZABBIX_URL       → https://tu-zabbix.example.com  (o la URL completa a api_jsonrpc.php)
  ZABBIX_TOKEN     → API Token (recomendado)
  ─ o ─
  ZABBIX_USER      → usuario
  ZABBIX_PASSWORD  → contraseña
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from zabbix_client import ZabbixClient, ZabbixError

# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Zabbix",
    instructions=(
        "Eres un asistente conectado a un servidor Zabbix 7.x. "
        "Usa las herramientas disponibles para consultar hosts, problemas, "
        "triggers, items e historial. También puedes reconocer problemas. "
        "Siempre responde de forma clara y resume la información más relevante."
    ),
)

# Cliente global (se crea bajo demanda)
_client: ZabbixClient | None = None


def get_client() -> ZabbixClient:
    global _client
    if _client is None:
        _client = ZabbixClient()
    return _client


def _format_error(e: Exception) -> str:
    if isinstance(e, ZabbixError):
        return f"Error Zabbix ({e.code}): {e} — {e.data or ''}"
    return f"Error: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def zabbix_api_version() -> str:
    """Devuelve la versión de la API / servidor Zabbix."""
    try:
        version = await get_client().api_version()
        return f"Zabbix API version: {version}"
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_get_hosts(
    search: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]] | str:
    """
    Lista hosts de Zabbix.

    Args:
        search: Filtro por nombre (soporta comodines, ej: \"web*\" o \"db\")
        limit: Número máximo de hosts a devolver (default 30)
    """
    try:
        hosts = await get_client().get_hosts(search=search, limit=limit)
        # Simplificamos un poco la salida
        result = []
        for h in hosts:
            interfaces = h.get("interfaces") or []
            main_ip = next(
                (i.get("ip") or i.get("dns") for i in interfaces if i.get("main") == "1"),
                None,
            )
            groups = [g.get("name") for g in (h.get("groups") or [])]
            result.append(
                {
                    "hostid": h.get("hostid"),
                    "host": h.get("host"),
                    "name": h.get("name"),
                    "status": "enabled" if h.get("status") == "0" else "disabled",
                    "ip": main_ip,
                    "groups": groups,
                }
            )
        return result
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_get_problems(
    hostids: list[str] | None = None,
    limit: int = 40,
    only_recent: bool = True,
) -> list[dict[str, Any]] | str:
    """
    Obtiene problemas actuales (o recientes) de Zabbix.

    Args:
        hostids: Lista opcional de hostids para filtrar
        limit: Máximo de problemas a devolver
        only_recent: Si True solo problemas recientes / activos
    """
    try:
        problems = await get_client().get_problems(
            hostids=hostids, recent=only_recent, limit=limit
        )
        # Mapeo de severidad
        sev_map = {
            "0": "Not classified",
            "1": "Information",
            "2": "Warning",
            "3": "Average",
            "4": "High",
            "5": "Disaster",
        }
        result = []
        for p in problems:
            result.append(
                {
                    "eventid": p.get("eventid"),
                    "name": p.get("name"),
                    "severity": sev_map.get(str(p.get("severity")), p.get("severity")),
                    "clock": p.get("clock"),
                    "acknowledged": p.get("acknowledged") == "1",
                    "tags": [
                        f"{t.get('tag')}={t.get('value')}"
                        for t in (p.get("tags") or [])
                    ],
                    "opdata": p.get("opdata"),
                }
            )
        return result
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_get_host_problems(
    hostid: str,
    limit: int = 30,
) -> list[dict[str, Any]] | str:
    """
    Problemas de un host concreto.

    Args:
        hostid: ID del host (puedes obtenerlo con zabbix_get_hosts)
        limit: Máximo de problemas
    """
    return await zabbix_get_problems(hostids=[hostid], limit=limit)


@mcp.tool()
async def zabbix_get_triggers(
    hostid: str | None = None,
    only_problem: bool = True,
    limit: int = 40,
) -> list[dict[str, Any]] | str:
    """
    Lista triggers (reglas de alerta).

    Args:
        hostid: Filtrar por un host concreto (opcional)
        only_problem: Solo triggers en estado PROBLEM
        limit: Máximo de resultados
    """
    try:
        hostids = [hostid] if hostid else None
        triggers = await get_client().get_triggers(
            hostids=hostids, only_active=only_problem, limit=limit
        )
        sev_map = {
            "0": "Not classified",
            "1": "Information",
            "2": "Warning",
            "3": "Average",
            "4": "High",
            "5": "Disaster",
        }
        result = []
        for t in triggers:
            hosts = t.get("hosts") or []
            host_names = [h.get("name") or h.get("host") for h in hosts]
            result.append(
                {
                    "triggerid": t.get("triggerid"),
                    "description": t.get("description"),
                    "priority": sev_map.get(str(t.get("priority")), t.get("priority")),
                    "value": "PROBLEM" if t.get("value") == "1" else "OK",
                    "lastchange": t.get("lastchange"),
                    "hosts": host_names,
                }
            )
        return result
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_get_items(
    hostid: str,
    search: str | None = None,
    limit: int = 40,
) -> list[dict[str, Any]] | str:
    """
    Lista items (métricas) de un host.

    Args:
        hostid: ID del host
        search: Filtro por nombre del item (ej: \"CPU\", \"memory\", \"disk\")
        limit: Máximo de items
    """
    try:
        items = await get_client().get_items(
            hostids=[hostid], search=search, limit=limit
        )
        result = []
        for i in items:
            result.append(
                {
                    "itemid": i.get("itemid"),
                    "name": i.get("name"),
                    "key": i.get("key_"),
                    "lastvalue": i.get("lastvalue"),
                    "units": i.get("units"),
                    "lastclock": i.get("lastclock"),
                    "status": "enabled" if i.get("status") == "0" else "disabled",
                }
            )
        return result
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_get_history(
    itemid: str,
    limit: int = 50,
    history_type: int = 0,
) -> list[dict[str, Any]] | str:
    """
    Historial de valores de un item.

    Args:
        itemid: ID del item (obtenerlo con zabbix_get_items)
        limit: Número de puntos históricos
        history_type: 0=float, 1=string, 2=log, 3=uint, 4=text (default 0)
    """
    try:
        history = await get_client().get_history(
            itemids=[itemid], history=history_type, limit=limit
        )
        return [
            {
                "clock": h.get("clock"),
                "value": h.get("value"),
                "ns": h.get("ns"),
            }
            for h in history
        ]
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_get_hostgroups(
    search: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]] | str:
    """
    Lista grupos de hosts.

    Args:
        search: Filtro por nombre del grupo
        limit: Máximo de grupos
    """
    try:
        groups = await get_client().get_hostgroups(search=search, limit=limit)
        return [{"groupid": g["groupid"], "name": g["name"]} for g in groups]
    except Exception as e:
        return _format_error(e)


@mcp.tool()
async def zabbix_acknowledge_problem(
    eventids: list[str],
    message: str = "Acknowledged via Grok",
) -> str:
    """
    Reconoce uno o varios problemas (eventos).

    Args:
        eventids: Lista de eventids a reconocer (obtenerlos de zabbix_get_problems)
        message: Mensaje opcional que se añadirá al reconocimiento
    """
    try:
        await get_client().acknowledge(eventids=eventids, message=message, action=2)
        return f"Problemas reconocidos correctamente: {', '.join(eventids)}"
    except Exception as e:
        return _format_error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Transporte HTTP (Streamable) – necesario para Grok custom connector
    # Por defecto escucha en 0.0.0.0:8000
    port = int(os.getenv("PORT", "8000"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
