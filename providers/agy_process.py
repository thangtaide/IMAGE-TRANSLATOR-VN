"""Contain only the process tree created by one AGY invocation on Windows."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w


def active_agy_processes():
    """Read image names/PIDs only. Never reads arguments, sessions or credentials."""
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),
            ('heap',ctypes.c_size_t),('module',w.DWORD),('threads',w.DWORD),
            ('parent',w.DWORD),('priority',w.LONG),('flags',w.DWORD),('exe',w.WCHAR*260)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
    k.Process32FirstW.argtypes=k.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(ProcessEntry)]
    k.Process32FirstW.restype=k.Process32NextW.restype=w.BOOL
    k.CloseHandle.argtypes=[w.HANDLE]
    snap=k.CreateToolhelp32Snapshot(2,0)
    if snap==ctypes.c_void_p(-1).value:raise OSError('AGY_PROCESS_SNAPSHOT_FAILED')
    try:
        entry=ProcessEntry();entry.size=ctypes.sizeof(entry);found=[]
        more=k.Process32FirstW(snap,ctypes.byref(entry))
        while more:
            if entry.exe.lower()=='agy.exe':found.append(entry.pid)
            more=k.Process32NextW(snap,ctypes.byref(entry))
        return found
    finally:k.CloseHandle(snap)


class WindowsProcessTree:
    """Assign a suspended child before any user code runs. Never targets a name/PID tree."""
    def __init__(self):
        k = self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateJobObjectW.argtypes = [w.LPVOID, w.LPCWSTR]; k.CreateJobObjectW.restype = w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]
        k.SetInformationJobObject.restype = w.BOOL
        k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]; k.AssignProcessToJobObject.restype = w.BOOL
        k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]; k.TerminateJobObject.restype = w.BOOL
        k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID]
        k.QueryInformationJobObject.restype = w.BOOL
        k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
        k.CloseHandle.argtypes = [w.HANDLE]; k.CloseHandle.restype = w.BOOL
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError('AGY_JOB_CREATE_FAILED')

        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', w.DWORD), ('min_working', ctypes.c_size_t), ('max_working', ctypes.c_size_t),
                ('active_limit', w.DWORD), ('affinity', ctypes.c_size_t),
                ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ('read_ops','write_ops','other_ops',
                          'read_bytes','write_bytes','other_bytes')]

        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]

        info = Extended(); info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close(); raise OSError('AGY_JOB_LIMIT_FAILED')

    def assign_and_resume(self, process):
        k = self.k
        handle = k.OpenProcess(0x0101, False, process.pid)  # SET_QUOTA | TERMINATE
        if not handle:
            raise OSError('AGY_JOB_PROCESS_HANDLE_FAILED')
        try:
            if not k.AssignProcessToJobObject(self.handle, handle):
                raise OSError('AGY_JOB_ASSIGN_FAILED')
        finally:
            k.CloseHandle(handle)

        class ThreadEntry(ctypes.Structure):
            _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('tid', w.DWORD),
                ('pid', w.DWORD), ('base_priority', w.LONG), ('delta_priority', w.LONG), ('flags', w.DWORD)]
        k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        k.CreateToolhelp32Snapshot.restype = w.HANDLE
        k.Thread32First.argtypes = k.Thread32Next.argtypes = [w.HANDLE, ctypes.POINTER(ThreadEntry)]
        k.Thread32First.restype = k.Thread32Next.restype = w.BOOL
        k.OpenThread.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenThread.restype = w.HANDLE
        k.ResumeThread.argtypes = [w.HANDLE]; k.ResumeThread.restype = w.DWORD
        snapshot = k.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise OSError('AGY_THREAD_SNAPSHOT_FAILED')
        try:
            entry = ThreadEntry(); entry.size = ctypes.sizeof(entry)
            more = k.Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.pid == process.pid:
                    thread = k.OpenThread(2, False, entry.tid)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise OSError('AGY_THREAD_OPEN_FAILED')
                    try:
                        if k.ResumeThread(thread) != 1:
                            raise OSError('AGY_THREAD_RESUME_FAILED')
                        return
                    finally:
                        k.CloseHandle(thread)
                more = k.Thread32Next(snapshot, ctypes.byref(entry))
            raise OSError('AGY_PRIMARY_THREAD_MISSING')
        finally:
            k.CloseHandle(snapshot)

    def active(self):
        class Accounting(ctypes.Structure):
            _fields_ = [(n, ctypes.c_longlong) for n in ('user','kernel','period_user','period_kernel')] + [
                (n, w.DWORD) for n in ('faults','total','active','terminated')]
        info = Accounting()
        if not self.k.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
            raise OSError('AGY_JOB_QUERY_FAILED')
        return info.active

    def terminate(self):
        if self.handle and not self.k.TerminateJobObject(self.handle, 1):
            raise OSError('AGY_JOB_TERMINATE_FAILED')

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None
