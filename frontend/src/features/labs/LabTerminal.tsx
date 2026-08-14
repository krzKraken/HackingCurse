import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

type LabTerminalProps = {
  instanceId: string;
};

export function LabTerminal({ instanceId }: LabTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({ convertEol: true });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(
      `${protocol}//${window.location.host}/api/v1/labs/instances/${instanceId}/terminal`
    );
    ws.binaryType = "arraybuffer";

    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        term.write(event.data);
      } else {
        term.write(new Uint8Array(event.data));
      }
    };

    ws.onclose = (event) => {
      term.write(`\r\n\r\n[terminal cerrada: ${event.reason || event.code}]\r\n`);
    };

    const dataDisposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    const sendResize = () => {
      fitAddon.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
    };
    window.addEventListener("resize", sendResize);
    ws.onopen = sendResize;

    return () => {
      window.removeEventListener("resize", sendResize);
      dataDisposable.dispose();
      ws.close();
      term.dispose();
    };
  }, [instanceId]);

  return <div ref={containerRef} style={{ height: "400px", width: "100%" }} />;
}
