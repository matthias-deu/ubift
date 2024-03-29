# UBI Forensic Toolkit

The UBI Forensic Toolkit (UBIFT) is a Python command-line interface tool that aims to provide various functionalities to assist an IT-forensic evaluation of the UBIFS file system. It is based on the concepts of *The Sleuth Kit* by Brian Carrier.
As such, UBIFT aims to fulfil the requirements for forensic tools set by Brian Carrier in his paper [Defining Digital Forensic Examination and Analysis Tools Using Abstraction Layers](https://www.utica.edu/academic/institutes/ecii/publications/articles/A04C3F91-AFBB-FC13-4A2E0F13203BA980.pdf).
Furthermore, UBIFT makes use of Carrier's idea of a layered approach for forensics tools that is also described in his paper.

A notable feature of UBIFT is the ability to recover deleted data. Most commands can be used in conjunction with a **--deleted** parameter, causing UBIFT to look for deleted content. For instance, all deleted directory entries may be retrieved with the following command:

```python
python ./ubift.py fls /path/to/your_flash_dump.bin -o 0 -n data --deleted
Type    Inode   Parent  Name
file    0       105     secret.txt
dir     0       104     secret_folder
file    0       107     secret_image1.jpg
file    0       107     secret_image4.jpg
```

In order to recover all files (including deleted files), use the following command:

```python
python ./ubift.py ubift_recover /path/to/your_flash_dump.bin --output /path/to/output --deleted
```

# Usage

UBIFT uses a similar syntax as *The Sleuth Kit*. Every command has a prefix and a suffix. The prefix, such as **mtd** refers to the layer it is operating on. The suffix, such as **ls** depicts the desired operation to be performed.

UBIFT supports the following commands:

| Command       | Description                                                                                                              |
|---------------|--------------------------------------------------------------------------------------------------------------------------|
| mtdls         | Lists information about all available Partitions, including UBI instances. UBI instances have the description 'UBI'.     |
| mtdcat        | Outputs the binary data of an MTD partition, given by its index. Use 'mtdls' to see all indeces.                         |
| pebcat        | Outputs a specific phyiscal erase block.                                                                                 | 
| ubils         | Lists all instances of UBI and their volumes.                                                                            |
| ubicat        | Outputs contents of a specific UBI volume to stdout.                                                                     |
| lebls         | Lists all mapped LEBs of a specific UBI volume.                                                                          | 
| lebcat        | Outputs a specific mapped logical erase block of a specified UBI volume.                                                 |
| fsstat        | Outputs information regarding the UBIFS file-system within a specific UBI volume.                                        |
| fls           | Outputs information regarding file names in an UBIFS instance within a specific UBI volume.                              | 
| istat         | Displays information about a specific inode in an UBIFS instance.                                                        |
| icat          | Outputs the data of an inode.                                                                                            |
| ils           | Lists all inodes of a given UBIFS instance.                                                                              |
| ffind         | Outputs directory entries associated with a given inode number.                                                          |
| ubift_recover | Extracts all files found in UBIFS instances. Creates one directory for each UBI volume with UBIFS.                       |
| ubift_info    | Outputs information regarding recoverability of deleted inodes. This parameter takes priority over all other parameters. |
| jls           | Lists all nodes within the journal.                                                                                      |

For a detailed description of every command, refer to the **--help** of the tool.

# Autopsy Integration

UBIFT can be integrated with Autopsy by using the Python ingest module found at **/ubift/autopsy/ubift_autopsy.py**

An installation guide about the installation of Python modules can be found [here](https://sleuthkit.org/autopsy/docs/user-docs/3.1/module_install_page.html#:~:text=Installing%20Python%20Module,next%20time%20it%20loads%20modules.)

**IMPORTANT: The module requires UBIFT to be available in the same directory as the Python ingest module. Therefore UBIFT has to be packed and provided via [*pyInstaller*](https://pyinstaller.org/en/stable/) to the same directory as the module**

# Branch *original*

Contains the original version described in the master's thesis. The original version contains some differences that were changed in later versions. For instance, instead of specifying offsets and ubi volumes as follows:

```python
python .\ubift.py fls 'D:\flash_dump.bin' -o 123 -n data
```

The parameters were positional arguments, resulting in a loss of flexibility.

```python
python .\ubift.py fls 'D:\flash_dump.bin' 123 data
```

# Dependencies

cstruct~=5.2

setuptools~=60.2.0

crcmod~=1.7

zstandard~=0.21.0

python-lzo>=1.11

pathvalidate

# Similar Tools

[UBIFS Dumper](https://github.com/nlitsme/ubidump)

[UBI Reader](https://github.com/onekey-sec/ubi_reader)

# References

[The Sleuth Kit](https://github.com/sleuthkit/sleuthkit)

[Autopsy](https://www.autopsy.com/)

# Author

Matthias Deutschmann (matthias_de@gmx.net)

