from django.core.management.base import BaseCommand, CommandError

from tracker.mcp_server import (
    mcp,
    mcp_path,
    run_mcp_server,
    validate_mcp_configuration,
)


class Command(BaseCommand):
    help = 'Run the ChatGPT-compatible Streamable HTTP MCP server.'

    def handle(self, *args, **options):
        try:
            validate_mcp_configuration()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f'Starting MCP on {mcp.settings.host}:{mcp.settings.port}'
            f'{"/<redacted>/mcp" if mcp.settings.streamable_http_path != "/mcp" else mcp_path()}'
        )
        try:
            run_mcp_server()
        except KeyboardInterrupt:
            self.stdout.write('MCP server stopped.')
