# Labs Sub-plan B: Terminal Web Integrada — Diseño

> Continuación de Labs Sub-plan A (`docs/superpowers/specs/2026-08-13-labs-orchestrator-design.md`).
> Sub-plan A entregó el orquestador Docker + acceso publicado por relay TCP.
> Sub-plan B entrega el segundo método de acceso pedido por el usuario: una terminal
> web integrada (xterm.js) que da una shell real dentro del contenedor del lab.

## Objetivo

Cuando una `LabInstance` está `running`, el usuario puede abrir una terminal en el
navegador (sin instalar nada, sin `nc`/SSH manual) que le da una shell (`/bin/sh`)
dentro del contenedor del lab, además del acceso por puerto publicado que ya existe.

## Decisiones de diseño (confirmadas con el usuario)

1. **Shell del contenedor**, no un cliente de red hacia el servicio del lab — el usuario
   quiere poder explorar el sistema de archivos del contenedor, no solo hablar con el
   servicio vulnerable (para eso ya está el acceso por puerto publicado de Sub-plan A).
2. **El worker sigue siendo el único proceso que toca el socket Docker** (invariante de
   Sub-plan A). Para lograr streaming bidireccional en tiempo real sin romper esa regla,
   el worker expone un relay WebSocket local (`127.0.0.1`) y la API hace de proxy
   autenticado hacia él — RQ (fire-and-forget) no sirve para esto.
3. **Terminal disponible solo mientras `status == running`** — no durante `provisioning`
   ni después de `destroyed`/`expired`.

## Arquitectura

```
Browser (xterm.js)
   │  wss://.../api/v1/labs/{lab_id}/terminal
   ▼
FastAPI WebSocket endpoint (API process)
   — autentica al usuario vía cookie de sesión
   — verifica que la LabInstance pertenece al usuario y status == running
   — abre un WebSocket saliente hacia el relay del worker
   — relaya bytes browser ⇄ worker en ambas direcciones
   │  ws://127.0.0.1:<relay_port>/{instance_id}
   ▼
Terminal relay server (proceso worker, nuevo servidor asyncio websockets)
   — re-valida que la instancia esté running (consulta DB)
   — docker exec_create + exec_start(tty=True, socket=True) → /bin/sh en el contenedor
   — relaya bytes worker-WS ⇄ exec socket del contenedor, ambas direcciones
   — reenvía eventos de resize a docker exec_resize
   ▼
Shell del contenedor (/bin/sh, dentro de la red aislada del lab)
```

Este diseño reutiliza el patrón ya probado de `relay.py` (Sub-plan A): un proceso host
puentea hacia dentro de una red Docker aislada. Aquí el "host" es el proceso worker,
que ya tiene acceso al Docker SDK y a la base de datos.

## Componentes

### `backend/worker/terminal_relay.py` (nuevo)
- Servidor `websockets` en `127.0.0.1:<LABS_TERMINAL_RELAY_PORT>` (nuevo setting en
  `app/config.py`, default `8765`).
- Arrancado en un hilo daemon desde `run_worker.py`, mismo patrón que el hilo de
  `sweep_expired_labs()`.
- Por cada conexión con path `/{instance_id}`:
  - Consulta `LabInstance` por id; si no existe o `status != running`, cierra con
    código 4404.
  - `client.api.exec_create(container_id, cmd="/bin/sh", tty=True, stdin=True, stdout=True, stderr=True)`
  - `client.api.exec_start(exec_id, tty=True, socket=True)` → socket crudo bidireccional.
  - Bucle de relay: lee del socket del contenedor → envía por WS; lee del WS → escribe
    al socket del contenedor. Corre con `loop.sock_recv`/`sock_sendall` sobre el fd
    subyacente del socket que devuelve docker-py.
  - Mensajes de control JSON `{"type": "resize", "cols": N, "rows": N}` intercalados en
    el flujo entrante del WS se interceptan (no se escriben al contenedor) y disparan
    `client.api.exec_resize(exec_id, height=rows, width=cols)`. Todo lo demás son bytes
    crudos de terminal.
  - Al cerrarse cualquiera de los dos extremos, cierra el otro y libera el exec socket.

### `backend/app/labs/router.py` (modificado)
- Nuevo endpoint `@router.websocket("/{lab_id}/terminal")` (usa `lab_id` como nombre de
  path param — nunca `session_id`, por el gotcha ya documentado de Sub-plan A).
- Autentica leyendo la cookie de sesión igual que las rutas HTTP existentes.
- Verifica que la `LabInstance` pertenece al usuario autenticado y que
  `status == running`; si no, cierra el WS con código 4403 o 4404 según corresponda.
- Abre `websockets.connect(f"ws://127.0.0.1:{settings.labs_terminal_relay_port}/{instance.id}")`.
  Si falla (worker caído), cierra con 4503 "terminal service unavailable".
- Hace `asyncio.gather` de dos tareas de relay (browser→worker, worker→browser) hasta
  que cualquiera de los dos lados se desconecte.

### `frontend/src/features/labs/LabTerminal.tsx` (nuevo)
- Nuevas dependencias npm: `xterm`, `xterm-addon-fit`.
- Monta un `Terminal` de xterm.js en un `div`, usa `FitAddon` para ajustar filas/columnas
  al contenedor.
- Abre `new WebSocket(...)` hacia `/api/v1/labs/{labId}/terminal`.
- Teclado del usuario → `ws.send(data)`. Mensajes del WS → `term.write(data)`.
- En `onResize` del `FitAddon`, envía `{"type": "resize", "cols": ..., "rows": ...}`
  como mensaje JSON por el mismo WS.
- Al desmontar el componente, cierra el WS.

### `frontend/src/features/labs/LabInstancePage.tsx` (modificado)
- Botón "Abrir terminal" visible solo cuando `instance.status === "running"`.
- Al hacer click, monta `<LabTerminal labId={...} />` (toggle, se puede cerrar y reabrir).

### `frontend/src/lib/api.ts` (modificado)
- No requiere nuevo método REST — el WebSocket se abre directo desde el componente
  usando la URL base ya conocida.

## Manejo de errores

| Caso | Comportamiento |
|---|---|
| Instancia no `running` | API cierra el WS con código 4404, mensaje "lab not running" |
| Usuario no es dueño de la instancia | API cierra el WS con código 4403 |
| Worker/relay no disponible | API cierra el WS con código 4503, mensaje "terminal service unavailable" |
| Contenedor sin `/bin/sh` | El error de `exec_start` se propaga como cierre 4500 con el mensaje de Docker (no se asume silenciosamente que todas las imágenes lo tienen, aunque las actuales sí) |
| Browser se desconecta | La API cierra su WS saliente hacia el worker; el worker cierra el exec socket — no quedan procesos exec huérfanos |
| Lab se destruye/expira mientras la terminal está abierta | El contenedor desaparece, el exec socket se rompe, el worker detecta el cierre y cierra el WS hacia la API, que cierra el WS hacia el browser |

## Testing

Sigue la filosofía ya establecida en Sub-plan A: tests de integración reales contra
Docker, sin mocks.

- `backend/tests/worker/test_terminal_relay.py`: levanta el relay server real apuntando
  a un contenedor real (reutiliza fixtures de `test_docker_ops.py`), conecta un cliente
  WS crudo, manda `echo hola\n`, verifica que la salida contiene `hola`. Prueba también
  el caso de instancia no-`running` → cierre inmediato con 4404.
- `backend/tests/labs/test_terminal_router.py`: prueba a nivel del endpoint de la API —
  usuario no dueño → 4403, instancia no `running` → 4404, camino feliz con un relay real
  corriendo en background durante el test (echo roundtrip vía el proxy completo
  browser-side).

## Fuera de alcance (explícitamente)

- Múltiples terminales concurrentes hacia la misma instancia: se permite de forma
  natural (cada conexión WS abre su propio `exec`), pero no hay UI de "sesiones activas"
  ni límite artificial — no es necesario para un solo usuario.
- Grabación/replay de sesiones de terminal.
- Terminal durante `provisioning` (el usuario confirmó: solo cuando `running`).
