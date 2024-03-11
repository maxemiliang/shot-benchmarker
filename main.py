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
from github_data import GithubData
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

    comparison_data = []
    for benchmark in benchmark_names:
        comparison_data.append(
            {
                "name": benchmark,
                "time": bench_times[benchmark]["Total"],
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
        handle_comparison(comparison_data)


def handle_comparison(comparison_data):
    pass


def handle_upload(data_json):
    gh_api = GithubAPI()
    allas = Allas()
    # Create the bucket
    allas.create_bucket()
    current_commit = gh_api.get_commit_from_head(0)
    allas.upload_file(current_commit.sha, data_json)


# Handles generating the Markdown table, used in GH Actions Job Summary.
def generate_markdown_table(headers, data):
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
