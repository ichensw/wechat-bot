"""Tests for command registry."""

from bot.admin.commands import CommandRegistry, CommandContext


class TestCommandRegistry:
    """Tests for CommandRegistry."""

    def test_register_command(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("test", description="Test command", admin_only=False)
        def test_cmd(ctx: CommandContext) -> str:
            return "test response"

        assert registry.count == 1
        assert "test" in registry.command_names

    def test_resolve_command(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("hello", admin_only=False)
        def hello(ctx: CommandContext) -> str:
            return "world"

        result = registry.resolve("#hello")
        assert result is not None
        cmd, args = result
        assert cmd.name == "hello"

    def test_resolve_with_args(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("add", usage="<item>")
        def add(ctx: CommandContext) -> str:
            return f"added {ctx.args}"

        result = registry.resolve("#add some_item")
        assert result is not None
        cmd, args = result
        assert args == "some_item"

    def test_resolve_unknown_command(self):
        registry = CommandRegistry(prefix="#")
        result = registry.resolve("#unknown")
        assert result is None

    def test_resolve_non_command(self):
        registry = CommandRegistry(prefix="#")
        result = registry.resolve("just a message")
        assert result is None

    def test_execute_command(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("greet", admin_only=False)
        def greet(ctx: CommandContext) -> str:
            return f"Hello {ctx.sender_name}!"

        ctx = CommandContext(sender_wxid="wxid_test", sender_name="Alice", is_admin=False)
        response = registry.execute("#greet", ctx)
        assert response == "Hello Alice!"

    def test_execute_admin_only_denied(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("admin_cmd", admin_only=True)
        def admin_cmd(ctx: CommandContext) -> str:
            return "secret"

        ctx = CommandContext(sender_wxid="wxid_stranger", is_admin=False)
        response = registry.execute("#admin_cmd", ctx)
        assert "仅管理员" in response

    def test_execute_admin_only_allowed(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("admin_cmd", admin_only=True)
        def admin_cmd(ctx: CommandContext) -> str:
            return "secret"

        ctx = CommandContext(sender_wxid="wxid_admin", is_admin=True)
        response = registry.execute("#admin_cmd", ctx)
        assert response == "secret"

    def test_command_aliases(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("帮助", admin_only=False, aliases=["help", "h"])
        def help_cmd(ctx: CommandContext) -> str:
            return "help text"

        # Main name works
        assert registry.resolve("#帮助") is not None
        # Alias works
        assert registry.resolve("#help") is not None
        assert registry.resolve("#h") is not None

    def test_format_help(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("测试", description="测试命令", admin_only=False)
        def test_cmd(ctx: CommandContext) -> str:
            return "ok"

        @registry.command("管理", description="管理命令", admin_only=True)
        def admin_cmd(ctx: CommandContext) -> str:
            return "ok"

        help_text = registry.format_help()
        assert "#测试" in help_text
        assert "#管理" in help_text
        assert "公开命令" in help_text
        assert "管理员命令" in help_text

    def test_error_in_handler(self):
        registry = CommandRegistry(prefix="#")

        @registry.command("fail", admin_only=False)
        def fail_cmd(ctx: CommandContext) -> str:
            raise ValueError("test error")

        ctx = CommandContext(sender_wxid="test", is_admin=False)
        response = registry.execute("#fail", ctx)
        assert "出错" in response
