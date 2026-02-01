"""Cliente MCP para integrar servidores MCP externos en el pipeline."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


class MCPClientService:
    """Servicio para conectar con MCPs externos (Pinterest, filesystem, etc.)."""

    def __init__(self):
        self.servers: dict[str, StdioServerParameters] = {
            "pinterest": StdioServerParameters(
                command="npx",
                args=["pinterest-mcp-server"],
                env={"MCP_PINTEREST_DOWNLOAD_DIR": str(Path("references").absolute())},
            ),
            "filesystem": StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", str(Path(".").absolute())],
            ),
        }

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Llama a un tool de un servidor MCP.

        Args:
            server_name: Nombre del servidor (pinterest, filesystem)
            tool_name: Nombre del tool a ejecutar
            arguments: Argumentos para el tool

        Returns:
            Resultado del tool
        """
        if server_name not in self.servers:
            raise ValueError(f"Servidor MCP '{server_name}' no configurado")

        server_params = self.servers[server_name]

        console.print(f"[blue][MCP][/blue] Conectando a {server_name}...")

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                console.print(f"[blue][MCP][/blue] Ejecutando {tool_name}...")
                result = await session.call_tool(tool_name, arguments)

                console.print(f"[green][OK][/green] Tool {tool_name} ejecutado")
                return result

    async def list_tools(self, server_name: str) -> list[dict]:
        """Lista los tools disponibles en un servidor MCP."""
        if server_name not in self.servers:
            raise ValueError(f"Servidor MCP '{server_name}' no configurado")

        server_params = self.servers[server_name]

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [{"name": t.name, "description": t.description} for t in tools.tools]

    async def search_pinterest(
        self,
        query: str,
        limit: int = 10,
        download: bool = True,
    ) -> list[dict]:
        """
        Busca imágenes en Pinterest y opcionalmente las descarga.

        Args:
            query: Término de búsqueda
            limit: Cantidad máxima de resultados
            download: Si descargar las imágenes a references/

        Returns:
            Lista de resultados con URLs e información + local_path si download=True
        """
        console.print(f"[blue][Pinterest][/blue] Buscando: {query}")

        # Try different tool names depending on Pinterest MCP implementation
        tool_name = "search_and_download" if download else "search_images"
        try:
            result = await self.call_tool(
                "pinterest",
                tool_name,
                {"keyword": query, "limit": limit},
            )
            # Handle different response formats
            if isinstance(result, dict) and "content" in result:
                # MCP tool result format
                import json

                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    # Extract text from content blocks
                    text_content = content[0].get("text", "[]")
                    try:
                        result = json.loads(text_content)
                    except json.JSONDecodeError:
                        result = []
                else:
                    result = []
            elif not isinstance(result, list):
                result = []

            # Enrich results with local_path (downloaded images are in references/)
            if download and result:
                from pathlib import Path

                refs_dir = Path("references")
                if refs_dir.exists():
                    # Get most recent downloaded images
                    downloaded_files = sorted(
                        list(refs_dir.glob("*.jpg"))
                        + list(refs_dir.glob("*.png"))
                        + list(refs_dir.glob("*.webp")),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                    # Match downloaded files to results (by count - assumes MCP downloads in order)
                    for i, item in enumerate(result[: len(downloaded_files)]):
                        if isinstance(item, dict):
                            item["local_path"] = str(downloaded_files[i])

            return result if result else []
        except Exception as e:
            # Try alternative tool name
            try:
                tool_name = "search" if download else "search"
                result = await self.call_tool(
                    "pinterest",
                    tool_name,
                    {"query": query, "limit": limit},
                )
                return result if isinstance(result, list) else []
            except Exception:
                logger.error(f"Pinterest search failed with both tool names: {e}")
                return []

    async def get_image_details(self, image_id: str) -> dict:
        """Obtiene detalles de una imagen de Pinterest."""
        return await self.call_tool("pinterest", "get_image_details", {"id": image_id})


# Funciones de conveniencia para uso síncrono
def search_pinterest_sync(query: str, limit: int = 10, download: bool = True) -> list[dict]:
    """Versión síncrona de search_pinterest."""
    service = MCPClientService()
    return asyncio.run(service.search_pinterest(query, limit, download))


def list_mcp_tools_sync(server_name: str) -> list[dict]:
    """Lista tools de un servidor MCP de forma síncrona."""
    service = MCPClientService()
    return asyncio.run(service.list_tools(server_name))
