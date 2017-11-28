from http import HTTPStatus
import logging

from server.request import Request
from utils.common import get_latest_release


class UpdateRequest(Request):
    def __init__(self, request_json):
        super().__init__(request_json)
        self.log = logging.getLogger(__name__)

    def package_transformation(self, distro, release, packages):
        # perform package transformation
        packages_transformed = self.packages_transformed = [package[0] for package in self.database.transform_packages(distro, release, self.release, " ".join(packages))]
        self.log.debug("transformed packages {}".format(self.packages_transformed))
        return packages_transformed

    def run(self):
        for needed_value in ["distro", "version", "target", "subtarget"]:
            if not needed_value in self.request_json:
                self.response_status = HTTPStatus.BAD_REQUEST
                return self.respond()

        bad_request = self.check_bad_request()
        if bad_request:
            return bad_request

        # check target for old version
        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        bad_packages = self.check_bad_packages()
        if bad_packages:
            return bad_packages

        self.installed_release = self.release
        if self.installed_release  == "snapshot":
            self.release = "snapshot"
            self.response_json["version"] = "SNAPSHOT"
        else:
            self.release = get_latest_release(self.distro)
            if not self.release == self.installed_release:
                self.response_json["version"] = self.release

        # check target for new version
        bad_target = self.check_bad_target()
        if bad_target:
            return bad_target

        bad_packages = self.check_bad_packages()
        if bad_packages:
            return bad_packages

        if "packages" in self.request_json:
            self.log.debug(self.request_json["packages"])
            self.packages_installed = self.request_json["packages"]
            self.response_json["packages"] = list(self.packages_installed.keys())
            if "version" in self.response_json:
                self.packages_transformed = self.package_transformation(self.distro, self.installed_release, self.packages_installed)
                self.response_json["packages"] = self.packages_transformed

            if "upgrade_packages" in self.request_json or "version" in self.response_json:
                if self.request_json["upgrade_packages"] is 1 or "version" in self.response_json:
                    packages_updates = self.database.packages_updates(self.distro, self.release, self.target, self.subtarget, self.packages_installed)
                    if packages_updates:
                        self.response_json["upgrades"] = {}
                        for name, version, version_installed in packages_updates:
                            if name in self.response_json["packages"]:
                                self.response_json["upgrades"][name] = [version, version_installed]

        if "version" in self.response_json or "upgrades" in self.response_json:
            self.response_status = HTTPStatus.OK # 200
        else:
            self.response_status = HTTPStatus.NO_CONTENT # 204

        return self.respond()
