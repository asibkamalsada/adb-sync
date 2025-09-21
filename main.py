import os
import re
import time
import shutil
import uuid
from datetime import datetime

from tqdm import tqdm
from subprocess import run
from sys import stdout, stderr

from cloup import command, option, option_group, argument
from cloup.constraints import mutually_exclusive


class AdbSync:
    def __init__(
        self, device: str, adb: str, copy_newer: bool, local: str, remote: str
    ):
        self.device = device
        """device identifier used by adb"""
        self.adb = adb
        """path to adb executable"""
        self.copy_newer = copy_newer
        """
        Only copy files that are newer. 
        If set to false, no overwriting is done at all.
        """
        self.local = local
        """
        Path to local folder.
        
        For pull, this will be the root folder since remote paths are going to be fully qualified.
        
        Push is not implemented yet.
        """
        self.remote = remote
        """
        Path to remote folder.
        
        Not implemented. Currently for pull /sdcard/ is pulled
        """

        self.successes: int | None = None
        self.errors: int | None = None
        self.skipped: list[str] = []
        self.overwritten: int | None = None

    @property
    def device_switch(self):
        return ["-s", self.device] if self.device else []

    def pull(self) -> None:
        remote_folders_str = run(
            [self.adb] + self.device_switch + ["shell", "ls", "-d", "/sdcard/*"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        remote_folders = re.split(r"[\t\n]", remote_folders_str.stdout)

        remote_folders.remove("")
        remote_folders.remove("/sdcard/Android")
        remote_folders.append("/sdcard/Android/media/com.whatsapp")
        # remote_folders.append("/sdcard/Android/data/com.simplescan.scanner")

        print(remote_folders)

        for source in remote_folders:
            skipped = self.pull_folder(source)

            with open(
                os.path.join(
                    os.path.dirname(__file__),
                    "skipped",
                    f"skipped-{format(datetime.now(), '%Y%m%d%H%M%S%f')}-{source}-{uuid.uuid4()}.csv",
                ),
                "w+",
                encoding="utf8",
            ) as f:
                for line in skipped:
                    f.write(f"{line}\n")

    def pull_folder(self, source: str) -> list[str]:
        remote_files_str = run(
            [self.adb] + self.device_switch + ["shell", "find", source, "-type", "f"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        remote_files = remote_files_str.stdout.split("\n")
        self.successes = 0
        self.errors = 0
        self.skipped: list[str] = []
        self.overwritten = 0
        start = time.time()
        with tqdm(bar_format="{desc}") as desc_bar:
            for remote_file in (pbar := tqdm(remote_files)):
                if (
                    remote_file
                    and "cache" not in remote_file.lower()
                    and ".thumbnails" not in remote_file.lower()
                    and ".mcrypt1" not in remote_file.lower()
                    and ".trashed" not in remote_file.lower()
                ):
                    desc_bar.set_description(remote_file)
                    self.pull_file(remote_file)
                else:
                    self.skipped.append(remote_file)
        print(
            f"copied {source}: {self.successes} successes and {self.errors} errors in {time.time() - start}s "
            f"(skipped {len(self.skipped)}, overwritten {self.overwritten})"
        )

        skipped = [x for x in self.skipped]

        self.successes = None
        self.errors = None
        self.skipped = []
        self.overwritten = None

        return skipped

    def pull_file(self, remote_file):
        remote_parts = [
            re.sub(r'[:*?"<>|]', "-", part) for part in remote_file.split("/")
        ]
        local_file = os.path.join(
            self.local,
            *remote_parts,
        )
        # print_statusline(local_file)
        # local_file_path = os.path.dirname(local_file)
        overwrite = False
        if self.copy_newer and os.path.exists(local_file):
            local_time = int(os.path.getmtime(local_file))
            check_time = run(
                [self.adb]
                + self.device_switch
                + ["shell", "stat", remote_file, "-c", "%.9Y"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            try:
                remote_time = int(check_time.stdout)
            except ValueError:
                overwrite = False
            else:
                overwrite = remote_time - local_time > -100
        if not os.path.exists(local_file) or overwrite:
            # print(f"\ncopied {remote_file}")
            # print(f"{local_file} does not exist")
            os.makedirs(os.path.dirname(local_file), exist_ok=True)

            pull_process = run(
                [self.adb]
                + self.device_switch
                + ["pull", "-a", "-p", remote_file, local_file],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            msg = pull_process.stdout
            if msg and "adb: error:" in msg:
                print(pull_process.stdout, file=stderr, end="")
                self.errors += 1
            else:
                self.successes += 1
                self.overwritten += 1 if overwrite else 0
        else:
            self.skipped.append(remote_file)

    def push(self):
        raise NotImplementedError("Push is not supported yet.")


def print_statusline(msg: str, newline: bool = False):
    """
    Unused
    """
    terminal_width = shutil.get_terminal_size().columns

    last_msg_length = (
        len(print_statusline.last_msg) if hasattr(print_statusline, "last_msg") else 0
    )
    print(" " * last_msg_length, end="\r")
    if newline:
        print(msg)
    else:
        print(msg, end="\r")
    print_statusline.last_msg = msg


@command()
@option("-s", "--device", "device", type=str)
@option("--adb", default="adb")
@option_group(
    "Direction",
    option("--pull", is_flag=True),
    option("--push", is_flag=True),
    constraint=mutually_exclusive,
)
@option("--newer", "copy_newer", is_flag=True)
@argument("local")
@argument("remote", required=False)
def main(local, remote, device, adb, pull, push, copy_newer):
    adb_sync = AdbSync(device, adb, copy_newer, local, remote)
    if pull or not push:  # makes pull the default
        adb_sync.pull()
    else:
        adb_sync.push()


if __name__ == "__main__":
    main()
