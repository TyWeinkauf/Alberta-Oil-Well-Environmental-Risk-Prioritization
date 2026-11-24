"""Build the portable classroom ZIP from a verified projected package."""
import argparse
import hashlib
from pathlib import Path
from subprocess import check_output
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from _bootstrap import run_cli
from src.artifacts import atomic_output
from src.config import ROOT
from src.demo.data import DEFAULT_PACKAGE, decode_package, read_package_bytes


START = """# ST37 classroom demo

Install the pinned dependencies with Python 3.12 before going offline. In the
extracted folder, open PowerShell and run:

```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Stay in **Classroom demo**. Choose Red Deer, Drayton Valley or Both. Choose the
water layer and use **Buffer distance** to compare 50 m, 100 m, 250 m and 500 m. Uncheck
**Only show wells within the buffer** to see all filtered wells. Click a well to
inspect its reported attributes and display the selected radius. The CSV, GeoJSON,
standalone map and manifest are below the table. Leave the optional OpenStreetMap basemap off for
offline use. The app reads the bundled JSON locally.

Source credit is Alberta Energy Regulator, ST37 List of Wells in Alberta
(surface holes). The archive contains an attributed regional extract for
educational use. The app and downloaded manifest describe the source and
coverage of each environmental layer. See the [ST37 product page](https://www.aer.ca/data-and-performance-reports/statistical-reports/st37)
and [AER reproduction terms](https://www.aer.ca/copyright-and-disclaimer).
"""


def package_classroom(data_path: Path, output: Path) -> tuple[str, str]:
    contents = read_package_bytes(data_path)
    package = decode_package(contents)
    if package['manifest']['readiness'] != 'projected':
        raise ValueError('The teacher ZIP requires a projected classroom package')
    if output.suffix.lower() != '.zip':
        raise ValueError('Choose a .zip output path')

    names = check_output([
        'git', 'ls-files', '-z', '--', 'LICENSE', 'app.py', 'requirements.txt',
        'config/*.yml', 'src/*.py', 'sql/migrations/*.sql', 'vendor/',
    ], cwd=ROOT).decode('utf-8').split('\0')
    files = {name: (ROOT / name).read_bytes() for name in names if name}
    start = START + '\n' + package['manifest']['disclaimer'] + '\n'
    files.update({'START.md': start.encode('utf-8'), DEFAULT_PACKAGE.relative_to(ROOT).as_posix(): contents})
    with atomic_output(output) as candidate:
        with ZipFile(candidate, 'w') as archive:
            for name, data in sorted(files.items()):
                archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
        with ZipFile(candidate) as archive:
            if archive.testzip() is not None:
                raise ValueError('The generated archive failed its member checksum check')
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return package['package_id'], digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/classroom/st37-classroom-imported-water.zip')
    args = parser.parse_args()
    package_id, digest = package_classroom(args.package, args.output)
    print(f'{args.output} ({args.output.stat().st_size} bytes)')
    print(f'Package ID {package_id}\nArchive SHA-256 {digest}')


if __name__ == '__main__':
    run_cli(main, error_hint='Check the repository checkout and projected classroom package.')
