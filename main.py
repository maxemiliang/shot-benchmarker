import os
import sys
from git import Repo, exc
import xml.etree.ElementTree as ET
import json


# Checks if a path is a git repo
def is_git_repo(path):
    try:
        _ = Repo(path).git_dir
        return True
    except exc.InvalidGitRepositoryError:
        return False


def main():
    benchmark_folder = os.environ.get("INPUT_BENCHMARK_FOLDER")
    benchmark_type = os.environ.get("INPUT_BENCHMARK_TYPE")
    benchmarks = os.environ.get("INPUT_BENCHMARKS")
    shot_executable = os.environ.get("INPUT_SHOT_EXECUTABLE")
    if benchmark_folder is None or benchmark_type is None or shot_executable is None:
        print("Missing required input")
        sys.exit(1)
    benchmark_files = []
    if benchmarks is None or benchmarks == "":
        benchmarks = "all"
    else:
        benchmarks = benchmarks.split(",")
        benchmark_files = ["{0}.{1}".format(benchmark, benchmark_type) for benchmark in benchmarks]
    # Cloning the repo to a subfolder of the current working directory
    repo_dir = os.path.join(os.getcwd(), "SHOT_benchmark_problems")
    if os.path.isdir(repo_dir) and is_git_repo(repo_dir):
        print("Repo already exists")
        repo = Repo(repo_dir)
        repo.git.checkout("main")
        repo.git.pull()
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

    # Run the benchmarks
    for benchmark in benchmarks_paths:
        print("Running benchmark: {0}".format(benchmark))
        os.system("{0} {1}".format(shot_executable, benchmark))

    # Parse the XML files (osrl)
    bench_times = {}
    for benchmark in benchmarks:
        tree = ET.parse('{0}.osrl'.format(benchmark))
        root = tree.getroot()
        times = {}
        for element in root.iter('{os.optimizationservices.org}time'):
            times[element.attrib['type']] = element.text
        bench_times[benchmark] = times

    # Write the results to a JSON file
    with open('results.json', 'w') as fp:
        json.dump(bench_times, fp)


if __name__ == "__main__":
    main()
