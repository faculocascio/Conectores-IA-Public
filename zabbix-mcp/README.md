# Zabbix MCP Connector for Grok

Conector personalizado (MCP Server) que permite a **Grok** consultar y gestionar un servidor **Zabbix 7.x**.

## Características

- Autenticación por **API Token** o **usuario/contraseña**
- Consulta de hosts, grupos, problemas, triggers e items
- Historial de métricas
- Reconocimiento de problemas (escritura)
- Compatible con Grok custom connectors, Claude, Cursor, etc.

## Herramientas disponibles

| Tool | Descripción |
|------|-------------|
| `zabbix_api_version` | Versión del servidor Zabbix |
| `zabbix_get_hosts` | Lista hosts (con búsqueda) |
| `zabbix_get_hostgroups` | Lista grupos de hosts |
| `zabbix_get_problems` | Problemas actuales / recientes |
| `zabbix_get_host_problems` | Problemas de un host concreto |
| `zabbix_get_triggers` | Triggers (solo PROBLEM o todos) |
| `zabbix_get_items` | Items / métricas de un host |
| `zabbix_get_history` | Historial de un item |
| `zabbix_acknowledge_problem` | Reconocer problemas |

## Requisitos

- Python 3.11+
- Servidor Zabbix 7.x con API habilitada
- API Token **o** usuario con permisos de API

## Instalación rápida

```bash
git clone https://github.com/faculocascio/Conectores-IA-Public.git
cd Conectores-IA-Public/zabbix-mcp
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copia el archivo de ejemplo y rellénalo:

```bash
cp .env.example .env
```

Edita `.env`:

```env
ZABBIX_URL=https://tu-zabbix.example.com
ZABBIX_TOKEN=tu_token_aqui
# o alternativamente:
# ZABBIX_USER=Admin
# ZABBIX_PASSWORD=tu_password
PORT=8000
```

## Ejecutar localmente

```bash
# Carga las variables de entorno
export $(grep -v '^#' .env | xargs)

python server.py
```

El servidor queda escuchando en `http://0.0.0.0:8000/mcp` (o el puerto que indiques).

### Probar con MCP Inspector

```bash
npx @modelcontextprotocol/inspector
# o
mcp dev server.py
```

## Desplegar (recomendado para Grok)

Grok necesita una **URL pública HTTPS**. Opciones fáciles:

### 1. Railway / Render / Fly.io

Con el `Dockerfile` incluido es trivial:

```bash
# Ejemplo con Railway
railway up
```

### 2. Túnel temporal (desarrollo)

```bash
# Terminal 1
python server.py

# Terminal 2
ngrok http 8000
# Copia la URL https://xxxx.ngrok-free.app
```

Luego en Grok usa: `https://xxxx.ngrok-free.app/mcp`

> **Nota**: Cloudflare quick tunnels no soportan SSE. Usa ngrok si tu transporte lo necesita. Streamable HTTP funciona con ambos.

## Conectar en Grok

1. Ve a [grok.com/connectors](https://grok.com/connectors)
2. **New Connector** → **Custom**
3. Name: `Zabbix`
4. Server URL: `https://tu-servidor/mcp`  
   (la ruta exacta depende del despliegue; normalmente termina en `/mcp`)
5. Completa autenticación si se solicita (en este conector no hace falta OAuth extra)
6. ¡Listo! Grok descubrirá las herramientas automáticamente.

### Ejemplo de uso en Grok

> "¿Qué problemas hay ahora mismo en Zabbix?"
>
> "Muéstrame los hosts del grupo Linux"
>
> "Reconoce el problema eventid 123456 con el mensaje 'Revisado por el equipo'"

## Variables de entorno

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `ZABBIX_URL` | Sí | URL del frontend Zabbix |
| `ZABBIX_TOKEN` | * | API Token (recomendado) |
| `ZABBIX_USER` | * | Usuario (si no usas token) |
| `ZABBIX_PASSWORD` | * | Contraseña (si no usas token) |
| `PORT` | No | Puerto del servidor MCP (default 8000) |

\* Necesitas **token** **o** usuario+contraseña.

## Seguridad

- Nunca subas el archivo `.env` a GitHub.
- Usa un API Token con los permisos mínimos necesarios.
- Si despliegas públicamente, protege el endpoint (API Gateway, IP allowlist, o autentica el propio MCP).

## Licencia

MIT – úsalo libremente.
