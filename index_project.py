import os
import mimetypes
import shutil

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "indexed_src")
SKIP_DIRS = {
    'venv', '.venv', '__pycache__', 'node_modules', '.git', '.mypy_cache',
    'dist', 'build', '.next', 'coverage', 'migrations', 'static', 'staticfiles',
    'media', 'public', '.parcel-cache', 'indexed_src'
}
INCLUDE_EXT = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.md', '.rst', '.yml', '.yaml', '.json',
    '.css', '.scss', '.html', '.txt', '.env', '.ini'
}
INCLUDE_NAMES = {'Dockerfile', 'docker-compose.yml', 'Makefile', '.env.example'}
MAX_FILE_SIZE = 200_000  # 200 KB

ROOT_FILES = [
    "README.md",
    "debug.md",
    "docker-compose.yml",
    "install.md",
    "progress.md",
    "Carbon-dev-roadmap_v0.1.md",
    "Carbon-design-v1.0.md"
]

def is_text_file(path):
    if os.path.isdir(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext in INCLUDE_EXT or os.path.basename(path) in INCLUDE_NAMES:
        return True
    if os.path.basename(path).startswith('Dockerfile'):
        return True
    mime = mimetypes.guess_type(path)[0]
    if mime and not mime.startswith('text'):
        return False
    return False

def should_skip_dir(dirname):
    return dirname in SKIP_DIRS or dirname.startswith('.')

def ensure_output_dir():
    # Remove old contents if exists, then recreate
    if os.path.exists(OUTPUT_ROOT):
        shutil.rmtree(OUTPUT_ROOT)
    os.makedirs(OUTPUT_ROOT)

def process_folder(folder):
    outputs = []
    for entry in sorted(os.listdir(folder)):
        path = os.path.join(folder, entry)
        if os.path.isfile(path) and is_text_file(path) and os.path.getsize(path) <= MAX_FILE_SIZE:
            try:
                with open(path, encoding='utf-8') as fin:
                    content = fin.read()
            except Exception:
                continue  # skip unreadable files
            rel_path = os.path.relpath(path, PROJECT_ROOT)
            file_header = f"=== {rel_path} ===\n"
            outputs.append(file_header + content + "\n\n")
    if outputs:
        rel_dir = os.path.relpath(folder, PROJECT_ROOT)
        safe_name = rel_dir.replace(os.sep, "_")
        if safe_name == '.' or safe_name == '':
            safe_name = os.path.basename(os.path.abspath(folder))
        out_path = os.path.join(OUTPUT_ROOT, f"{safe_name}.txt")
        with open(out_path, "w", encoding='utf-8') as fout:
            fout.writelines(outputs)

def process_docs_folder():
    docs_path = os.path.join(PROJECT_ROOT, "docs")
    if not os.path.exists(docs_path):
        return
    for dirpath, dirnames, filenames in os.walk(docs_path):
        # Skip diagrams subfolder and hidden dirs
        dirnames[:] = [d for d in dirnames if d != "diagrams" and not d.startswith('.')]
        process_folder(dirpath)

def process_root_docs():
    outputs = []
    for fname in ROOT_FILES:
        path = os.path.join(PROJECT_ROOT, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as fin:
                content = fin.read()
        except Exception:
            continue
        file_header = f"=== {fname} ===\n"
        outputs.append(file_header + content + "\n\n")
    if outputs:
        os.makedirs(OUTPUT_ROOT, exist_ok=True)
        out_path = os.path.join(OUTPUT_ROOT, "root.txt")
        with open(out_path, "w", encoding='utf-8') as fout:
            fout.writelines(outputs)

def main():
    ensure_output_dir()
    # Root docs first
    process_root_docs()
    # Docs folder (excluding diagrams)
    process_docs_folder()
    # Then index backend/frontend
    for top in ['backend', 'frontend']:
        top_path = os.path.join(PROJECT_ROOT, top)
        if not os.path.exists(top_path):
            continue
        for dirpath, dirnames, filenames in os.walk(top_path):
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
            process_folder(dirpath)

if __name__ == '__main__':
    main()