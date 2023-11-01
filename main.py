import os
import sys
from git import Repo, exc
from inspect import getsourcefile
import xml.etree.ElementTree as ET


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
    if benchmarks is None or benchmarks == "" or benchmarks == 'all':
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

    print("Executing SHOT located at: {0}".format(shot_executable))
    # Changes the working directory to the shot folder
    os.chdir(os.path.dirname(shot_executable))

    # Run the benchmarks
    for benchmark in benchmarks_paths:
        print("Running benchmark: {0}".format(benchmark))
        benchmark_name = os.path.basename(benchmark).split(".")[0]
        os.system("{0} {1} --trc {2}.trc".format(shot_executable, benchmark, benchmark_name))

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

        # We parse the osrl files and extract the needed information.
    bench_times = {}
    statuses = {}
    for benchmark in benchmark_names:
        tree = ET.parse('{0}/{1}.osrl'.format(benchmark_dest, benchmark))
        root = tree.getroot()
        times = {}
        for element in root.iter('{os.optimizationservices.org}time'):
            times[element.attrib['type']] = element.text
        bench_times[benchmark] = times

        statuses = {}
        for element in root.iter('{os.optimizationservices.org}status'):
            statuses['status'] = element.attrib['type']

        for element in root.iter('{os.optimizationservices.org}substatus'):
            statuses['substatus'] = element.attrib['type']

    # We generate the Markdown table
    headers = ["Benchmark", "Total Time", "Status", "Substatus"]
    data = []
    for benchmark in benchmark_names:
        data.append(
            [
                benchmark,
                bench_times[benchmark]["total"],
                statuses[benchmark]["status"],
                statuses[benchmark]["substatus"]
            ]
        )

    markdown_table = generate_markdown_table(headers, data)
    # We write the Markdown table to the output file
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as fh:
        print('# Benchmark results', file=fh)
        print(markdown_table, file=fh)


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
