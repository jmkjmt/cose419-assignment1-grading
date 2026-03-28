import os
import re
import csv
import shutil
import subprocess
import tempfile
import json

SUBMISSIONS_DIR = "submissions"
BASE_REPO = "click"
DOCKER_IMAGE = "click-test"
TIMEOUT = 20


# -----------------------------
# Step 0: baseline coverage
# -----------------------------
def get_baseline_coverage():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = os.path.join(tmpdir, BASE_REPO)
        shutil.copytree(BASE_REPO, repo_dir)

        cmd = f"""
         docker run --rm -v "{repo_dir}:/app" -w /app {DOCKER_IMAGE} \
        sh -c "python -m pip install -e . && \
               python -m coverage erase && \
               python -m coverage run --source=src/ -m pytest tests/ && \
               python -m coverage json -o cov.json"
        """

        subprocess.run(cmd, shell=True, check=True)

        cov_path = os.path.join(repo_dir, "cov.json")
        with open(cov_path) as f:
            data = json.load(f)

    coverage_map = {}
    for file, info in data["files"].items():
        covered = set(info["executed_lines"])
        # 경로 normalize
        file = file.replace("\\", "/")
        coverage_map[file] = covered

    return coverage_map


# -----------------------------
# Step 1: patch parsing
# -----------------------------
def parse_patch(patch_path):
    file_path = None
    added_lines = set()
    current_line = None

    hunk_count = 0

    with open(patch_path) as f:
        for line in f:
            if line.startswith("+++ "):
                file_path = line.split()[1]
                file_path = file_path.replace("b/", "").strip()

            elif line.startswith("@@"):
                hunk_count += 1
                m = re.search(r"\+(\d+)", line)
                if m:
                    current_line = int(m.group(1))

            elif line.startswith("+") and not line.startswith("+++"):
                if current_line is not None:
                    added_lines.add(current_line)
                    current_line += 1

            elif line.startswith("-") and not line.startswith("---"):
                # deletion does not advance new file line
                pass

            else:
                if current_line is not None:
                    current_line += 1

    return file_path, added_lines, hunk_count


# -----------------------------
# Step 2: single hunk
# -----------------------------
def is_single_hunk(lines, hunk_count):
    if hunk_count != 1:
        return False
    if not lines:
        return False

    sorted_lines = sorted(lines)
    return all(b - a == 1 for a, b in zip(sorted_lines, sorted_lines[1:]))


# -----------------------------
# Step 3: classification
# -----------------------------
def check_classification(file_path, lines, coverage_map, student_label):
    file_path = file_path.replace("\\", "/")

    covered_lines = coverage_map.get(file_path, set())

    is_covered = any(line in covered_lines for line in lines)
    actual = "covered" if is_covered else "uncovered"

    return actual == student_label


# -----------------------------
# Step 4: survive check
# -----------------------------
def check_survive(patch_path):
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = os.path.join(tmpdir, BASE_REPO)
        shutil.copytree(BASE_REPO, repo_dir)
        patch_abs_path = os.path.abspath(patch_path)

        # apply patch
        try:
            subprocess.run(
                ["patch", "-p1", "-i", patch_abs_path],
                cwd=repo_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            print(f"Failed to apply patch: {patch_path}")
            return False

        # run pytest in docker
        cmd = f"""
        docker run --rm -v "{repo_dir}:/app" -w /app {DOCKER_IMAGE} \
        sh -c "python -m pip install -e . && pytest tests/"
        """

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                timeout=TIMEOUT,
            )
            print(f"Patch: {patch_path}, Return code: {result.returncode}")
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"Patch: {patch_path} timed out")
            return False


# -----------------------------
# Step 5: distinct check
# -----------------------------
def compute_distinct(patches):
    seen = {}
    result = {}

    for p in patches:
        key_lines = [(p["file"], l) for l in p["lines"]]

        overlap = False
        for k in key_lines:
            if k in seen:
                overlap = True
                result[seen[k]] = False
            else:
                seen[k] = p["name"]

        result[p["name"]] = not overlap

    return result


# -----------------------------
# Main grading
# -----------------------------
def grade():
    coverage_map = get_baseline_coverage()

    rows = []

    for student in os.listdir(SUBMISSIONS_DIR):
        student_path = os.path.join(SUBMISSIONS_DIR, student)
        if not os.path.isdir(student_path):
            continue

        patches = []

        for label in ["covered", "uncovered"]:
            dir_path = os.path.join(student_path, label)
            if not os.path.isdir(dir_path):
                continue

            for fname in os.listdir(dir_path):
                if not fname.endswith(".patch"):
                    continue

                patch_path = os.path.join(dir_path, fname)

                file_path, lines, hunk_count = parse_patch(patch_path)

                patches.append(
                    {
                        "student": student,
                        "name": fname,
                        "path": patch_path,
                        "label": label,
                        "file": file_path,
                        "lines": lines,
                        "hunks": hunk_count,
                    }
                )

        # distinct 계산
        distinct_map = compute_distinct(patches)

        for p in patches:
            classification = check_classification(
                p["file"], p["lines"], coverage_map, p["label"]
            )

            single_hunk = is_single_hunk(p["lines"], p["hunks"])

            survive = check_survive(p["path"])

            distinct = distinct_map.get(p["name"], True)

            rows.append(
                [
                    p["student"],
                    p["name"],
                    "O" if classification else "X",
                    "O" if single_hunk else "X",
                    "O" if survive else "X",
                    "O" if distinct else "X",
                ]
            )

    # CSV 출력
    rows.sort(key=lambda row: (row[0], row[1]))

    with open("result.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "student",
                "patch",
                "classification",
                "single_hunk",
                "survive",
                "distinct_lines",
            ]
        )
        writer.writerows(rows)


if __name__ == "__main__":
    grade()
