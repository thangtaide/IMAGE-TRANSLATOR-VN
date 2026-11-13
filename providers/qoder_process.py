"""Bounded transport for the installed, official Windows Qoder executable."""
from __future__ import annotations

import os
import subprocess
import threading
import time

from core.types import CancelledError
from providers.online import ProviderSuspended


class QoderCancelled(CancelledError):
    code = 'CANCELLED'


def run_process(argv, payload, cwd, timeout, cancelled=lambda: False, limit=1_000_000):
    from providers.agy_process import WindowsProcessTree
    tree = WindowsProcessTree() if os.name == 'nt' else None
    process = None
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()
    threads = []
    started = time.monotonic()

    def drain(stream, buffer):
        try:
            while True:
                block = stream.read1(4096)
                if not block:
                    break
                if len(buffer) + len(block) > limit:
                    overflow.set()
                else:
                    buffer.extend(block)
        except OSError:
            overflow.set()

    def write():
        try:
            if payload is not None:
                process.stdin.write(payload)
                process.stdin.flush()
        except (OSError, BrokenPipeError):
            pass
        finally:
            process.stdin.close()

    try:
        environment = {k:v for k,v in os.environ.items() if not k.upper().startswith('QODER_')
            or k.upper() in ('QODER_PERSONAL_ACCESS_TOKEN','QODER_CONFIG_DIR')}
        process = subprocess.Popen(argv, cwd=cwd, env=environment, shell=False, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=(subprocess.CREATE_NO_WINDOW | 0x00000004) if tree else 0)
        if tree:
            tree.assign_and_resume(process)
        for stream, buffer in zip((process.stdout, process.stderr), buffers):
            thread = threading.Thread(target=drain, args=(stream, buffer), daemon=True)
            thread.start(); threads.append(thread)
        writer = threading.Thread(target=write, daemon=True)
        writer.start(); threads.append(writer)
        while process.poll() is None:
            if cancelled():
                raise QoderCancelled('Đã hủy Qoder; giữ checkpoint, không tự gửi lại.')
            if overflow.is_set():
                raise ProviderSuspended('INVALID_RESPONSE', 'Qoder vượt giới hạn stdout/stderr.')
            if time.monotonic() - started >= timeout:
                raise ProviderSuspended('TIMEOUT', 'Qoder hết thời gian chờ; kết quả/chi phí chưa xác định. Không tự retry.')
            time.sleep(.03)
    except FileNotFoundError:
        raise ProviderSuspended('CLI_NOT_FOUND', 'Không tìm thấy Qoder CLI đã cài.') from None
    except OSError:
        raise ProviderSuspended('PROVIDER_ERROR', 'Không khởi chạy hoặc quản lý được tiến trình Qoder.') from None
    finally:
        if tree:
            try:
                tree.terminate()
            finally:
                tree.close()
        elif process and process.poll() is None:
            process.kill()
        if process:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=2)
            for stream in (process.stdout, process.stderr):
                if not any(t.is_alive() for t in threads):
                    stream.close()
    if overflow.is_set() or any(t.is_alive() for t in threads):
        raise ProviderSuspended('INVALID_RESPONSE', 'Không thu được đầy đủ output Qoder trong giới hạn.')
    return process.returncode, bytes(buffers[0]), bytes(buffers[1])
