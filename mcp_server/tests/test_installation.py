from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMcpServerInstallation(TransactionCase):
    """Test the installation of the MCP Server module."""

    def test_module_installed(self):
        """Test if the module is properly installed."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "mcp_server"),
            ]
        )
        self.assertTrue(module.exists())
        self.assertEqual(module.state, "installed")
