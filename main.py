from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from inspect import getsourcefile

from git import Repo

from allas import Allas
from github_api import GithubAPI
from utils import is_git_repo


def main():
    parser = argparse.ArgumentParser(
        prog="Shot benchmarker",
        description="Used to benchmark the SHOT program"
    )
    parser.add_argument("-c", "--compare", action="store_true")
    parser.add_argument("-s", "--store-result", action="store_true")
    args = parser.parse_args()

    benchmark_folder = os.environ.get("INPUT_BENCHMARK_FOLDER")
    benchmark_type = os.environ.get("INPUT_BENCHMARK_TYPE")
    benchmarks = os.environ.get("INPUT_BENCHMARKS")
    shot_executable = os.environ.get("INPUT_SHOT_EXECUTABLE")
    is_ci = os.environ.get("CI") is not None
    if benchmark_folder is None or benchmark_type is None or shot_executable is None:
        print("Missing required input")
        sys.exit(1)
    if not os.path.isfile(shot_executable):
        print("SHOT executable does not exist")
        sys.exit(1)

    if benchmarks is None or benchmarks == "" or benchmarks == 'all':
        benchmarks = "all"
    else:
        benchmarks = benchmarks.split(",")
        benchmark_files = ["{0}.{1}".format(benchmark, benchmark_type) for benchmark in benchmarks]
    # Cloning the repo to a subfolder of the current working directory
    repo_dir = os.path.join(os.getcwd(), "SHOT_benchmark_problems")
    if os.path.isdir(repo_dir) and is_git_repo(repo_dir):
        print("Repo already exists")
        bench_repo = Repo(repo_dir)
        bench_repo.git.checkout("main")
        bench_repo.git.pull()
    else:
        print("Cloning repo")
        Repo.clone_from("https://github.com/andreaslundell/SHOT_benchmark_problems.git", repo_dir)

    # Check if the benchmark folder exists
    if not os.path.isdir(os.path.join(repo_dir, benchmark_folder)):
        print("Benchmark folder does not exist")
        sys.exit(1)
    # Check if the benchmark type exists
    if not os.path.isdir(os.path.join(repo_dir, benchmark_folder, benchmark_type)):
        print("Benchmark type does not exist")
        sys.exit(1)
    # Check if the benchmark exists
    benchmarks_paths = []
    if benchmarks != "all":
        for benchmark in benchmark_files:
            if not os.path.isfile(os.path.join(repo_dir, benchmark_folder, benchmark_type, benchmark)):
                print("Benchmark does not exist")
                sys.exit(1)
            else:
                benchmarks_paths.append(os.path.join(repo_dir, benchmark_folder, benchmark_type, benchmark))
    else:
        benchmarks_paths = [os.path.join(repo_dir, benchmark_folder, benchmark_type, benchmark) for benchmark in
                            os.listdir(os.path.join(repo_dir, benchmark_folder, benchmark_type))]

    # Print the benchmarks
    print("Selected benchmarks:")
    for benchmark in benchmarks_paths:
        print(benchmark)

    print("Executing SHOT located at: {0}".format(shot_executable))
    # Changes the working directory to the shot folder
    os.chdir(os.path.dirname(shot_executable))

    # Run the benchmarks
    for benchmark in benchmarks_paths:
        print("Running benchmark: {0}".format(benchmark))
        benchmark_name = os.path.basename(benchmark).split(".")[0]
        os.system("{0} {1} --trc {2}.trc --log {2}.log".format(shot_executable, benchmark, benchmark_name))

    if is_ci:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print("benchmarks={0}".format(",".join(benchmarks)), file=fh)

    # Move the osrl files to a separate folder.
    current_path = os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))
    benchmark_dest = "{0}/benchmarks".format(current_path)
    os.makedirs(benchmark_dest, exist_ok=True)
    benchmark_names = []
    for benchmark in benchmarks_paths:
        benchmark_names.append(os.path.basename(benchmark).split(".")[0])

    for benchmark in benchmark_names:
        os.rename("{0}/{1}.osrl".format(os.path.dirname(shot_executable), benchmark),
                  "{0}/{1}.osrl".format(benchmark_dest, benchmark))
        os.rename("{0}/{1}.trc".format(os.path.dirname(shot_executable), benchmark),
                  "{0}/{1}.trc".format(benchmark_dest, benchmark))
        os.rename("{0}/{1}.log".format(os.path.dirname(shot_executable), benchmark),
                  "{0}/{1}.log".format(benchmark_dest, benchmark))

        # We parse the osrl files and extract the needed information.
    bench_times = {}
    statuses = defaultdict(lambda: {"status": "", "substatus": ""})
    for benchmark in benchmark_names:
        tree = ET.parse('{0}/{1}.osrl'.format(benchmark_dest, benchmark))
        root = tree.getroot()
        times = {}
        for element in root.iter('{os.optimizationservices.org}time'):
            times[element.attrib['type']] = element.text
        bench_times[benchmark] = times

        for element in root.iter('{os.optimizationservices.org}status'):
            statuses[benchmark]['status'] = element.attrib['type']

        for element in root.iter('{os.optimizationservices.org}substatus'):
            statuses[benchmark]['substatus'] = element.attrib['type']

    # We generate the Markdown table
    headers = ["Benchmark", "Total Time", "Status", "Substatus"]
    data = []
    for benchmark in benchmark_names:
        data.append(
            [
                benchmark,
                bench_times[benchmark]["Total"],
                statuses[benchmark]["status"],
                statuses[benchmark]["substatus"]
            ]
        )

    markdown_table = generate_markdown_table(headers, data)
    # We write the Markdown table to the output file
    if is_ci:
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as fh:
            print('# Benchmark results', file=fh)
            print(markdown_table, file=fh)
    else:
        print(markdown_table)

    comparison_data = []
    for benchmark in benchmark_names:
        try:
            time = float(bench_times[benchmark]["Total"])
        except ValueError as e:
            time = bench_times[benchmark]["Total"]
            print("Error converting runtime to float: {0}".format(e))

        comparison_data.append(
            {
                "name": benchmark,
                "time": time,
                "status": statuses[benchmark]["status"],
                "substatus": statuses[benchmark]["substatus"]
            }
        )

    # Finally write the data to a file, and prepare it for upload
    with open('data.json', 'w') as json_file:
        json.dump(comparison_data, json_file, sort_keys=True, indent=4)

    # Move the file to the benchmark destination.
    data_json = "{0}/data.json".format(benchmark_dest)
    os.rename("data.json", data_json)

    if args.store_result:
        handle_upload(data_json)

    if args.compare:
        changes = prepare_comparison(comparison_data)
        if changes is not None:
            headers = ["Benchmark", "Status changed", "New status", "Old status", "Substatus changed", "New substatus",
                       "Old substatus", "Time changed", "Time change", "New time", "Old time"]
            markdown_data = []
            for change in changes.keys():
                markdown_data.append([
                    change,
                    str(changes[change].get("status_change", "")),
                    changes[change].get("current", {}).get("status", ""),
                    changes[change].get("previous", {}).get("status", ""),
                    str(changes[change].get("substatus_change", "")),
                    changes[change].get("current", {}).get("substatus", ""),
                    changes[change].get("previous", {}).get("substatus", ""),
                    str(changes[change].get("time_changed", "")),
                    changes[change].get("time_change", ""),
                    changes[change].get("current", {}).get("time", ""),
                    changes[change].get("previous", {}).get("time", ""),
                ])
            change_table = generate_markdown_table(headers, markdown_data)
            if is_ci:
                with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as fh:
                    print('# Comparison to previous commit', file=fh)
                    print(change_table, file=fh)
            else:
                print(change_table)

            # Finally write the data to a file, and prepare it for upload
            with open('comparison.json', 'w') as json_file:
                json.dump(changes, json_file, sort_keys=True, indent=4)

            # Move the file to the benchmark destination.
            data_json = "{0}/comparison.json".format(benchmark_dest)
            os.rename("comparison.json", data_json)

    else:
        print("Failed to get changes or no changes detected, see log for more information")


def get_comparison_dict(comparison_data: list, previous_result: list) -> dict | None:
    """
    Matches the current + previous data and returns a comparison array, that can be used by other functions.
    """
    comparison_by_keys = {result["name"]: result for result in comparison_data}
    previous_by_keys = {result["name"]: result for result in previous_result}

    matches = set(comparison_by_keys.keys()).intersection(previous_by_keys.keys())

    if not matches:
        print("No common benchmarks found between this run and the previous run")
        return None

    all_changes = {}

    for match in matches:
        current = comparison_by_keys[match]
        previous = previous_by_keys[match]
        changes = {}
        # We check if the key exists, just so we don't get false positives like "" != "" = True
        if "status" in current and "status" in previous:
            changes["status_change"] = current.get("status", "") != previous.get("status", "")

        if "substatus" in current and "substatus" in previous:
            changes["substatus_change"] = current.get("substatus", "") != previous.get("substatus", "")

        if "time" in current and "time" in previous:
            changes["time_changed"] = current["time"] != previous["time"]
            # Here we do not use any defaults, as to once again not get false positives, if the value somehow
            # does not pass
            try:
                changes["time_change"] = float(current["time"]) - float(previous["time"])
            except ValueError as e:
                print("Error parsing time: {0}".format(e))

        if len(changes) == 0:
            continue

        all_changes[match] = {
            "changes": changes,
            "current": current,
            "previous": previous
        }

    if len(all_changes) == 0:
        return None

    return all_changes


def prepare_comparison(comparison_data: list) -> dict | None:
    """
    Handles checking if there is a previous commit to compare, then downloads the file and reads in its contents.
    continues on to comparison if this works.
    """
    gh_api = GithubAPI()
    allas = Allas()
    previous_commit = gh_api.get_commit_from_head(1)
    if previous_commit is None:
        print("No previous commit found, exiting comparison")
        return None

    downloaded_file_path = allas.download_file(previous_commit.sha, "{0}.json".format(previous_commit.sha))
    if downloaded_file_path is None:
        print("No comparison file found in Allas, exiting comparison")
        return None

    try:
        with open(downloaded_file_path, "r") as file:
            file_contents = json.load(file)
            return get_comparison_dict(comparison_data, file_contents)
    except OSError as e:
        print("Error opening temporary file: {0}".format(e))
        return None


def handle_upload(data_json):
    """
    Uploads the passed file to Allas
    """
    gh_api = GithubAPI()
    allas = Allas()
    # Create the bucket
    allas.create_bucket()
    current_commit = gh_api.get_commit_from_head(0)
    allas.upload_file(current_commit.sha, data_json)


def generate_markdown_table(headers, data):
    """
    Handles generating the Markdown table, used in GH Actions Job Summary.
    """
    # Create the header row
    header_row = "| " + " | ".join(headers) + " |"
    # Create the separator row
    separator_row = "| " + " | ".join(["---" for _ in headers]) + " |"
    # Create the data rows
    data_rows = []
    for row in data:
        data_rows.append("| " + " | ".join(map(str, row)) + " |")

    # Combine all parts of the table
    markdown_table = [header_row, separator_row] + data_rows

    # Return the table as a string
    return "\n".join(markdown_table)


if __name__ == "__main__":
    main()
