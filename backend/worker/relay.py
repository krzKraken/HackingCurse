import asyncio
import sys


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


async def _handle(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target_host: str,
    target_port: int,
) -> None:
    try:
        remote_reader, remote_writer = await asyncio.open_connection(target_host, target_port)
    except OSError:
        client_writer.close()
        return
    await asyncio.gather(
        _pipe(client_reader, remote_writer),
        _pipe(remote_reader, client_writer),
    )


async def main(listen_port: int, target_host: str, target_port: int) -> None:
    server = await asyncio.start_server(
        lambda r, w: _handle(r, w, target_host, target_port), "0.0.0.0", listen_port
    )
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    # argv: listen_port target_host target_port instance_id
    # instance_id is accepted only so the process is identifiable in `ps`
    # output for manual debugging — it plays no role in the relay logic.
    listen_port_arg = int(sys.argv[1])
    target_host_arg = sys.argv[2]
    target_port_arg = int(sys.argv[3])
    asyncio.run(main(listen_port_arg, target_host_arg, target_port_arg))
