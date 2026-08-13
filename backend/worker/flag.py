import secrets


def generate_flag_token() -> str:
    return f"FLAG{{{secrets.token_hex(8)}}}"
