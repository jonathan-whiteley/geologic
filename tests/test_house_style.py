import pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIPPED = ("src", "jobs", "sql", "app/backend", "app/frontend/src", "genie", "scripts", "resources", "pipelines",
           "README.md", "databricks.yml", "app/app.yaml")

def test_no_em_or_en_dashes_in_shipped_files():
    files = subprocess.run(["git", "ls-files", *SHIPPED], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    bad = [f for f in files if (ROOT / f).is_file() and ("\u2014" in (ROOT / f).read_text(errors="ignore")
                                                        or "\u2013" in (ROOT / f).read_text(errors="ignore"))]
    assert bad == []

def test_no_vendor_names_on_screen_or_in_readme():
    files = subprocess.run(["git", "ls-files", "app/frontend/src", "README.md", "genie"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split()
    bad = [f for f in files if any(w in (ROOT / f).read_text(errors="ignore").lower() for w in ("profound", "revere", "peec"))]
    assert bad == []

def test_unlicensed_assets_stay_local():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for pattern in ("_press.jpg", "goff_slices_n_stix.jpg", "kittle_radio_row.jpg", "lce-pepperoni.webp", "count-caesar.png",
                    "docs/demo-script", "docs/superpowers/", "mockups/"):
        assert not any(pattern in t for t in tracked), pattern

def test_retired_people_are_gone():
    files = subprocess.run(["git", "ls-files", *SHIPPED], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    bad = [f for f in files if (ROOT / f).is_file() and any(w in (ROOT / f).read_text(errors="ignore")
                                                            for w in ("Merriwether", "p_fictional_dax", "EX-01", "Saquon", "Justin Jefferson"))]
    assert bad == []
