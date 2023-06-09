# UBI Forensic Toolkit

The UBI Forensic Toolkit (UBIFT) is a Python command-line interface tool that aims to provide various functionalities to assist an IT-forensic evaluation of the UBIFS file system. It is based on the concepts of *The Sleuth Kit* by Brian Carrier.
As such, UBIFT aims to fulfil the requirements for forensic tools set by Brian Carrier in his paper [Defining Digital Forensic Examination and Analysis Tools Using Abstraction Layers](https://www.utica.edu/academic/institutes/ecii/publications/articles/A04C3F91-AFBB-FC13-4A2E0F13203BA980.pdf).
Furthermore, UBIFT makes use of Carrier's idea of a layered approach for forensics tools that is also described in his paper.

A notable feature of UBIFT is the ability to recover deleted data. Most commands can be used in conjunction with a **--deleted** parameter, causing UBIFT to look for deleted content. For instance, all deleted directory entries may be retrieved with the following command:

```python
(venv) PS C:\ubift> python .\ubift.py fls "E:\nand_flash.bin" 0 data --deleted
Type    Inode   Parent  Name
file    0       105     secret.txt
dir     0       104     secret_folder
file    0       107     secret_image1.jpg
file    0       107     secret_image4.jpg
```


# Usage

UBIFT uses a similar syntax as *The Sleuth Kit*. Every command has a prefix and a suffix. The prefix, such as **mtd** refers to the layer it is operating on. The suffix, such as **ls** depicts the desired operation to be performed.

UBIFT supports the following commands:

| Command        | Description      |
| ------------- |---------------|
| mtdls      | Lists information about all available Partitions, including UBI instances. UBI instances have the description 'UBI'. |
| mtdcat      | Outputs the binary data of an MTD partition, given by its index. Use 'mtdls' to see all indeces.      |
| pebcat       | Outputs a specific phyiscal erase block.  | 
| ubils       | Lists all instances of UBI and their volumes.   |
| lebls       | Lists all mapped LEBs of a specific UBI volume.      | 
| lebcat       | Outputs a specific mapped logical erase block of a specified UBI volume.      |
| fsstat       | Outputs information regarding the UBIFS file-system within a specific UBI volume.      |
| fls | Outputs information regarding file names in an UBIFS instance within a specific UBI volume. | 
| istat | Displays information about a specific inode in an UBIFS instance. |
| icat | Outputs the data of an inode. |
| ils | Lists all inodes of a given UBIFS instance. |
| ffind | Outputs directory entries associated with a given inode number. |
| ubift_recover | Extracts all files found in UBIFS instances. Creates one directory for each UBI volume with UBIFS. |
| ubift_info | Outputs information regarding recoverability of deleted inodes. This parameter takes priority over all other parameters. |
| jls | **(develop branch only)** Lists all nodes within the journal. |

For a detailed description of every command, refer to the **--help** of the tool.

In order to recover all files (including deleted files), use the following command:

```python
python .\ubift.py ubift_recover D:\your_flash_dump.bin --output D:\ --deleted
```

# Branches

### master

Contains the original version described in the master's thesis.

### develop

Contains a highly improved version that has slightly different syntax and is more lenient towards possible errors. Therefore this version might be able to parse flash images that the original may not be able to.

A notable difference is the notation for the **offset** and **name of an UBI volume**. A valid **ubils** command in the develop version is as follows:

```python
python .\ubift.py fls 'D:\flash_dump.bin' -o 123 -n data
```

As opposed to the original one:

```python
python .\ubift.py fls 'D:\flash_dump.bin' 123 data
```

# Dependencies

cstruct~=5.2

setuptools~=60.2.0

crcmod~=1.7

zstd~=1.5.4.1

python-lzo>=1.11

# Similar Tools

[UBIFS Dumper](https://github.com/nlitsme/ubidump)

[UBI Reader](https://github.com/onekey-sec/ubi_reader)

# References

[The Sleuth Kit](https://github.com/sleuthkit/sleuthkit)

# Author

Matthias Deutschmann (matthias_de@gmx.net)

