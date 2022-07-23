import os
import time
import shutil
from tqdm import tqdm
from subprocess import run
from sys import stdout, stderr

from cloup import command, option, option_group, argument
from cloup.constraints import mutually_exclusive


def print_statusline(msg: str, newline: bool = False):
    terminal_width = shutil.get_terminal_size().columns

    last_msg_length = len(print_statusline.last_msg) if hasattr(print_statusline, 'last_msg') else 0
    print(' ' * last_msg_length, end='\r')
    if newline:
        print(msg)
    else:
        print(msg, end='\r')
    print_statusline.last_msg = msg


@command()
@option('-s', '--device', 'device', type=str)
@option('--adb', default='adb')
@option_group('Direction', option('--pull', is_flag=True), option('--push', is_flag=True),
              constraint=mutually_exclusive)
@option('--newer', 'copy_newer', is_flag=True)
@argument('local')
@argument('remote')
def main(local, remote, device, adb, pull, push, copy_newer):
    device_switch = ['-s', device] if device else []

    if not push:
        for source in ["bluetooth", "Books", "DCIM", "Documents", "Download", "Mamajan", "Marjam", "MIUI", "Movies",
                       "Music", "Pictures", "SimpleScanner", "SplitPDF", "Telegram", "viber",
                       "Android/media/com.whatsapp/WhatsApp"]:

            # this overwrites the option from cli
            remote = f"/sdcard/{source}"

            remote_files_str = run([adb] + device_switch + ['shell', 'find', remote], capture_output=True, text=True,
                                   encoding='utf-8')

            # skips the top level folder containing all subfolders
            remote_files = remote_files_str.stdout.split('\n')[1:]

            successes = 0
            errors = 0
            skipped = 0
            overwritten = 0
            start = time.time()
            for remote_file in tqdm(remote_files):
                if remote_file and "one pace" not in remote_file.lower():
                    local_file = os.path.join(local, *remote_file.split('/'))
                    print_statusline(local_file)
                    # local_file_path = os.path.dirname(local_file)

                    overwrite = False

                    if copy_newer:
                        local_time = int(os.path.getmtime(local_file))
                        check_time = run([adb] + device_switch + ['shell', 'stat', remote_file, '-c', '%.9Y'],
                                         capture_output=True, text=True, encoding='utf-8')
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

                        pull_process = run([adb] + device_switch + ['pull', '-a', '-p', remote_file, local_file],
                                           capture_output=True, text=True, encoding='utf-8')
                        msg = pull_process.stdout
                        if msg and "adb: error:" in msg:
                            print(pull_process.stdout, file=stderr, end='')
                            errors += 1
                        else:
                            successes += 1
                            overwritten += 1 if overwrite else 0
                    else:
                        skipped += 1
            print_statusline(f"copied {source}: {successes} successes and {errors} errors in {time.time() - start}s "
                             f"(skipped {skipped}, overwritten {overwritten})", newline=True)


if __name__ == '__main__':
    main()
