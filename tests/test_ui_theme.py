import unittest
from unittest import mock
import ui_theme


class TestTheme(unittest.TestCase):
    def test_global_css_has_apple_dark_selectors(self):
        css = ui_theme.GLOBAL_CSS
        for selector in ("stSidebar", "stMetric", "stDataFrame", "prefers-reduced-motion", "backdrop-filter"):
            self.assertIn(selector, css)
        self.assertIn("#0a0a0f", css)
        self.assertIn("#0a84ff", css)

    def test_inject_theme_marks_down_markdown(self):
        st = mock.Mock()
        with mock.patch.dict("sys.modules", {"streamlit": st}):
            import importlib
            ui_theme_mod = importlib.reload(ui_theme)
            ui_theme_mod.inject_theme()
        args = st.markdown.call_args
        self.assertTrue(args.kwargs.get("unsafe_allow_html", args.args[1] if len(args.args) > 1 else False))

    def test_conn_badge_connected(self):
        html = ui_theme.conn_badge_html(True, "Conectado · Paper")
        self.assertIn("Conectado", html)
        self.assertIn("online", html)

    def test_conn_badge_disconnected(self):
        html = ui_theme.conn_badge_html(False, "No conectado")
        self.assertIn("No conectado", html)
        self.assertIn("offline", html)


if __name__ == "__main__":
    unittest.main()
