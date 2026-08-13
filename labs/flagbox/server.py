import asyncio
import os

FLAG_TOKEN = os.environ.get("FLAG_TOKEN", "FLAG{dev_placeholder}")

USERS: dict[str, int] = {}
NOTES: dict[int, dict[str, str]] = {
    0: {"owner": "admin", "content": FLAG_TOKEN},
    1: {"owner": "alice", "content": "Reunion movida a las 3pm."},
    2: {"owner": "bob", "content": "Recordar renovar el certificado TLS."},
}

_next_user_id = 1


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    global _next_user_id
    session: dict[str, str | int | None] = {"username": None, "user_id": None}

    writer.write(b"FLAGBOX v1\r\n")
    await writer.drain()

    while True:
        line = await reader.readline()
        if not line:
            break
        command = line.decode("utf-8", errors="replace").strip()
        if not command:
            continue

        parts = command.split(" ", 1)
        verb = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "LOGIN":
            username = arg.strip() or "anonymous"
            if username not in USERS:
                USERS[username] = _next_user_id
                _next_user_id += 1
            session["username"] = username
            session["user_id"] = USERS[username]
            writer.write(f"OK session={session['user_id']}\r\n".encode())

        elif verb == "WHOAMI":
            if session["username"] is None:
                writer.write(b"ERR not logged in\r\n")
            else:
                writer.write(f"USER {session['username']} id={session['user_id']}\r\n".encode())

        elif verb == "GET":
            if session["username"] is None:
                writer.write(b"ERR not logged in\r\n")
            else:
                try:
                    note_id = int(arg.strip())
                except ValueError:
                    writer.write(b"ERR invalid id\r\n")
                else:
                    # VULNERABILITY: no check that note_id belongs to the
                    # logged-in session — classic IDOR at the protocol level.
                    note = NOTES.get(note_id)
                    if note is None:
                        writer.write(b"ERR not found\r\n")
                    else:
                        writer.write(f"NOTE {note['content']}\r\n".encode())

        else:
            writer.write(b"ERR unknown command\r\n")

        await writer.drain()

    writer.close()


async def main() -> None:
    server = await asyncio.start_server(handle_client, "0.0.0.0", 9000)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
