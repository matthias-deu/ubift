import argparse
import logging
import os
import shutil
import subprocess
import sys
import getpass
import random
from time import sleep

rootlog = logging.getLogger("ubigen")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(message)s")
console.setFormatter(formatter)
rootlog.setLevel(1)
rootlog.addHandler(console)


class CommandLine:

    def __init__(self):
        pass

    def run(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command", help="Commands to run", required=True)

        # create
        create = subparsers.add_parser("create", help="Creates a new image dump.")
        create.add_argument("--output", "-o", help="Where the created image dump will be written to.", required=True)
        create.add_argument("--size", "-s", choices=[256], default=256, help="Size in MiB of the image dump.", type=int)
        create.add_argument("--contentfolder", "-cf", help="Directory of files that will be written to the image dump.",
                            required=True)
        create.add_argument("--ubi-instances", "-ubis", help="Amount of UBI instances in the image dump.", default=1, type=int)
        create.add_argument("--ubi-volumes", "-vols", help="Maximum amount of UBI volumes per instance (randomized)",
                            default=1, type=int)
        create.add_argument("--force", "-f", help="Unloads kernel modules 'ubi', 'ubifs' and 'nandsim' before running.", default=False, action="store_true")
        create.add_argument("--file-count", "-fc",
                            help="Amount of files that will be written to UBI volumes.", default=100)
        create.set_defaults(func=self._create)

        # mount
        mount = subparsers.add_parser("mount", help="Mounts an image dump containing UBI & UBIFS.")
        mount.add_argument("--mtdn", "-m", help="MTD device number.", type=int, required=True, default=0)
        mount.add_argument("--image", "-i", help="Path to UBI image file.", type=str, required=True)
        mount.set_defaults(func=self._mount)

        # simulate
        simulate = subparsers.add_parser("simulate", help="Simulates random write accesses to a mounted UBIFS file system.")
        simulate.add_argument("--contentfolder", "-cf", help="Directory of files that will be written to the image dump.",
                            required=True)
        simulate.add_argument("--mount", "-m", help="Where the UBIFS file system is mounted, e.g., /mnt", required=True)
        simulate.add_argument("--count", "-c", help="Amount of operations on files (erases, creations etc)",
                            default=800)
        simulate.add_argument("--dump", "-d", help="If set to a path, will create a dump of the UBIFS file system.", type=str)
        simulate.set_defaults(func=self._simulate)

        args = parser.parse_args()
        args.func(args)

    def _simulate(self, args):
        cf = args.contentfolder
        mountpoint = args.mount
        ops = args.count
        do_dump = args.dump

        if not os.path.exists(cf) or not os.path.isdir(cf):
            rootlog.error(f"[-] Invalid path to content folder: {cf}")
            exit(1)

        for i in range(ops):
            if i % 2 == 0:
                random_file = random.choice(os.listdir(cf))
                random_dest = random.choice(os.listdir(mountpoint))
                shutil.copy(os.path.join(cf, random_file), os.path.join(mountpoint, random_dest))
                self._execute_command(["sync", "-f", os.path.join(mountpoint, random_dest, random_file)])
                rootlog.info(f"[!] [{i+1}/{ops}] Copying file: {os.path.join(cf, random_file)} to {os.path.join(mountpoint, random_dest)}")
            else:
                done = False
                while not done:
                    dir = random.choice(os.listdir(mountpoint))
                    if len(os.listdir(os.path.join(mountpoint, dir))) == 0:
                        continue
                    file = random.choice(os.listdir(os.path.join(mountpoint, dir)))
                    path = os.path.join(mountpoint, dir, file)
                    rootlog.info(f"[!] [{i+1}/{ops}] Deleting file: {path}")
                    os.remove(path)
                    done = True

        if do_dump is not None:
            nanddump = ["nanddump", f"/dev/mtd0", "-f", do_dump, "--noecc", "--omitoob"]
            print(self._execute_command(nanddump))


    def _mount(self, args):
        mtdn = args.mtdn
        image_path = args.image

        if not os.path.exists(image_path) or not os.path.isfile(image_path):
            rootlog.error(f"[-] Invalid path to image: {image_path}")
            exit(1)

        # Create mtd devices with nandsim
        # Right now this is hardcoded to use a nand flash with parameters
        # 256 MiB, SLC, erase size: 128 KiB, page size: 2048, OOB size: 64
        ubi_instances = 1 # args.ubi_instances
        peb_count = 2048
        parts = self._create_parts_string(ubi_instances, peb_count)
        self._nandsim(256, parts)

        ubiformat = ["ubiformat", f"/dev/mtd{mtdn}", "-f", image_path]
        print(self._execute_command(ubiformat))

        ubiattach = ["ubiattach", "/dev/ubi_ctrl", "-m", str(mtdn)]
        print(self._execute_command(ubiattach))

        mount = ["mount", "-t", "ubifs", "-o", "sync", "/dev/ubi0_0", "/mnt"]
        print(self._execute_command(mount))

    def _create(self, args):
        if args.force:
            rootlog.info(f"[!] Unloading kernel modules.")
            self._reset()

        mtd_devs = self.get_mtd_devices()
        if len(mtd_devs) > 0:
            rootlog.error(f"[-] There are already MTD devices. Please remove them before running the 'create' command. Alternativly, use --force.")
            exit(1)

        ubi_instances = args.ubi_instances
        peb_count = 2048
        parts = self._create_parts_string(ubi_instances, peb_count)

        use_mtd = 0
        tmp_folder = ["/", "tmp", "vol0"]
        os.mkdir(os.path.join(*tmp_folder))
        for folder in self._load_linux_folders():
            os.mkdir(os.path.join(*tmp_folder, folder))

        filecount = args.file_count
        files_dir = args.contentfolder
        for i in range(filecount):
            random_file = random.choice(os.listdir(files_dir))
            random_dest = random.choice(os.listdir(os.path.join(*tmp_folder)))
            shutil.copy(os.path.join(files_dir, random_file), os.path.join(*tmp_folder, random_dest))

        self._execute_command(["modprobe", "ubi"])
        self._execute_command(["modprobe", "ubifs"])

        mkfs_cmd = ["mkfs.ubifs", "-r", "/tmp/vol0", "-m", "2048", "-e", "129024", "-c", "300", "-o", "/tmp/vol0.ubifs"]
        print(self._execute_command(mkfs_cmd))

        # nand flash that will be created with nand sim supports subpages therefore set -s to 512
        ubinize_cmd = ["ubinize", "-o", "/tmp/vol0.ubi", "-m", "2048", "-s", "512", "-p", "128KiB", "./test.cfg"]
        print(self._execute_command(ubinize_cmd))

        rootlog.info(f"[!] Cleaning tmp files.")
        shutil.rmtree(os.path.join(*tmp_folder))
        os.remove("/tmp/vol0.ubifs")


    def _load_linux_folders(self) -> list[str]:
        folders = []
        with open("./folder_names.txt", mode="r") as f:
            for line in f:
                if "0:" in line:
                    folders.append(line[2:].rstrip())
        return folders

    def _nandsim(self, size: int, parts: str) -> str:
        if size == 256:
            cmd = ["modprobe", "nandsim", "first_id_byte=0x2c", "second_id_byte=0xda", "third_id_byte=0x90", "fourth_id_byte=0x95"]
            if parts is not None and len(parts) > 0:
                cmd = cmd + [f"parts={parts}"]
            return self._execute_command(subprocess.list2cmdline(cmd), shell=True)
        else:
            rootlog.error(f"[-] Unsupported size. Supported sizes: [256]")
            sys.exit(1)

    def _create_parts_string(self, ubi_instances: int, pebs: int) -> str:
        """
        Creates a 'parts' parameter needed for mtdparts.
        Example: 300,100,50
        :param ubi_instances:
        :param pebs:
        :return:
        """
        if ubi_instances == 1:
            return f"{pebs}"

        rand = random.randint(100, pebs // ubi_instances)
        peb_count = pebs - rand
        mtd_parts = f"{rand}"
        instances = 2
        while peb_count >= rand and instances < ubi_instances:
            rand = random.randint(100, pebs // ubi_instances)
            peb_count = peb_count - rand
            instances = instances + 1
            mtd_parts = mtd_parts + f",{rand}"
            rand = random.randint(300, 500)
        if mtd_parts[0] == ",":
            mtd_parts = mtd_parts[1:]
        mtd_parts = mtd_parts + f",{peb_count}"

        return mtd_parts

    def get_mtd_devices(self) -> list[str]:
        """
        :return: Returns the contents of /sys/class/mtd
        """

        cmd = ["ls", "/sys/class/mtd"]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = process.stdout

        if len(output) == 0:
            return []
        else:
            return output.splitlines()

    def _reset(self):
        """
        Unloads all kernel modules
        :return:
        """
        self._execute_command(["rmmod", "nandsim"])

    def _execute_command(self, cmd: list[str], text: bool = True, shell: bool = False) -> str:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=text, shell=shell)
        output = process.stdout
        return output

def check_sudo() -> None:
    if "root" in getpass.getuser():
        return
    else:
        sys.exit("You need to have root privileges to run this script.")


if __name__ == "__main__":
    if os.name == 'nt':
        rootlog.error(f"[-] This program supports UNIX only.")
        sys.exit(1)
    else:
        check_sudo()
        CommandLine().run()
