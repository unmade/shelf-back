module default {
    type Account {
        property email -> str {
            constraint exclusive;
        };
        required property first_name -> str;
        required property last_name -> str;
        required property created_at -> datetime;

        property storage_quota -> int64;

        required single link user -> User {
            on target delete DELETE SOURCE;
        };
    }

    abstract type Auditable {}

    type AuditTrailAction {
        required property name -> str {
            constraint exclusive;
        };
    }

    type AuditTrail {
        required property created_at -> datetime;

        required link action -> AuditTrailAction {
            on target delete DELETE SOURCE;
        };
        multi link assets -> Auditable {
            on target delete DELETE SOURCE;
        };
        required link user -> User {
            on target delete DELETE SOURCE;
        };
    }

    type File extending Auditable {
        required property name -> str;
        required property path -> str;
        required property size -> int64;
        required property mtime -> float64;

        required link mediatype -> MediaType;
        required link namespace -> Namespace;

        constraint exclusive on ((.path, .namespace));
    }

    type FileMetadata {
        required property data -> json;

        required link file -> File {
            constraint exclusive;
            on target delete DELETE SOURCE;
        };
    }

    type Fingerprint {
        required property part1 -> int32;
        required property part2 -> int32;
        required property part3 -> int32;
        required property part4 -> int32;

        required link file -> File {
            constraint exclusive;
            on target delete DELETE SOURCE;
        };

        index on (.part1);
        index on (.part2);
        index on (.part3);
        index on (.part4);
    }

    type MediaType {
        required property name -> str {
            constraint exclusive;
        };
    }

    type Namespace {
        required property path -> str {
            constraint exclusive;
        };
        required link owner -> User {
            on target delete DELETE SOURCE;
        };
    }

    type SharedLink {
        required property token  -> str {
            constraint exclusive;
        }
        required link file -> File {
            constraint exclusive;
            on target delete DELETE SOURCE;
        }
    }

    type User {
        required property username -> str {
            constraint exclusive;
        };
        required property password -> str;
        required property superuser -> bool;

        multi link bookmarks -> File {
            on target delete allow;
        };
    }
}
