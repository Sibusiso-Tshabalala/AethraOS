"""Local machine facts. No shutdown, volume, or network changes."""

import platform
import shutil
import subprocess

import psutil


def get_system_info():
    memory = psutil.virtual_memory()
    return {
        "success": True,
        "verified": True,
        "operating_system": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_usage_percent": psutil.cpu_percent(interval=0.2),
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "memory_used_percent": memory.percent,
    }


def get_disk_info():
    usage = shutil.disk_usage("C:\\" if platform.system() == "Windows" else "/")
    free_gb = round(usage.free / (1024 ** 3), 1)
    return {
        "success": True,
        "verified": True,
        "free_gb": free_gb,
        "total_gb": round(usage.total / (1024 ** 3), 1),
        "message": f"{free_gb} GB free.",
    }


def get_top_process():
    top = None
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            mem = proc.info["memory_info"].rss
        except Exception:
            continue
        if top is None or mem > top[1]:
            top = (proc.info.get("name") or "unknown", mem)
    if not top:
        return {"success": False, "verified": False, "error": "No process info."}
    return {
        "success": True,
        "verified": True,
        "name": top[0],
        "memory_gb": round(top[1] / (1024 ** 3), 2),
        "message": f"{top[0]} is using the most memory.",
    }


def get_gpu_info():
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).strip()
    except Exception as exc:
        return {"success": False, "verified": False, "error": f"NVIDIA info unavailable: {exc}"}
    name, used, total, temp = [part.strip() for part in output.splitlines()[0].split(",")]
    return {
        "success": True,
        "verified": True,
        "name": name,
        "memory_used_mb": int(float(used)),
        "memory_total_mb": int(float(total)),
        "temperature_c": int(float(temp)),
        "message": f"{name}: {used} MB of {total} MB, {temp} C.",
    }


def get_system_health():
    info = get_system_info()
    disk = get_disk_info()
    gpu = get_gpu_info()
    top = get_top_process()
    verdict = "ok"
    if info["memory_used_percent"] >= 85 or disk["free_gb"] < 20:
        verdict = "tight"
    if gpu.get("success") and gpu.get("temperature_c", 0) >= 80:
        verdict = "hot"
    return {
        "success": True,
        "verified": True,
        "verdict": verdict,
        "memory_used_percent": info["memory_used_percent"],
        "disk_free_gb": disk["free_gb"],
        "gpu": gpu.get("message") or gpu.get("error"),
        "top_process": top.get("name"),
        "message": f"System is {verdict}.",
    }