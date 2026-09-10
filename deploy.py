from pathlib import Path

from pyinfra import host
from pyinfra.facts.deb import DebArch
from pyinfra.facts.server import OsRelease, User
from pyinfra.operations import apt, files, server, systemd

from vars import *

server.hostname(
  name = "Set the hostname",
  hostname = HOSTNAME,
)

server.timezone(
  name = "Set the timezone",
  timezone = TIMEZONE,
)

for (group, gid, system) in [("docker", None, True), (USER, 1000, False)]:
  server.group(
    name = f"Create group: {group}",
    group = group,
    gid = gid,
    system = system,
  )

files.put(
  name = f"Add {USER} group to sudoers",
  src = StringIO(f"%{USER} ALL=(ALL) NOPASSWD:ALL"),
  dest = f"/etc/sudoers.d/{USER}",
  user = "root",
  group = "root",
  mode = "440",
)

server.user(
  name = f"Create user: {USER}",
  uid = 1000,
  user = USER,
  group = USER,
  groups = ["docker"],
  append = True,
  shell = "/bin/bash",
  ensure_home = True,
  create_home = True,
  public_keys = PUBLIC_KEYS,
)

if Path("config/motd").exists():
  files.put(
      name = "Set message of the day",
      src = "config/motd",
      dest = "/etc/motd",
      mode = "644",
  )

server.shell(
  name = "Create swap file",
  commands = [f"dd if=/dev/zero of={SWAP_FILE} bs=1M count={SWAP_SIZE_MB}"],
  not_if = f"test -f {SWAP_FILE}",
)

files.file(
  name = "Secure swap file",
  path = SWAP_FILE,
  user = "root",
  group = "root",
  mode = "0600"
)

server.shell(
  name = "Format swap file",
  commands = [f"mkswap {SWAP_FILE}"],
  not_if = f"blkid {SWAP_FILE} | grep -q swap",
)

server.shell(
  name = "Enable swap",
  commands = [f"swapon {SWAP_FILE}"],
  not_if = f"grep -q {SWAP_FILE} /proc/swaps",
)

files.line(
  name = "Add swap to fstab",
  path = "/etc/fstab",
  line = f"{SWAP_FILE} none swap sw 0 0",
)

apt.packages(
  name = "Remove old Docker packages",
  packages = [
    "docker.io",
    "docker-compose",
    "docker-doc",
    "docker-buildx",
    "podman-docker",
  ],
  present = False,
  purge = True,
)

apt.dist_upgrade(
  name="Upgrade all packages",
  auto_remove=True,
)

apt.key(
  name = "Add Docker GPG key",
  src = "https://download.docker.com/linux/debian/gpg",
  dest = "docker.gpg",
)

codename = host.get_fact(OsRelease).get("version_codename")
architecture = host.get_fact(DebArch)

apt.sources_file(
  name = "Add Docker apt repository",
  filename = "docker",
  types = ["deb"],
  uris = ["https://download.docker.com/linux/debian"],
  suites = [codename],
  components = ["stable"],
  architectures = [architecture],
  signed_by = "/etc/apt/keyrings/docker.gpg",
)

apt.packages(
  name = "Install Docker packages",
  update = True,
  packages = [
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-buildx-plugin",
    "docker-compose-plugin",
  ],
  latest = True,
)

if Path("config/docker.json").exists():
  files.put(
    name = "Copy in Docker config",
    src = "config/docker.json",
    dest = "/etc/docker/daemon.json",
    user = "root",
    group = "root",
    mode = "644",
  )

systemd.service(
  name = "Ensure Docker service is started",
  service = "docker",
  enabled = True,
  running = True,
)

user = host.get_fact(User)

system.user(
  name = f"Remove bootstrap user: {user}",
  user = user,
  present = False,
)
