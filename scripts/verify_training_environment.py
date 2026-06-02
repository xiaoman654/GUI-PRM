import importlib
import json
import platform


PACKAGES = [
    "torch",
    "transformers",
    "datasets",
    "peft",
    "accelerate",
    "qwen_vl_utils",
    "PIL",
]


def package_status(name: str) -> dict:
    try:
        module = importlib.import_module(name)
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    return {"available": True, "version": getattr(module, "__version__", "unknown")}


def main() -> None:
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {name: package_status(name) for name in PACKAGES},
    }
    torch_status = report["packages"].get("torch", {})
    if torch_status.get("available"):
        import torch

        report["cuda"] = {
            "available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count(),
            "devices": [
                torch.cuda.get_device_name(idx)
                for idx in range(torch.cuda.device_count())
            ],
            "torch_cuda": torch.version.cuda,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
