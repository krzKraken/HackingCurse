from app.config import Settings


def test_labs_terminal_relay_port_default():
    settings = Settings()
    assert settings.labs_terminal_relay_port == 8765
