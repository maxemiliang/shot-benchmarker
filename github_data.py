import os
import sys


class GithubData:
    gh_type = os.environ.get("GITHUB_REF_TYPE")
    short_name = os.environ.get("GITHUB_REF_NAME")
    run_number = os.environ.get("GITHUB_RUN_NUMBER")

    def __init__(self):
        if self.gh_type is None or self.run_number is None or self.short_name is None:
            print("GH Actions environment not detected exiting")
            sys.exit(1)

    def construct_valid_data(self, sha: str):
        path = os.path.normpath(
            "{0}/{1}/{2}".format(self.gh_type, self.short_name, sha))
        return os.path.join(path, '')
