import os
import sys
import json
from collections import defaultdict

from git import Repo, exc
from inspect import getsourcefile
import xml.etree.ElementTree as ET

from keystoneauth1 import session
from keystoneauth1.identity import v3
import os
import swiftclient
from swiftclient.multithreading import OutputManager
from swiftclient.service import SwiftError, SwiftService, SwiftUploadObject

_authurl = os.environ['OS_AUTH_URL']
_auth_version = os.environ['OS_IDENTITY_API_VERSION']
_user = os.environ['OS_USERNAME']
_key = os.environ['OS_PASSWORD']
_os_options = {
    'user_domain_name': os.environ['OS_USER_DOMAIN_NAME'],
    'project_domain_name': os.environ['OS_USER_DOMAIN_NAME'],
    'project_name': os.environ['OS_PROJECT_NAME']
}

conn = swiftclient.Connection(
    authurl=_authurl,
    user=_user,
    key=_key,
    os_options=_os_options,
    auth_version=_auth_version
)

bucket_name = "shot-benchmarks"


# Checks if a path is a git repo
def is_git_repo(path):
    try:
        _ = Repo(path).git_dir
        return True
    except exc.InvalidGitRepositoryError:
        return False


# Creates the bucket if it does not exist.
def create_bucket(containers):
    # We create the container if it does not exist.
    for container in containers:
        if container['name'] == bucket_name:
            # We can break here, this means the else block will not be executed.
            break
    else:
        conn.put_container(bucket_name)


def get_git_object():
    gh_type = os.environ.get("GITHUB_REF_TYPE")
    short_name = os.environ.get("GITHUB_REF_NAME")
    run_number = os.environ.get("GITHUB_RUN_NUMBER")
    return {
        "type": gh_type,
        "short_name": short_name,
        "run_number": run_number
    }


def construct_valid_path(git_object):
    if git_object["type"] is None or git_object["short_name"] is None or git_object["run_number"] is None:
        print("Unable to get the current branch/ref name, wont upload the file")
        return False

    path = os.path.normpath(
        "{0}/{1}/{2}".format(git_object["type"], git_object["short_name"], git_object["run_number"]))
    return os.path.join(path, '')


# Uploads the file to the correct place.
def upload_file(file):
    git_object = get_git_object()
    if not git_object:
        return False
    path = construct_valid_path(git_object)
    if not path:
        return False
    path = "{0}data.json".format(path)
    with open(file, "r") as f:
        print("Uploading file {0}".format(file))
        conn.put_object(
            bucket_name,
            path,
            contents=f.read(),
            content_type="application/json"
        )


def main():
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
    # We check the connection here.
    try:
        resp_headers, containers = conn.get_account()
    except swiftclient.ClientException:
        print("Error getting the acccount, check your swift credentials")
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

    # Create the bucket
    create_bucket(containers)

    upload_file(data_json)


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
