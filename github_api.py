import os
import sys
from github import Github, GithubException, Auth
from github.Commit import Commit

from github_data import GithubData


class GithubAPI:
    gh_data = GithubData()

    def __init__(self):
        # Setup GitHub auth
        self.auth = Auth.Token(os.environ.get("GITHUB_TOKEN"))
        self.g = Github(auth=self.auth)
        try:
            self.repo = self.g.get_repo("coin-or/SHOT")
        except GithubException:
            print("Error connecting to GitHub")
            sys.exit(1)

    def get_commit_from_head(self, i: int) -> Commit | None:
        """
        Handles getting the commit from head (so e.g. i = 1 gets the previous commit)
        :param i: The commit to get from head, backwards.
        :return Commit | None:
        """
        if self.gh_data.gh_type != "branch":
            raise RuntimeError("Can only be called when the action is run in a branch")
        commits = self.repo.get_commits(sha=self.gh_data.short_name)
        if commits.totalCount < i + 1:
            return None
        return commits[i]
