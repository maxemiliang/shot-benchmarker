import os
import sys

from github import Github, GithubException
from github.Auth import Auth

from github_data import GithubData


class GithubAPI:
    gh_data = GithubData()

    def __init(self):
        # Setup GitHub auth
        self.auth = Auth.Token(os.environ.get("GITHUB_TOKEN"))
        self.g = Github(auth=auth)
        try:
            self.repo = self.g.get_repo("coin-or/SHOT")
        except GithubException:
            print("Error connecting to GitHub")

    # Should only be called when the run type is branch.
    def get_latest_completed_run(self):
        if self.gh_data.gh_type != "branch":
            raise RuntimeError("Can only be called when the action is run in a branch")
        resp = self.repo.get_workflow_runs(status="completed", branch=self.gh_data.short_name)
        for res in resp:
            print(res)
