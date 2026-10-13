"""Portable launcher: native Python service, local browser UI, no remote service."""

import argparse
import socket
import threading
import webbrowser


def main():
    """
    Bind only IPv4 loopback, never all interfaces or a remote address.
    Port zero lets the operating system choose an unused local port.
    Pass the already-bound socket to the server to avoid a port selection race.
    Delay browser opening until the service reports a successful start.
    A no-browser option supports scripted local acceptance and manual browser choice.
    The UI shutdown callback requests graceful termination of this server instance.
    The console variant can also be stopped with the usual terminal interruption.
    The browser UI is local packaging, not a hosted cloud application.
    """
    parser = argparse.ArgumentParser(description="图译 · 本地机械图纸翻译")
    parser.add_argument("--port", type=int, default=0, help="0 自动选择可用端口")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    # Hand an already bound socket to uvicorn, avoiding a free-port race.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", args.port))
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    print(f"图译已启动：{url}\n所有图纸和译文只保存在本机。关闭此窗口可退出。", flush=True)
    import uvicorn
    from . import service
    config = uvicorn.Config(service.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    service.shutdown_callback = lambda: setattr(server, "should_exit", True)
    if not args.no_browser:
        def open_when_ready():
            import time
            while not server.started and not server.should_exit:
                time.sleep(.1)
            if server.started:
                webbrowser.open(url)
        threading.Thread(target=open_when_ready, daemon=True).start()
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
