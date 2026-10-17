"""Read only selected Firefox crash fields from the runner's own profiles."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = []
    fields = ("Version", "ProcessType", "MozCrashReason", "OOMAllocationSize",
              "AvailablePhysicalMemory", "SystemMemoryUsePercentage", "AvailableVirtualMemory",
              "AvailablePageFile", "TotalPageFile", "StartupTime", "GraphicsCriticalError",
              "GpuProcessStatus", "GPUProcessStatus", "GPUProcessLaunchCount", "HeadlessMode")
    for profile in (root / ".local").glob("chatgpt-firefox-profile*"):
        for path in (profile / "minidumps").glob("*.extra"):
            data = json.loads(path.read_text(encoding="utf-8"))
            crash_time = datetime.fromtimestamp(int(data.get("CrashTime", "0")), timezone.utc)
            if crash_time.date().isoformat() != args.date:
                continue
            row = {"profile": profile.name, "path": str(path), "crash_utc": crash_time.isoformat()}
            row.update({key: data[key] for key in fields if key in data})
            stack = data.get("StackTraces", {})
            if isinstance(stack, str):
                try:
                    stack = json.loads(stack)
                except ValueError:
                    stack = {}
            if isinstance(stack, dict):
                info = stack.get("crash_info", {})
                row["crash_info"] = info
                thread = info.get("crashing_thread")
                threads = stack.get("threads", [])
                if isinstance(thread, int) and 0 <= thread < len(threads):
                    row["top_frames"] = [
                        {key: frame[key] for key in ("function", "module", "module_offset") if key in frame}
                        for frame in threads[thread].get("frames", [])[:5]
                    ]
            rows.append(row)
    for row in sorted(rows, key=lambda row: row["crash_utc"]):
        print(json.dumps(row, ensure_ascii=True))
    print(json.dumps({"date": args.date, "crashes": len(rows)}))


if __name__ == "__main__":
    main()
