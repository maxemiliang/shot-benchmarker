import os
import sys
from git import Repo, exc
from inspect import getsourcefile


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
        os.system("{0} {1}".format(shot_executable, benchmark))

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


if __name__ == "__main__":
    main()
