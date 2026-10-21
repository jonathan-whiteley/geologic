import pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIPPED = ("src", "jobs", "sql", "app/backend", "app/frontend/src", "genie", "scripts", "resources", "pipelines",
           "README.md", "databricks.yml", "app/app.yaml")

def test_no_em_or_en_dashes_in_shipped_files():
    files = subprocess.run(["git", "ls-files", *SHIPPED], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    bad = [f for f in files if (ROOT / f).is_file() and ("\u2014" in (ROOT / f).read_text(errors="ignore")
                                                        or "\u2013" in (ROOT / f).read_text(errors="ignore"))]
    assert bad == []
