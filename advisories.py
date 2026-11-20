#!/usr/bin/env python3
"""No dependency has a published advisory that nobody has judged.

Run from a repository that has build-tools at build-tools/, with osv-scanner
on PATH (install-osv-scanner.sh):

    python3 build-tools/advisories.py --root . [--lockfile PATH ...]

It scans every lockfile git tracks in the repository, and each --lockfile
named: one CI resolved where the repository commits none. osv-scanner runs
with an empty configuration, so only advisories.toml, at the repository's
root, ignores anything. A dune package lock (a dune.lock directory: its
lock.dune and a <name>.<version>.pkg file for each package) is one osv-scanner
cannot match, so each of its packages is asked of OSV's API, in the opam
ecosystem, directly. The run fails on a finding no ignore names, and on an
ignore that matched no finding, so none outlives what it was about:

    [[ignore]]
    id = "RUSTSEC-2023-0071"
    reason = "Why it cannot reach anything this repository ships."

An ignore names a finding by any of its advisories' ids or aliases.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

# The lockfiles osv-scanner scans, by name: those of every language the
# repositories use but OCaml, whose dune.lock is scanned by DUNE_LOCK.
LOCKFILES = {
    "package-lock.json",
    "Cargo.lock",
    "go.mod",
    "uv.lock",
    "packages.lock.json",
    "gradle.lockfile",
    "cabal.project.freeze",
    "Package.resolved",
}


# A dune package lock is the directory holding this file.
DUNE_LOCK = "lock.dune"
OSV = "https://api.osv.dev/v1"


def fail(lines):
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(1)


def read_ignores(root):
    path = root / "advisories.toml"
    if not path.is_file():
        fail([f"{path} is missing. A repository with nothing to ignore has one with no [[ignore]] entries."])
    data = tomllib.loads(path.read_text())
    if set(data) - {"ignore"}:
        fail([f"{path}: unexpected keys {sorted(set(data) - {'ignore'})}; only [[ignore]] entries belong here."])
    ignores = {}
    for entry in data.get("ignore", []):
        if set(entry) != {"id", "reason"} or not all(isinstance(entry[key], str) and entry[key].strip() for key in entry):
            fail([f"{path}: every [[ignore]] has a non-empty id and reason and nothing else: {entry}"])
        if entry["id"] in ignores:
            fail([f"{path}: {entry['id']} is ignored twice."])
        ignores[entry["id"]] = entry["reason"]
    return ignores


def refuse_unversioned_swift_pins(resolved):
    """A pin to a bare revision has no version for an advisory to match: it would pass unseen."""
    for pin in json.loads(resolved.read_text())["pins"]:
        if "version" not in pin["state"]:
            fail([f"{resolved}: {pin['identity']} is pinned to a revision, not a version, so no advisory can match it."])


def dune_packages(lock, tracked):
    """Each package a dune lock pins, as (name, version), from its tracked .pkg files."""
    packages = []
    for pkg in sorted(path for path in tracked if path.parent == lock and path.suffix == ".pkg"):
        versions = [line[len("(version "):-1] for line in pkg.read_text().splitlines()
                    if line.startswith("(version ") and line.endswith(")")]
        if len(versions) != 1:
            fail([f"{pkg}: states {len(versions)} versions, not one."])
        version = versions[0]
        suffix = f".{version}.pkg"
        if not pkg.name.endswith(suffix) or pkg.name == suffix:
            fail([f"{pkg}: states version {version}, and its name is not <package>{suffix}."])
        packages.append((pkg.name[:-len(suffix)], version))
    if not packages:
        fail([f"{lock} pins no package."])
    return packages


def osv(path, body=None):
    request = urllib.request.Request(f"{OSV}/{path}", method="POST" if body else "GET",
                                     data=json.dumps(body).encode() if body else None,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except OSError as error:
        fail([f"OSV's API failed at {path}: {error}"])


def scan_dune_lock(lock, packages):
    """Each finding of a dune lock's packages, as scan gives them, from OSV's API."""
    answers = osv("querybatch", {"queries": [{"package": {"ecosystem": "opam", "name": name}, "version": version}
                                             for name, version in packages]})["results"]
    findings = []
    for (name, version), answer in zip(packages, answers, strict=True):
        if "next_page_token" in answer:
            fail([f"{lock}: OSV's answer for {name} {version} runs past one page."])
        for listed in answer.get("vulns", []):
            advisory = osv(f"vulns/{listed['id']}")
            findings.append((lock, name, version, {advisory["id"], *advisory.get("aliases", [])},
                             [advisory["id"]], advisory.get("summary", "")))
    return findings


def scan(lockfiles, directory):
    """Each finding as (lockfile, package, version, its advisories' ids and aliases, the ids, a summary)."""
    configuration = directory / "empty.toml"
    configuration.write_text("")
    command = ["osv-scanner", "scan", "source", "--format", "json", "--no-call-analysis=go",
               "--config", str(configuration)]
    for lockfile in lockfiles:
        if lockfile.name == "Package.resolved":
            refuse_unversioned_swift_pins(lockfile)
        command += ["--lockfile", str(lockfile)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        fail([f"osv-scanner failed (exit {result.returncode}):", result.stderr])
    findings = []
    for source in json.loads(result.stdout)["results"]:
        lockfile = Path(source["source"]["path"])
        for package in source["packages"]:
            advisories = {advisory["id"]: advisory for advisory in package["vulnerabilities"]}
            for group in package["groups"]:
                names = set(group["ids"])
                for id in group["ids"]:
                    names |= set(advisories[id].get("aliases", []))
                summary = advisories[group["ids"][0]].get("summary", "")
                findings.append((lockfile, package["package"]["name"], package["package"]["version"],
                                 names, sorted(group["ids"]), summary))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True, help="the repository whose lockfiles are scanned")
    parser.add_argument("--lockfile", type=Path, action="append", default=[], dest="lockfiles",
                        help="a lockfile git does not track, resolved for this scan")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    ignores = read_ignores(root)
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True,
                             check=True).stdout.split("\0")
    lockfiles = [root / path for path in tracked if path and Path(path).name in LOCKFILES]
    tracked_paths = [root / path for path in tracked if path]
    dune_locks = [path.parent for path in tracked_paths if path.name == DUNE_LOCK]
    for lockfile in arguments.lockfiles:
        if not lockfile.is_file():
            fail([f"{lockfile} does not exist."])
        lockfiles.append(lockfile.resolve())
    if not lockfiles and not dune_locks:
        fail([f"{root} has no lockfile to scan."])
    for lockfile in lockfiles + dune_locks:
        print(f"scanning {lockfile.relative_to(root) if lockfile.is_relative_to(root) else lockfile}")

    findings = []
    if lockfiles:
        with tempfile.TemporaryDirectory() as scratch:
            findings += scan(lockfiles, Path(scratch))
    for lock in dune_locks:
        findings += scan_dune_lock(lock, dune_packages(lock, tracked_paths))

    problems = []
    matched = set()
    for lockfile, name, version, names, ids, summary in findings:
        named = names & set(ignores)
        if named:
            matched |= named
            print(f"ignored {name} {version}: {', '.join(ids)} ({', '.join(sorted(named))} in advisories.toml)")
        else:
            problems.append(f"  {lockfile.relative_to(root) if lockfile.is_relative_to(root) else lockfile}: "
                            f"{name} {version}: {', '.join(ids)} {summary}")
    stale = sorted(set(ignores) - matched)
    lines = []
    if problems:
        lines += ["Advisories no ignore in advisories.toml names (move the dependency past them, or judge"
                  " each and ignore it with its reason):", *problems]
    if stale:
        lines += ["Ignores in advisories.toml that matched no finding (delete them):", *(f"  {id}" for id in stale)]
    if lines:
        fail(lines)
    print(f"{len(lockfiles) + len(dune_locks)} lockfiles, {len(findings)} findings, each ignored with a reason")


if __name__ == "__main__":
    main()
