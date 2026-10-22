"""
Cliente sencillo para la API JSON-RPC de Zabbix 7.x
Soporta autenticación por API Token (Bearer) o usuario/contraseña.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class ZabbixError(Exception):
    """Error devuelto por la API de Zabbix."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class ZabbixClient:
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        user: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ):
        self.url = (url or os.getenv("ZABBIX_URL", "")).rstrip("/")
        if not self.url.endswith("api_jsonrpc.php"):
            # Permitir tanto la URL base como la completa
            if self.url.endswith("/"):
                self.url = self.url + "api_jsonrpc.php"
            else:
                self.url = self.url + "/api_jsonrpc.php"

        self.token = token or os.getenv("ZABBIX_TOKEN")
        self.user = user or os.getenv("ZABBIX_USER")
        self.password = password or os.getenv("ZABBIX_PASSWORD")
        self.timeout = timeout
        self._auth: str | None = self.token  # Si hay token lo usamos directamente
        self._id = 0

        if not self.url:
            raise ValueError(
                "Debes configurar ZABBIX_URL (ej: https://zabbix.example.com)"
            )
        if not self.token and not (self.user and self.password):
            raise ValueError(
                "Debes configurar ZABBIX_TOKEN o (ZABBIX_USER + ZABBIX_PASSWORD)"
            )

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def _request(
        self,
        method: str,
        params: dict | list | None = None,
        auth: bool = True,
    ) -> Any:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._next_id(),
        }

        headers = {
            "Content-Type": "application/json-rpc",
            "Accept": "application/json",
        }

        # Zabbix 7.x prefiere Authorization: Bearer
        if auth and self._auth:
            headers["Authorization"] = f"Bearer {self._auth}"
            # También enviamos "auth" por compatibilidad con versiones antiguas
            payload["auth"] = self._auth

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            err = data["error"]
            raise ZabbixError(
                message=err.get("message", "Error desconocido"),
                code=err.get("code"),
                data=err.get("data"),
            )

        return data.get("result")

    async def login(self) -> str:
        """Obtiene un token de sesión con usuario/contraseña."""
        if self.token:
            self._auth = self.token
            return self.token

        result = await self._request(
            "user.login",
            {"username": self.user, "password": self.password},
            auth=False,
        )
        self._auth = result
        return result

    async def ensure_auth(self) -> None:
        if not self._auth:
            await self.login()

    # ------------------------------------------------------------------
    # Métodos de alto nivel
    # ------------------------------------------------------------------

    async def api_version(self) -> str:
        return await self._request("apiinfo.version", {}, auth=False)

    async def get_hosts(
        self,
        search: str | None = None,
        groupids: list[str] | None = None,
        hostids: list[str] | None = None,
        limit: int = 50,
        output: list[str] | str = ["hostid", "host", "name", "status"],
    ) -> list[dict]:
        await self.ensure_auth()
        params: dict[str, Any] = {
            "output": output,
            "limit": limit,
            "sortfield": "name",
            "selectGroups": ["groupid", "name"],
            "selectInterfaces": ["interfaceid", "ip", "dns", "port", "type", "main"],
        }
        if search:
            params["search"] = {"name": search}
            params["searchWildcardsEnabled"] = True
        if groupids:
            params["groupids"] = groupids
        if hostids:
            params["hostids"] = hostids
        return await self._request("host.get", params)

    async def get_problems(
        self,
        hostids: list[str] | None = None,
        recent: bool = True,
        limit: int = 50,
        severities: list[int] | None = None,
    ) -> list[dict]:
        """
        severities: 0=Not classified … 5=Disaster
        """
        await self.ensure_auth()
        params: dict[str, Any] = {
            "output": "extend",
            "selectTags": "extend",
            "selectAcknowledges": "extend",
            "recent": recent,
            "sortfield": ["eventid"],
            "sortorder": "DESC",
            "limit": limit,
        }
        if hostids:
            params["hostids"] = hostids
        if severities is not None:
            params["severities"] = severities
        return await self._request("problem.get", params)

    async def get_triggers(
        self,
        hostids: list[str] | None = None,
        only_active: bool = True,
        limit: int = 50,
    ) -> list[dict]:
        await self.ensure_auth()
        params: dict[str, Any] = {
            "output": ["triggerid", "description", "priority", "value", "lastchange", "status"],
            "selectHosts": ["hostid", "host", "name"],
            "expandDescription": True,
            "limit": limit,
            "sortfield": "priority",
            "sortorder": "DESC",
        }
        if hostids:
            params["hostids"] = hostids
        if only_active:
            params["filter"] = {"value": 1}  # 1 = PROBLEM
            params["only_true"] = True
        return await self._request("trigger.get", params)

    async def get_items(
        self,
        hostids: list[str] | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        await self.ensure_auth()
        params: dict[str, Any] = {
            "output": [
                "itemid",
                "name",
                "key_",
                "lastvalue",
                "lastclock",
                "units",
                "status",
                "value_type",
            ],
            "selectHosts": ["hostid", "host", "name"],
            "limit": limit,
            "sortfield": "name",
        }
        if hostids:
            params["hostids"] = hostids
        if search:
            params["search"] = {"name": search}
            params["searchWildcardsEnabled"] = True
        return await self._request("item.get", params)

    async def get_history(
        self,
        itemids: list[str],
        history: int = 0,
        limit: int = 100,
        time_from: int | None = None,
        time_till: int | None = None,
    ) -> list[dict]:
        """
        history: 0=float, 1=str, 2=log, 3=uint, 4=text
        """
        await self.ensure_auth()
        params: dict[str, Any] = {
            "output": "extend",
            "history": history,
            "itemids": itemids,
            "sortfield": "clock",
            "sortorder": "DESC",
            "limit": limit,
        }
        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        return await self._request("history.get", params)

    async def acknowledge(
        self,
        eventids: list[str],
        message: str = "",
        action: int = 1,  # 1 = acknowledge
    ) -> Any:
        """
        action bit mask:
          1  = close problem
          2  = acknowledge
          4  = add message
          8  = change severity
          16 = unacknowledge
          ...
        Por defecto solo acknowledge (2) + mensaje (4) = 6
        """
        await self.ensure_auth()
        # Combinamos acknowledge + mensaje si hay texto
        final_action = action
        if message:
            final_action |= 4  # add message

        params = {
            "eventids": eventids,
            "action": final_action,
            "message": message or "Acknowledged via Grok MCP connector",
        }
        return await self._request("event.acknowledge", params)

    async def get_hostgroups(self, search: str | None = None, limit: int = 50) -> list[dict]:
        await self.ensure_auth()
        params: dict[str, Any] = {
            "output": ["groupid", "name"],
            "limit": limit,
            "sortfield": "name",
        }
        if search:
            params["search"] = {"name": search}
            params["searchWildcardsEnabled"] = True
        return await self._request("hostgroup.get", params)
