import os
import sys

from keystoneauth1 import session
from keystoneauth1.identity import v3
import os
import swiftclient
from swiftclient.multithreading import OutputManager
from swiftclient.service import SwiftError, SwiftService, SwiftUploadObject

from github_data import GithubData

_authurl = os.environ['OS_AUTH_URL']
_auth_version = os.environ['OS_IDENTITY_API_VERSION']
_user = os.environ['OS_USERNAME']
_key = os.environ['OS_PASSWORD']
_os_options = {
    'user_domain_name': os.environ['OS_USER_DOMAIN_NAME'],
    'project_domain_name': os.environ['OS_USER_DOMAIN_NAME'],
    'project_name': os.environ['OS_PROJECT_NAME']
}


class Allas:
    gh_data = GithubData()

    def __init(self, bucket_name=None):
        if bucket_name is not None:
            self.bucket_name = bucket_name
        self.conn = swiftclient.Connection(
            authurl=_authurl,
            user=_user,
            key=_key,
            os_options=_os_options,
            auth_version=_auth_version
        )
        # We check the connection here.
        try:
            _, containers = self.conn.get_account()
            self.containers = containers
        except swiftclient.ClientException:
            print("Error getting the acccount, check your swift credentials")
            sys.exit(1)

    # Creates the bucket if it does not exist.
    def create_bucket(self):
        # We create the container if it does not exist.
        for container in self.containers:
            if container['name'] == self.bucket_name:
                # We can break here, this means the else block will not be executed.
                break
        else:
            self.conn.put_container(self.bucket_name)

    # Uploads the file to the correct place.
    def upload_file(self, file):
        path = self.gh_data.construct_valid_data()
        if not path:
            return False
        path = "{0}data.json".format(path)
        with open(file, "r") as f:
            print("Uploading file {0}".format(file))
            self.conn.put_object(
                self.bucket_name,
                path,
                contents=f.read(),
                content_type="application/json"
            )
