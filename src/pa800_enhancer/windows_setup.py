from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GeneratedWindowsScripts:
    install_path: str
    run_path: str


def generate_windows_scripts(
    output_directory: Path = Path("."), *, overwrite: bool = False
) -> GeneratedWindowsScripts:
    targets = {
        "install.bat": output_directory / "install.bat",
        "run.bat": output_directory / "run.bat",
    }
    if not overwrite:
        existing = [path for path in targets.values() if path.exists()]
        if existing:
            raise FileExistsError(f"refusing to overwrite {existing[0]}")
    template_root = files("pa800_enhancer").joinpath("templates")
    contents = {
        name: template_root.joinpath(f"{name}.txt").read_text(encoding="utf-8")
        for name in targets
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, path in targets.items():
        path.write_text(contents[name], encoding="utf-8", newline="\r\n")
    return GeneratedWindowsScripts(
        install_path=str(targets["install.bat"]),
        run_path=str(targets["run.bat"]),
    )