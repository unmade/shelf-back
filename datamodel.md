# File Storage Data Model

## User Files

### Basic concept

Let's start with the example to illustrate some basic concepts.

Suppose, we have two users: `Alice` and `Bob`.
Whenever a user uploads a file, he actually uploads it
to his own namespace in a storage:

    Alice/          <--- namespace
        folder/
        file

    Bob/            <--- namespace
        file

> Namespace - is a root directory for a user.

Typically, namespace matches to a given user name.

File metadata is stored in DB. Every operation with a file,
should be reflected both in a storage and in DB. For example,
if `Alice` moves `file` in a `folder`, then `file` should be
moved in a storage to a `folder` and metadata should be updated
accordingly.

User owns a namespace and file belongs to a namespace, not to a user.
This is probably not needed now, but can give flexibility in the future
with things like Group/Team folders.

### File metadata

Basic file metadata includes such information as:
- namespace to which file belong
- path to a file relative to namespace
- size
- modified time

For a basic file metadata we can use only one self-referential table
to represent both files and folders.

Some pseudo-code, that shows sample data model:

```python
class Namespace:
    pk: int
    path: str
    owner -> User


class File:
    pk: int
    path: str
    size: int
    mtime: float
    is_dir: bool

    parent -> File
    namespace -> Namespace
```

## Sharing

For now, we consider only user-to-user sharing.

Use cases:

- user can share any file or folder, only if he owns it
- shared file/folder initially "mounted" to user home folder
- user can move shared file/folder, but not to another shared folder
- shared file/folder have permissions on read, write, share
- permissions take effect for all files/folders in shared folder

Shared folder is a virtual concept, meaning, that it cannot be reflected
in a storage itslef, but only at a database level. In other words,
the actual file hierarchy in a storage would look like that:

Suppose we have a following structure:

        Application-level               Storage-level

    Alice/                            Alice/
        folder3/                          folder3/
            shared/       --\
                inner/      |
                    file1   |
                file2       |
            file3           |                 file3
                            |
    Bob/                    |         Bob/
        folder1/            |             folder1/
            folder2/     <--/                 folder2/
                inner/                            inner/
                    file1                             file1
                file2                             file2
            file4                             file4

Here, `Bob` shares his `folder2` with `Alice`. Initially,
`Alice` would see `folder2` in her home directory, but as we can see,
she moved it to `Alice/folder3` and renamed it to `shared`

### Representation at Application-level

Shared file/folder can be represented with following model:

```python
class Share:
    pk: int
    mount_path: str
    mount_namespace -> Namespace
    shared_file -> File
```

We can then find parent shared folder for a given namespace and space like this:

```sql
SELECT
    s.shared_file
FROM
    shares s
JOIN
    files f ON f.id = s.shared_file
WHERE
    s.mount_namespace = ns_id AND POSITION(s.mount_path in 'folder3/shared/inner')
```
