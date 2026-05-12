# Changelog

All notable changes to the MCP Server Odoo module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [17.0.1.0.6] - 2026-04-30

### Added

- Map `message_post` XML-RPC method to the `write` operation so chatter messages can be posted via the MCP XML-RPC endpoint on models with write access.

## [17.0.1.0.5] - 2026-03-15

### Fixed

- **odoo.sh Test Compatibility**: Added `@mute_logger` decorators to tests that deliberately trigger ERROR-level logs, preventing false failures on odoo.sh

## [17.0.1.0.4] - 2026-02-25

### Added

- **Session-Based Authentication**: Endpoints now accept Odoo session cookies in addition to API keys, enabling browser-based access
- **Auth Method Reporting**: `/mcp/auth/validate` response includes `auth_method` field (`api_key` or `session`)

### Changed

- Authentication priority: API key → session → 401 (previously API key only)
- Routes changed from `auth="none"` to `auth="public"` for session resolution

## Removed

- **"Require API Keys" setting** (`mcp_server.use_api_keys`): All endpoints now always require a valid API key or session cookie

## [17.0.1.0.3] - 2025-08-18

### Added
- **Technical Menu**: Added MCP section with Available Models and Logs menu items under Settings → Technical → MCP for easier access

## [17.0.1.0.2] - 2025-06-28

### Fixed
- **Configuration Defaults**: Fixed checkbox states in settings view to properly reflect field defaults

## [17.0.1.0.1] - 2025-06-26

### Added

- **Initial Release for Odoo 17**: Version of MCP Server module for Odoo 17
- **Security Groups**: MCP Administrator (full access) and MCP User (read-only)
- **Model Configuration**: Enable/disable models with granular permissions (read, write, create, unlink)
- **API Key Authentication**: Secure authentication with rate limiting support
- **REST API Endpoints**:
  - `/mcp/health` - Health check
  - `/mcp/auth/validate` - API key validation
  - `/mcp/system/info` - System information
  - `/mcp/models` - List enabled models
  - `/mcp/models/{model}/access` - Check permissions
- **XML-RPC Controllers**: MCP-specific endpoints with access control
  - `/mcp/xmlrpc/common` - Authentication
  - `/mcp/xmlrpc/object` - Model operations
- **Configuration UI**: Settings integration and model selection wizard
- **Audit Logging**: Comprehensive operation tracking with built-in viewer
- **Data Models**:
  - `mcp.enabled.model` - Model access configuration
  - `mcp.log` - Audit trail

### Technical Details
- Compatible with Odoo 17.0
- Follows Odoo module best practices
- Extensive test coverage
- Full documentation and type hints