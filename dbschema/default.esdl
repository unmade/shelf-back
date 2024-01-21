module default {
    type Account {
        email: str {
            constraint exclusive;
        };
        required first_name: str;
        required last_name: str;
        required created_at: datetime;

        storage_quota: int64;

        required user: User {
            on target delete DELETE SOURCE;
        };
    }

    abstract type Auditable {}

    type AuditTrailAction {
        required name: str {
            constraint exclusive;
        };
    }

    type AuditTrail {
        required created_at: datetime;

        required action: AuditTrailAction {
            on target delete DELETE SOURCE;
        };
        multi assets: Auditable {
            on target delete DELETE SOURCE;
        };
        required user: User {
            on target delete DELETE SOURCE;
        };
    }

    type File extending Auditable {
        required name: str;
        required path: str;
        required chash: str;
        required size: int64;
        required mtime: float64;

        required mediatype: MediaType;
        required namespace: Namespace;

        constraint exclusive on ((.path, .namespace));
        index on ((.chash, .namespace));
    }

    type FileMember {
        required actions: int16;
        required created_at: datetime;

        required file: File {
            on target delete DELETE SOURCE;
        };
        required user: User {
            on target delete DELETE SOURCE;
        };

        constraint exclusive on ((.file, .user));
    }

    type FileMemberMountPoint {
        required display_name: str;
        required member: FileMember {
            constraint exclusive;
            on target delete DELETE SOURCE;
        };
        required parent: File {
            on target delete DELETE SOURCE;
        };
    }

    type FileMetadata {
        required data: json;

        required file: File {
            constraint exclusive;
            on target delete DELETE SOURCE;
        };
    }

    type Fingerprint {
        required part1: int32;
        required part2: int32;
        required part3: int32;
        required part4: int32;

        required file: File {
            constraint exclusive;
            on target delete DELETE SOURCE;
        };

        index on (.part1);
        index on (.part2);
        index on (.part3);
        index on (.part4);
    }

    type MediaType {
        required name: str {
            constraint exclusive;
        };
    }

    type Namespace {
        required path: str {
            constraint exclusive;
        };
        required owner: User {
            on target delete DELETE SOURCE;
        };
    }

    type SharedLink {
        required token : str {
            constraint exclusive;
        }
        required created_at: datetime;
        required file: File {
            constraint exclusive;
            on target delete DELETE SOURCE;
        }
    }

    type User {
        required username: str {
            constraint exclusive;
        };
        required password: str;
        required superuser: bool;

        multi bookmarks: File {
            on target delete allow;
        };
    }
}
