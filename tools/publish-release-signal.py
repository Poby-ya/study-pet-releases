"""Validate both official installers before notifying running desktop apps."""
import datetime
import hashlib
import json
import os
import re
import urllib.request
import urllib.parse

REPO = "Poby-ya/study-pet-releases"
DATABASE = "https://poby-study-room-default-rtdb.asia-southeast1.firebasedatabase.app"


def fetch(url, token=None):
    headers = {"User-Agent": "StudyPet-release-publisher"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return response.read()


def main():
    api = "https://api.github.com/repos/" + REPO + "/releases/latest"
    github_token = os.environ.get("GH_TOKEN")
    release = json.loads(fetch(api, github_token))
    tag = release["tag_name"]
    requested = os.environ.get("RELEASE_TAG", tag)
    if requested != tag or release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Only the current stable release can be announced")
    for name in ["StudyPet.exe", "StudyPet-mac.zip", "StudyPet-mac.zip.sha256", "install-mac.sh"]:
        matches = [asset for asset in release["assets"] if asset["name"] == name]
        if len(matches) != 1:
            raise ValueError("Missing or duplicate asset " + name)
        asset = matches[0]
        url = "https://github.com/" + REPO + "/releases/download/" + tag + "/" + name
        if asset["browser_download_url"] != url or not 0 < asset["size"] <= 100_000_000:
            raise ValueError("Invalid asset " + name)
        data = fetch(url)
        if len(data) != asset["size"] or "sha256:" + hashlib.sha256(data).hexdigest() != asset.get("digest"):
            raise ValueError("Size or digest mismatch for " + name)
    if json.loads(fetch(api, github_token))["tag_name"] != tag:
        raise ValueError("The latest release changed during verification")
    credentials = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": os.environ["FIREBASE_RELEASE_REFRESH_TOKEN"]}).encode()
    authentication = urllib.request.Request("https://securetoken.googleapis.com/v1/token?key=" + os.environ["FIREBASE_RELEASE_API_KEY"], credentials, {"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(authentication, timeout=30) as response:
        token = json.load(response)["id_token"]
    request = urllib.request.Request(
        DATABASE + "/releaseChannel/stable.json?auth=" + urllib.parse.quote(token, safe=""), json.dumps(tag).encode(),
        {"Content-Type": "application/json"}, method="PUT")
    print("Signal write started " + datetime.datetime.now(datetime.timezone.utc).isoformat(), flush=True)
    with urllib.request.urlopen(request, timeout=30) as response:
        if json.load(response) != tag:
            raise ValueError("The release signal was not acknowledged")
    print("Validated and announced " + tag)


if __name__ == "__main__":
    main()
