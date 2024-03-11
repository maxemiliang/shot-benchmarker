from git import Repo, exc


# Checks if a path is a git repo
def is_git_repo(path):
    try:
        _ = Repo(path).git_dir
        return True
    except exc.InvalidGitRepositoryError:
        return False


def get_last_completed_run(repo):
    resp = repo.get_workflow_runs()
    print(resp)
